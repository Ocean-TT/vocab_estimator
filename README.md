# 英语词汇量估算工具

基于 **FastAPI + SQLite + 原生 Web 前端** 的课程项目骨架，实现了分层抽样测试、词汇量区间估算，以及四类学习者批量估算示例。

## 功能概览

- Web 界面答题：认识 / 不确定 / 不认识
- 分层抽样算法：按词频层级抽样并估算总词汇量
- 区间 + 置信度：输出 90% 置信区间
- 批量估算：初学者 / 四级 / 六级雅思 / 高级 GRE 四类示例
- 可扩展词表：支持 CSV 导入或脚本自动生成演示词表

## 项目结构

```text
vocab-estimator/
├── backend/
│   ├── main.py              # FastAPI 入口
│   ├── config.py            # 分层与算法参数
│   ├── database.py          # SQLite 连接
│   ├── schemas.py           # API 数据模型
│   ├── models/              # 数据库实体
│   ├── routers/             # test / batch 路由
│   ├── services/            # 抽样、估算、会话缓存
│   └── scripts/seed_words.py
├── frontend/
│   ├── index.html
│   ├── css/style.css
│   └── js/app.js
├── data/sample_words.csv
└── requirements.txt
```

## 快速启动

### 1. 创建虚拟环境并安装依赖

```powershell
cd C:\Users\tanghaiyang\vocab-estimator
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. 导入词表

```powershell
python backend\scripts\seed_words.py
```

### 3. 启动服务

```powershell
uvicorn backend.main:app --reload
```

浏览器访问：<http://127.0.0.1:8000>

API 文档：<http://127.0.0.1:8000/docs>

## 主要 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/test/start` | 开始测试 |
| POST | `/api/test/{session_id}/answer` | 提交答案 |
| GET | `/api/test/{session_id}/result` | 获取估算结果 |
| GET | `/api/batch/estimate/default` | 四类学习者批量估算 |

## 后续可扩展

1. 替换 `data/sample_words.csv` 为 COCA / BNC 完整词频表
2. 将 `test_store.py` 的内存缓存改为 Redis 或数据库
3. 增加自适应测试（CAT）
4. 增加用户登录、历史记录、导出报告
5. 完善设计文档、测试用例和四类语料实测结果

## 团队分工建议

| 模块 | 建议负责人 |
|------|------------|
| 总体架构 | 1 人 |
| 算法与验证 | 1–2 人 |
| 前端 UI | 1–2 人 |
| 数据库与词表 | 1 人 |
| 测试与批量脚本 | 1 人 |
| 报告撰写 | 1 人 |
