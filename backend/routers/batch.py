from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.config import CONFIDENCE_Z, LEVEL_RANGES
from backend.database import get_db
from backend.schemas import BatchEstimateItem, BatchEstimateResponse, BatchProfile
from backend.services.estimator import level_total_words

router = APIRouter(prefix="/api/batch", tags=["batch"])

# 四类学习者预设认识率（骨架示例，可在报告中调整）
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
    del db  # 批量模拟不依赖数据库，保留参数便于后续扩展
    selected = profiles or DEFAULT_PROFILES
    results = [_simulate_profile(profile) for profile in selected]
    return BatchEstimateResponse(results=results)


@router.get("/estimate/default", response_model=BatchEstimateResponse)
def batch_estimate_default():
    results = [_simulate_profile(profile) for profile in DEFAULT_PROFILES]
    return BatchEstimateResponse(results=results)
