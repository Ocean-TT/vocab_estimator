from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
FRONTEND_DIR = BASE_DIR / "frontend"
DATABASE_URL = f"sqlite:///{BASE_DIR / 'vocab_estimator.db'}"

# 分层配置：按词频排名划分词汇层级
LEVEL_RANGES = [
    (1, 1, 1000),
    (2, 1001, 3000),
    (3, 3001, 6000),
    (4, 6001, 10000),
    (5, 10001, 20000),
]

QUESTIONS_PER_LEVEL = 10
CONFIDENCE_Z = 1.645  # 90% 置信区间
