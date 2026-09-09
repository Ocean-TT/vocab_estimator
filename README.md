# 英语词汇量估算工具

基于分层抽样与 IRT 自适应测试（CAT）的英语词汇量估算系统，支持在线测试、文本分析反向估算与批量学习者建模。

## 核心算法

| 方法 | 说明 |
|------|------|
| **分层抽样** | 按词频排名分 5 层，每层抽 10 词，90% 置信区间估算 |
| **CAT 自适应测试** | 基于 IRT 模型，根据作答动态调整题目难度，收敛即停 |
| **文本分析** | 上传英文文档，反向估算作者词汇量 |
| **批量建模** | 内置初学者/四级/六级/GRE 四类先验参数 |

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python · FastAPI · Pydantic |
| ORM | SQLAlchemy |
| 数据处理 | Pandas · CSV 词频表 |
| 算法 | 分层抽样 · 置信区间 · IRT (Item Response Theory) |
| 前端 | 原生 HTML/CSS/JS |
| 数据库 | SQLite |

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 导入词表
python backend/scripts/seed_words.py

# 启动
uvicorn backend.main:app --reload
```

访问 http://127.0.0.1:8000

## API 概览

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/test/start` | 开始分层抽样测试 |
| POST | `/test/{session_id}/answer` | 提交答案 |
| GET | `/test/{session_id}/result` | 获取估算结果 |
| POST | `/cat/start` | 开始 CAT 自适应测试 |
| POST | `/cat/{session_id}/answer` | 提交 CAT 答案 |
| POST | `/text/analyze` | 文本分析反向估算 |
| GET | `/batch/estimate/default` | 四类学习者批量估算 |

## 项目结构

```
backend/
├── main.py          # FastAPI 入口
├── config.py        # 算法参数与词汇层级配置
├── database.py      # SQLite 连接
├── schemas.py       # Pydantic 数据模型
├── routers/         # test / batch / text / cat 四个路由模块
├── services/        # 抽样、估算、会话缓存
└── scripts/         # 词表初始化脚本
```
