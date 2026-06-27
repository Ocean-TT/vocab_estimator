# 清洗真实的词频表
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent
ROOT = DATA_DIR.parent
sys.path.insert(0, str(ROOT))

from backend.config import LEVEL_RANGES  # noqa: E402

# 词条块起始：rank + 单词，如 "1 the" 或 "5604 Caribbean"
ENTRY_HEADER = re.compile(r"^(\d+)\s+(\S.*?)\s*$", re.MULTILINE)
# 音标行：- [ðə]  [ðə]
PHONETIC_LINE = re.compile(r"^\-\s*\[[^\]]+\]")
# 从释义行提取引号内中文
QUOTED_TEXT = re.compile(r'"([^"]*)"')


def rank_to_level(rank: int) -> int:
    for level, start_rank, end_rank in LEVEL_RANGES:
        if start_rank <= rank <= end_rank:
            return level
    return LEVEL_RANGES[-1][0]


def normalize_word(raw_word: str) -> str | None:
    word = raw_word.strip().lower()
    word = word.replace("''", "'")
    word = word.strip(".,;:")

    if not word or word == "undefined":
        return None
    if "undefined" in word:
        return None
    # 允许字母、撇号、连字符
    if not re.fullmatch(r"[a-z][a-z'\-]*", word):
        return None
    return word


def is_link_line(line: str) -> bool:
    lowered = line.lower()
    return (
        "人人词典" in line
        or "http" in lowered
        or "collins" in lowered
        or "ldoceonline" in lowered
    )


def is_phonetic_line(line: str) -> bool:
    stripped = line.strip()
    return bool(PHONETIC_LINE.match(stripped)) and '.["' not in stripped


def extract_definitions(block: str) -> str:
    parts: list[str] = []
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        if is_link_line(stripped) or is_phonetic_line(stripped):
            continue

        body = stripped[2:].strip()
        if not body or body.lower() == "undefined":
            continue

        quoted = QUOTED_TEXT.findall(body)
        if quoted:
            parts.extend(item.strip() for item in quoted if item.strip())
            continue

        # 兜底：去掉词性前缀，保留剩余文本
        fallback = re.sub(r"^[a-z.&\s]+?\.", "", body, flags=re.IGNORECASE).strip()
        if fallback and fallback.lower() != "undefined":
            parts.append(fallback)

    # 去重并保持顺序
    seen: set[str] = set()
    unique: list[str] = []
    for item in parts:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return ",".join(unique)


def parse_markdown_file(file_path: Path) -> list[dict]:
    content = file_path.read_text(encoding="utf-8")
    headers = list(ENTRY_HEADER.finditer(content))
    rows: list[dict] = []

    for index, match in enumerate(headers):
        rank = int(match.group(1))
        raw_word = match.group(2)
        start = match.end()
        end = headers[index + 1].start() if index + 1 < len(headers) else len(content)
        block = content[start:end]

        word = normalize_word(raw_word)
        if word is None:
            continue

        definition = extract_definitions(block)
        if not definition:
            continue

        rows.append(
            {
                "rank": rank,
                "word": word,
                "definition": definition,
            }
        )

    return rows


def load_all_parts(data_dir: Path) -> pd.DataFrame:
    part_files = sorted(data_dir.glob("part*.md"))
    if not part_files:
        raise FileNotFoundError(f"未找到 part*.md 文件: {data_dir}")

    all_rows: list[dict] = []
    for file_path in part_files:
        parsed = parse_markdown_file(file_path)
        all_rows.extend(parsed)
        print(f"  {file_path.name}: 解析 {len(parsed)} 条")

    return pd.DataFrame(all_rows)


def deduplicate_words(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """同一单词保留 rank 最小的一条。"""
    before = len(df)
    df = df.sort_values(["word", "rank"]).drop_duplicates(subset=["word"], keep="first")
    df = df.sort_values("rank").reset_index(drop=True)
    removed = before - len(df)
    return df, removed


def clean_vocabulary(
    data_dir: Path | None = None,
    output_path: Path | None = None,
    max_rank: int = 20000,
) -> pd.DataFrame:
    data_dir = data_dir or DATA_DIR
    output_path = output_path or data_dir / "coca_20000.csv"

    print(f"读取目录: {data_dir}")
    df = load_all_parts(data_dir)
    print(f"原始条目: {len(df)}")

    # 过滤 rank 范围
    df = df[df["rank"] <= max_rank].copy()
    print(f"rank <= {max_rank}: {len(df)}")

    # 去掉 rank 重复（保留第一条）
    rank_dupes = df.duplicated(subset=["rank"], keep="first").sum()
    if rank_dupes:
        df = df.drop_duplicates(subset=["rank"], keep="first")
        print(f"去除 rank 重复: {rank_dupes} 条")

    df, word_dupes_removed = deduplicate_words(df)
    print(f"去除 word 重复: {word_dupes_removed} 条")
    print(f"清洗后条目: {len(df)}")

    df["level"] = df["rank"].apply(rank_to_level)

    # 写入 CSV
    export_df = df[["rank", "word", "definition", "level"]]
    export_df.to_csv(output_path, index=False, encoding="utf-8")
    print(f"已保存: {output_path}")

    # 分层统计
    print("\n各层词数:")
    for level, start_rank, end_rank in LEVEL_RANGES:
        count = ((df["rank"] >= start_rank) & (df["rank"] <= end_rank)).sum()
        print(f"  L{level} ({start_rank}-{end_rank}): {count}")

    return export_df


def main() -> None:
    parser = argparse.ArgumentParser(description="清洗 COCA 词表 markdown 为 CSV")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DATA_DIR,
        help="part*.md 所在目录",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DATA_DIR / "coca_20000.csv",
        help="输出 CSV 路径",
    )
    parser.add_argument(
        "--max-rank",
        type=int,
        default=20000,
        help="保留的最大 rank（默认 20000）",
    )
    args = parser.parse_args()
    clean_vocabulary(args.data_dir, args.output, args.max_rank)


if __name__ == "__main__":
    main()
