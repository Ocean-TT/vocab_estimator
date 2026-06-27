import re
from typing import Dict, List, Set

from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.config import LEVEL_RANGES, CONFIDENCE_Z
from backend.models.entities import Word


def extract_words(text: str) -> List[str]:
    words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
    return list(set(words))


def normalize_words(words: List[str]) -> List[str]:
    normalized: Set[str] = set()
    for w in words:
        w = w.strip().lower()
        if re.fullmatch(r"[a-zA-Z]+", w):
            normalized.add(w)
    return list(normalized)


def match_words(words: List[str], db: Session) -> Dict[str, Word]:
    if not words:
        return {}
    word_objs = db.execute(select(Word).where(Word.word.in_(words))).scalars().all()
    return {w.word: w for w in word_objs}


def count_by_level(matched: Dict[str, Word]) -> Dict[int, int]:
    level_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for word_obj in matched.values():
        if word_obj.level in level_counts:
            level_counts[word_obj.level] += 1
    return level_counts


def level_total_words(start_rank: int, end_rank: int) -> int:
    return end_rank - start_rank + 1


def estimate_vocab_by_reverse(
    level_counts: Dict[int, int],
    min_recognition_rate: float = 0.85,
) -> Dict:
    """
    方法C：根据文档中各层级单词分布和最低认识率假设，反推学员词汇量。
    
    核心逻辑：从高频到低频逐层累加覆盖率，直到满足最低认识率要求。
    超出的部分按比例分配给最后一层，反推该层需要掌握的比例。
    """
    level_breakdown = []
    total_unique_words = sum(level_counts.values())
    
    if total_unique_words == 0:
        return {
            "point_estimate": 0,
            "lower_bound": 0,
            "upper_bound": 0,
            "confidence_level": 0.90,
            "level_breakdown": [],
            "explanation": "文档中未找到可识别的单词",
            "max_level": 0,
        }

    level_percentages = {}
    for level in [1, 2, 3, 4, 5]:
        level_percentages[level] = level_counts[level] / total_unique_words

    min_rate = min_recognition_rate
    remaining_required = min_rate
    level_min_rates = {}

    for level in [1, 2, 3, 4, 5]:
        if remaining_required <= 0:
            level_min_rates[level] = 0.0
            continue
        max_contribution = level_percentages[level]
        if max_contribution >= remaining_required:
            level_min_rates[level] = remaining_required / max_contribution
            remaining_required = 0
        else:
            level_min_rates[level] = 1.0
            remaining_required -= max_contribution

    total_point = 0.0
    total_lower = 0.0
    total_upper = 0.0
    max_level = 0

    for level, start_rank, end_rank in LEVEL_RANGES:
        total_words = level_total_words(start_rank, end_rank)
        min_rate_for_level = level_min_rates.get(level, 0.0)
        
        if min_rate_for_level > 0:
            max_level = level

        point_p = min_rate_for_level
        p_hat = min_rate_for_level

        if p_hat == 0:
            lower_p, upper_p = 0.0, 0.0
        elif p_hat == 1.0:
            lower_p, upper_p = 1.0, 1.0
        else:
            n = level_counts.get(level, 1)
            if n == 0:
                n = 1
            z = CONFIDENCE_Z
            z2 = z * z
            k = round(p_hat * n)
            center = (k + z2 / 2) / (n + z2)
            margin = z * ((p_hat * (1 - p_hat) / n) + (z2 / (4 * n * n))) ** 0.5
            lower_p = max(0.0, center - margin)
            upper_p = min(1.0, center + margin)

        estimated_known = round(total_words * point_p)

        level_breakdown.append({
            "level": level,
            "rank_start": start_rank,
            "rank_end": end_rank,
            "total_words": total_words,
            "document_word_count": level_counts.get(level, 0),
            "document_percentage": round(level_percentages.get(level, 0) * 100, 2),
            "min_recognition_rate": round(min_rate_for_level * 100, 1),
            "estimated_known_words": estimated_known,
        })

        total_point += total_words * point_p
        total_lower += total_words * lower_p
        total_upper += total_words * upper_p

    point_estimate = round(total_point)
    lower_bound = max(0, round(total_lower))
    upper_bound = round(total_upper)

    explanation = (
        f"基于文档词汇分布反推：假设最低认识率 {int(min_recognition_rate * 100)}%，"
        f"词汇量约 {point_estimate} 词（90%置信区间：{lower_bound}-{upper_bound}）"
    )

    return {
        "point_estimate": point_estimate,
        "lower_bound": lower_bound,
        "upper_bound": upper_bound,
        "confidence_level": 0.90,
        "level_breakdown": level_breakdown,
        "explanation": explanation,
        "max_level": max_level,
        "total_unique_words": total_unique_words,
        "min_recognition_rate": min_recognition_rate,
    }


def analyze_text_auto(text: str, min_recognition_rate: float, db: Session) -> Dict:
    words = extract_words(text)
    total_words = len(words)
    matched = match_words(words, db)
    level_counts = count_by_level(matched)

    estimate = estimate_vocab_by_reverse(level_counts, min_recognition_rate)

    return {
        "total_unique_words": total_words,
        "matched_words": len(matched),
        "vocab_estimate": estimate,
    }


def analyze_multiple_docs(
    docs: Dict[str, str],
    min_recognition_rates: Dict[str, float] = None,
    db: Session = None,
) -> Dict[str, Dict]:
    """
    批量分析多个文档，返回每类学员的词汇量估计。
    
    docs: {"C": "text...", "F": "text...", "P": "text...", "K": "text..."}
    min_recognition_rates: 可选，为每个文档指定不同的最低认识率
    """
    if min_recognition_rates is None:
        min_recognition_rates = {
            "C": 0.95,
            "F": 0.88,
            "P": 0.80,
            "K": 0.70,
        }

    results = {}
    for doc_name, text in docs.items():
        rate = min_recognition_rates.get(doc_name, 0.85)
        words = extract_words(text)
        total_words = len(words)
        
        matched = {}
        level_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        
        if db:
            matched = match_words(words, db)
            level_counts = count_by_level(matched)
        
        estimate = estimate_vocab_by_reverse(level_counts, rate)
        
        results[doc_name] = {
            "doc_name": doc_name,
            "total_unique_words": total_words,
            "matched_words": len(matched),
            "min_recognition_rate": rate,
            "vocab_estimate": estimate,
        }

    return results
