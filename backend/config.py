from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent # 项目根目录 
DATA_DIR = BASE_DIR / "data" # 词频数据目录
FRONTEND_DIR = BASE_DIR / "frontend" # 前端目录
DATABASE_URL = f"sqlite:///{BASE_DIR / 'vocab_estimator.db'}" # SQLite数据库文件路径

# 按词频排名划分词汇层级
LEVEL_RANGES = [
    (1, 1, 1000),
    (2, 1001, 3000),
    (3, 3001, 6000),
    (4, 6001, 10000),
    (5, 10001, 20000),
]

QUESTIONS_PER_LEVEL =  10  # 每个层级抽取的测试单词数量
CONFIDENCE_Z = 1.645  # 90% 置信区间
