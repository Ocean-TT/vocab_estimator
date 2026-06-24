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

def estimate_from_level_responses(level_responses: dict[int, list[str]]) -> EstimationResult:
    """
    核心估算逻辑：输入各层级的回答记录（如 {1: ["know", "unknown"], 2: ...}），返回估算结果。
    """
    level_breakdown: list[LevelEstimate] = []
    total_estimate = 0.0
    total_variance = 0.0

    for level, start_rank, end_rank in LEVEL_RANGES:
        # 获取该层级的所有回答
        responses = level_responses.get(level, [])
        sample_size = len(responses)
        
        total_words = level_total_words(start_rank, end_rank)
        
        # 统计已知单词数（支持 batch 和 session）
        # 这里统一判定 "know" 或 True 为认识
        known_count = sum(1 for r in responses if r in ("know", True))
        
        rate = known_count / sample_size if sample_size > 0 else 0.0
        known_words = round(total_words * rate)

        level_breakdown.append(
            LevelEstimate(
                level=level, rank_start=start_rank, rank_end=end_rank,
                total_words=total_words, known_words=known_words,
                recognition_rate=round(rate, 4),
            )
        )

        total_estimate += total_words * rate
        if sample_size > 0:
            variance = (rate * (1 - rate) / sample_size) * (total_words**2)
            total_variance += variance

    std_error = total_variance**0.5
    margin = CONFIDENCE_Z * std_error
    
    return EstimationResult(
        point_estimate=round(total_estimate),
        lower_bound=max(0, round(total_estimate - margin)),
        upper_bound=round(total_estimate + margin),
        confidence_level=0.90,
        level_breakdown=level_breakdown,
    )

def estimate_vocabulary(db: Session, session_id: int) -> EstimationResult:
    answers = (
        db.query(TestAnswer, Word)
        .join(Word, TestAnswer.word_id == Word.id)
        .filter(TestAnswer.session_id == session_id)
        .all()
    )
    # 整理数据格式
    by_level: dict[int, list[str]] = {}
    for answer, word in answers:
        by_level.setdefault(word.level, []).append(answer.response)
    
    return estimate_from_level_responses(by_level)