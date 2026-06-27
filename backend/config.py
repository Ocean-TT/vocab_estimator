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

# 各层级总词数
LEVEL_TOTAL_WORDS = {
    1: 1000,
    2: 2000,
    3: 3000,
    4: 4000,
    5: 10000,
}

# 四类学习者模型
LEARNER_MODELS = {
    "初学者": {
        "level_rates": {1: 0.90, 2: 0.50, 3: 0.10, 4: 0.00, 5: 0.00},
        "base_vocab": 2000,
    },
    "四级水平": {
        "level_rates": {1: 0.99, 2: 0.75, 3: 0.33, 4: 0.00, 5: 0.00},
        "base_vocab": 4500,
    },
    "六级/雅思水平": {
        "level_rates": {1: 1.00, 2: 0.90, 3: 0.67, 4: 0.25, 5: 0.10},
        "base_vocab": 6500,
    },
    "GRE/高级水平": {
        "level_rates": {1: 1.00, 2: 1.00, 3: 0.90, 4: 0.75, 5: 0.50},
        "base_vocab": 10000,
    },
}

QUESTIONS_PER_LEVEL =  10  # 每个层级抽取的测试单词数量
CONFIDENCE_Z = 1.645  # 90% 置信区间
