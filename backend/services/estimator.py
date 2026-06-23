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
    known_words: int
    recognition_rate: float


@dataclass
class EstimationResult:
    point_estimate: int
    lower_bound: int
    upper_bound: int
    confidence_level: float
    level_breakdown: list[LevelEstimate]


def level_total_words(start_rank: int, end_rank: int) -> int:
    return end_rank - start_rank + 1


def estimate_vocabulary(db: Session, session_id: int) -> EstimationResult:
    """
    基于分层抽样认识率估算总词汇量，并用 Wilson 区间近似置信区间。
    """
    answers = (
        db.query(TestAnswer, Word)
        .join(Word, TestAnswer.word_id == Word.id)
        .filter(TestAnswer.session_id == session_id)
        .all()
    )

    by_level: dict[int, list[str]] = {}
    for answer, word in answers:
        by_level.setdefault(word.level, []).append(answer.response)

    level_breakdown: list[LevelEstimate] = []
    total_estimate = 0.0
    total_variance = 0.0

    for level, start_rank, end_rank in LEVEL_RANGES:
        responses = by_level.get(level, [])
        if not responses:
            continue

        total_words = level_total_words(start_rank, end_rank)
        known_count = sum(1 for r in responses if r == "know")
        sample_size = len(responses)
        rate = known_count / sample_size if sample_size else 0.0
        known_words = round(total_words * rate)

        level_breakdown.append(
            LevelEstimate(
                level=level,
                rank_start=start_rank,
                rank_end=end_rank,
                total_words=total_words,
                known_words=known_words,
                recognition_rate=round(rate, 4),
            )
        )

        total_estimate += total_words * rate

        # 二项分布方差近似：p(1-p)/n * N^2
        if sample_size > 0:
            variance = (rate * (1 - rate) / sample_size) * (total_words**2)
            total_variance += variance

    std_error = total_variance**0.5
    margin = CONFIDENCE_Z * std_error
    point = round(total_estimate)
    lower = max(0, round(total_estimate - margin))
    upper = round(total_estimate + margin)

    return EstimationResult(
        point_estimate=point,
        lower_bound=lower,
        upper_bound=upper,
        confidence_level=0.90,
        level_breakdown=level_breakdown,
    )
