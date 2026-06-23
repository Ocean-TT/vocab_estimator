"""初始化数据库并导入示例词表。"""

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from backend.config import DATA_DIR, LEVEL_RANGES  # noqa: E402
from backend.database import Base, SessionLocal, engine  # noqa: E402
from backend.models.entities import Word  # noqa: E402

COMMON_WORDS = [
    "the", "be", "to", "of", "and", "a", "in", "that", "have", "I",
    "it", "for", "not", "on", "with", "he", "as", "you", "do", "at",
    "this", "but", "his", "by", "from", "they", "we", "say", "her", "she",
    "or", "an", "will", "my", "one", "all", "would", "there", "their", "what",
    "approach", "benefit", "community", "develop", "environment", "feature",
    "global", "history", "important", "language", "ambiguous", "criterion",
    "deliberate", "equivalent", "framework", "hypothesis", "implementation",
    "jurisdiction", "knowledge", "legitimate", "methodology", "nevertheless",
]


def rank_to_level(rank: int) -> int:
    for level, start_rank, end_rank in LEVEL_RANGES:
        if start_rank <= rank <= end_rank:
            return level
    return LEVEL_RANGES[-1][0]


def load_words_from_csv(csv_path: Path) -> list[dict]:
    rows: list[dict] = []
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rank = int(row["rank"])
            rows.append(
                {
                    "word": row["word"].strip(),
                    "rank": rank,
                    "level": rank_to_level(rank),
                    "definition": row.get("definition", "").strip(),
                }
            )
    return rows


def generate_demo_words(words_per_level: int = 120) -> list[dict]:
    """为每个层级生成演示词表，保证抽样算法可运行。"""
    words: list[dict] = []
    common_index = 0

    for level, start_rank, end_rank in LEVEL_RANGES:
        span = end_rank - start_rank + 1
        step = max(1, span // words_per_level)
        rank = start_rank

        while rank <= end_rank and len([w for w in words if w["level"] == level]) < words_per_level:
            if common_index < len(COMMON_WORDS):
                word = COMMON_WORDS[common_index]
                common_index += 1
            else:
                word = f"level{level}_word_{rank}"

            words.append(
                {
                    "word": word,
                    "rank": rank,
                    "level": level,
                    "definition": f"Demo definition for '{word}' (rank {rank})",
                }
            )
            rank += step

    return words


def seed():
    Base.metadata.create_all(bind=engine)
    csv_path = DATA_DIR / "sample_words.csv"

    if csv_path.exists():
        payload = load_words_from_csv(csv_path)
        if len(payload) < 100:
            payload = generate_demo_words()
    else:
        payload = generate_demo_words()

    db = SessionLocal()
    try:
        db.query(Word).delete()
        db.add_all([Word(**item) for item in payload])
        db.commit()
        print(f"Imported {len(payload)} words.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
