from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.config import CONFIDENCE_Z, LEVEL_RANGES
from backend.models.entities import TestAnswer, Word


@dataclass
class LevelEstimate:
    level: int
    rank_start: int
    rank_end: int
    total_words: int
    sampled_count: int
    known_count: int
    recognition_rate: float
    estimated_known_words: int


@dataclass
class EstimationResult:
    point_estimate: int
    lower_bound: int
    upper_bound: int
    confidence_level: float
    level_breakdown: list[LevelEstimate]


def level_total_words(start_rank: int, end_rank: int) -> int:
    return end_rank - start_rank + 1


def wilson_interval(k: int, n: int, z: float) -> tuple[float, float, float]:
    """
    Wilson 得分区间，返回 (lower_p, point_p, upper_p)。
    比正态近似更适合小样本和极端比例（0% 或 100%）。
    """
    if n == 0:
        return 0.0, 0.0, 1.0

    p_hat = k / n
    z2 = z * z

    center = (k + z2 / 2) / (n + z2)
    margin = z * ((p_hat * (1 - p_hat) / n) + (z2 / (4 * n * n))) ** 0.5
    lower = max(0.0, center - margin)
    upper = min(1.0, center + margin)

    return lower, p_hat, upper


def _count_known(responses: list, unsure_strategy: str = "ignore") -> tuple[int, int]:
    """
    统计认识数和有效样本数。
    unsure_strategy:
      - "ignore": 忽略不确定，仅统计 know/unknown（默认）
      - "half": 不确定计 0.5 个认识
      - "count_as_unknown": 不确定当作不认识
    """
    known_count = 0
    valid_count = 0

    for r in responses:
        if r is True or r == "know":
            known_count += 1
            valid_count += 1
        elif r is False or r == "unknown":
            valid_count += 1
        elif r == "unsure":
            if unsure_strategy == "half":
                known_count += 0.5
                valid_count += 1
            elif unsure_strategy == "count_as_unknown":
                valid_count += 1
            # "ignore" 则完全跳过

    return known_count, valid_count


def estimate_from_level_responses(
    level_responses: dict[int, list],
    unsure_strategy: str = "ignore",
) -> EstimationResult:
    """
    核心估算逻辑：输入各层级的回答记录，返回估算结果。
    使用 Wilson 得分区间计算置信区间。
    """
    level_breakdown: list[LevelEstimate] = []
    total_point = 0.0
    total_lower = 0.0
    total_upper = 0.0

    for level, start_rank, end_rank in LEVEL_RANGES:
        responses = level_responses.get(level, [])
        total_words = level_total_words(start_rank, end_rank)

        known_count, sample_size = _count_known(responses, unsure_strategy)

        lower_p, point_p, upper_p = wilson_interval(known_count, sample_size, CONFIDENCE_Z)

        estimated_known = round(total_words * point_p)

        level_breakdown.append(
            LevelEstimate(
                level=level,
                rank_start=start_rank,
                rank_end=end_rank,
                total_words=total_words,
                sampled_count=sample_size,
                known_count=known_count,
                recognition_rate=round(point_p, 4),
                estimated_known_words=estimated_known,
            )
        )

        total_point += total_words * point_p
        total_lower += total_words * lower_p
        total_upper += total_words * upper_p

    return EstimationResult(
        point_estimate=round(total_point),
        lower_bound=max(0, round(total_lower)),
        upper_bound=round(total_upper),
        confidence_level=0.90,
        level_breakdown=level_breakdown,
    )


def estimate_vocabulary(
    db: Session,
    session_id: int,
    unsure_strategy: str = "ignore",
) -> EstimationResult:
    answers = (
        db.query(TestAnswer, Word)
        .join(Word, TestAnswer.word_id == Word.id)
        .filter(TestAnswer.session_id == session_id)
        .all()
    )
    by_level: dict[int, list[str]] = {}
    for answer, word in answers:
        by_level.setdefault(word.level, []).append(answer.response)

    return estimate_from_level_responses(by_level, unsure_strategy)