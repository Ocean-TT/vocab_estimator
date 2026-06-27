from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.config import CONFIDENCE_Z, LEVEL_RANGES
from backend.database import get_db
from backend.schemas import (
    BatchEstimateItem,
    BatchEstimateResponse,
    BatchProfile,
    RealBatchRequest,
    RealBatchResultResponse,
    RealBatchLevelBreakdown,
)
from backend.services.estimator import estimate_from_level_responses, level_total_words
from backend.models.entities import Word

router = APIRouter(prefix="/api/batch", tags=["batch"])

# 四类学习者预设认识率
DEFAULT_PROFILES = [
    BatchProfile(name="初学者", know_rate_by_level={1: 0.85, 2: 0.35, 3: 0.10, 4: 0.03, 5: 0.01}),
    BatchProfile(name="四级水平", know_rate_by_level={1: 0.95, 2: 0.80, 3: 0.55, 4: 0.25, 5: 0.08}),
    BatchProfile(name="六级/雅思", know_rate_by_level={1: 0.98, 2: 0.92, 3: 0.78, 4: 0.50, 5: 0.20}),
    BatchProfile(name="高级/GRE", know_rate_by_level={1: 0.99, 2: 0.97, 3: 0.90, 4: 0.75, 5: 0.45}),
]


def _simulate_profile(profile: BatchProfile) -> BatchEstimateItem:
    total_estimate = 0.0
    total_variance = 0.0
    sample_size = 10

    for level, start_rank, end_rank in LEVEL_RANGES:
        rate = profile.know_rate_by_level.get(level, 0.0)
        total_words = level_total_words(start_rank, end_rank)
        total_estimate += total_words * rate
        variance = (rate * (1 - rate) / sample_size) * (total_words**2)
        total_variance += variance

    std_error = total_variance**0.5
    margin = CONFIDENCE_Z * std_error
    point = round(total_estimate)

    return BatchEstimateItem(
        profile=profile.name,
        point_estimate=point,
        lower_bound=max(0, round(total_estimate - margin)),
        upper_bound=round(total_estimate + margin),
        confidence_level=0.90,
    )


@router.post("/estimate", response_model=BatchEstimateResponse)
def batch_estimate(profiles: list[BatchProfile] | None = None, db: Session = Depends(get_db)):
    del db #暂时不使用数据库

    selected = profiles or DEFAULT_PROFILES
    results = [_simulate_profile(profile) for profile in selected]
    return BatchEstimateResponse(results=results)


@router.get("/estimate/default", response_model=BatchEstimateResponse)
def batch_estimate_default():
    results = [_simulate_profile(profile) for profile in DEFAULT_PROFILES]
    return BatchEstimateResponse(results=results)


@router.post("/estimate-from-words", response_model=RealBatchResultResponse)
def estimate_from_real_words(payload: RealBatchRequest, db: Session = Depends(get_db)):
    if not payload.answers:
        raise HTTPException(status_code=400, detail="答题列表不能为空")

    level_responses: dict[int, list[bool]] = {lvl: [] for lvl, _, _ in LEVEL_RANGES}
    level_sampled: dict[int, int] = {lvl: 0 for lvl, _, _ in LEVEL_RANGES}
    level_known: dict[int, int] = {lvl: 0 for lvl, _, _ in LEVEL_RANGES}
    level_unknown_words: dict[int, list[str]] = {lvl: [] for lvl, _, _ in LEVEL_RANGES}
    unmatched_words: list[str] = []
    matched_count = 0

    for item in payload.answers:
        word_lower = item.word.strip().lower()
        if not word_lower:
            continue
        word_obj = db.query(Word).filter(Word.word == word_lower).first()
        if word_obj is None:
            unmatched_words.append(item.word)
            continue

        matched_count += 1
        lvl = word_obj.level
        level_responses[lvl].append(item.known)
        level_sampled[lvl] += 1
        if item.known:
            level_known[lvl] += 1
        else:
            level_unknown_words[lvl].append(item.word)

    if matched_count == 0:
        raise HTTPException(status_code=400, detail="没有匹配到任何单词，请检查输入的单词是否正确")

    result = estimate_from_level_responses(level_responses)

    level_breakdown: list[RealBatchLevelBreakdown] = []
    for item in result.level_breakdown:
        level_breakdown.append(
            RealBatchLevelBreakdown(
                level=item.level,
                rank_start=item.rank_start,
                rank_end=item.rank_end,
                total_words=item.total_words,
                sampled_count=level_sampled.get(item.level, 0),
                known_count=level_known.get(item.level, 0),
                recognition_rate=item.recognition_rate,
                estimated_known_words=item.estimated_known_words,
                unknown_words=level_unknown_words.get(item.level, []),
            )
        )

    summary = (
        f"输入 {len(payload.answers)} 个单词，匹配 {matched_count} 个，"
        f"估计词汇量 {result.lower_bound}-{result.upper_bound} 词，"
        f"点估计 {result.point_estimate} 词，"
        f"置信度 {int(result.confidence_level * 100)}%"
    )

    return RealBatchResultResponse(
        point_estimate=result.point_estimate,
        lower_bound=result.lower_bound,
        upper_bound=result.upper_bound,
        confidence_level=result.confidence_level,
        summary=summary,
        level_breakdown=level_breakdown,
        matched_count=matched_count,
        unmatched_words=unmatched_words,
    )