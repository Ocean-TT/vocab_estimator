# 改进计划文档

本文档对照课程具体要求，说明当前项目骨架的不足、改进思路、推荐技术选型及实施优先级，供团队分工与报告撰写参考。

---

## 1. 文档目的

当前仓库（`vocab-estimator`）已实现：

- Web 答题界面（认识 / 不确定 / 不认识）
- 基于词频分层的固定抽样测试
- 单算法词汇量点估计 + 90% 置信区间
- 四类学习者**模拟**批量估算（预设认识率，非真实语料输入）
- SQLite 词表存储与基础 REST API

上述能力可用于**演示主流程**，但尚未完全满足课程对「数据采集、多算法、批量后端、验证对比、学生实测与统计分析」的要求。本文档列出差距与改进路径。

---

## 2. 课程要求与现状对照

| 课程要求 | 当前骨架 | 差距等级 |
|----------|----------|----------|
| 采集词汇表等辅助数据 | 600 条演示词 + 小 CSV | **高** |
| 设计一种或多种估算算法 | 仅分层比例估计 1 种 | **高** |
| 基于所给文本估算不同类别学生词汇量 | 未实现 | **高** |
| 设计验证估算准确性的方法 | 未实现 | **高** |
| 与 testyourvocab.com 等行业产品对比 | 未实现 | **高** |
| LLM / 在线 API 辅助验证（不作核心算法） | 未实现 | **中** |
| Web / 桌面 / 移动端界面 | Web 基础版已有 | **低** |
| 后端批量：单词+认识/不认识 → 词汇量 | 仅有模拟四类学习者 | **高** |
| 不同学生实测 3–5 次并上报 | 未实现 | **高** |
| 记录姓名、四六级成绩 | 未实现 | **高** |
| 分析四六级与估算词汇量的相关性 | 未实现 | **高** |

**结论**：优先补齐 **P0（必须）**，再完成 **P1（验证对比）**，最后做 **P2（体验与加分项）**。

---

## 3. 当前架构与已知缺陷

### 3.1 已有模块

```text
frontend/          → 静态 Web 页面，fetch 调用 API
backend/routers/   → test.py（交互测试）、batch.py（模拟批量）
backend/services/  → sampler.py（抽样）、estimator.py（估算）
backend/models/    → Word、TestSession、TestAnswer
data/              → sample_words.csv（演示词表）
```

### 3.2 技术债务（改进前需知晓）

| 问题 | 位置 | 影响 |
|------|------|------|
| 抽样非随机 | `sampler.py` 使用 `order_by(Word.id).limit()` | 每次测试题目固定，不符合统计学「随机样本」假设 |
| 「不确定」未参与估算 | `estimator.py` 只统计 `know` | 丢失信息，估计偏差 |
| 会话题目存内存 | `test_store.py` | 服务重启后会话丢失 |
| 批量接口为模拟 | `batch.py` 用预设认识率 | 不符合「单词列表输入」的作业要求 |
| 词表规模过小 | `seed_words.py` / CSV | 分层覆盖不完整，估算代表性不足 |
| 注释写 Wilson 区间，实现为正态近似 | `estimator.py` | 小样本时区间不准，报告易被质疑 |

---

## 4. 改进项清单（按优先级）

### P0 — 必须完成（否则难以通过作业验收）

---

#### 4.1 真实词表与数据采集

**改进点**

- 替换演示词表为 **COCA / BNC / 综合词频表**（建议 20,000+ 词）
- 可选：标注 CET-4、CET-6、雅思、GRE 等标签，便于分层解释与验证
- 支持词表版本号，报告可说明数据来源与导入时间

**思路**

1. 下载公开词频资源（COCA 5000/20000、BNC 等）
2. 用脚本清洗：去重、小写、rank 排序、分层映射（复用 `config.py` 的 `LEVEL_RANGES`）
3. 批量写入 SQLite `words` 表
4. 对无法匹配的词（批量 API 输入）记录为 `unknown_word`，估算时跳过或单独统计

**推荐技术**

| 用途 | 技术 |
|------|------|
| 数据清洗 | `pandas` |
| 入库 | SQLAlchemy + 现有 `Word` 模型 |
| 脚本 | `backend/scripts/import_coca.py`（新建） |
| 存储 | SQLite（课程规模足够） |

**涉及文件**

- 新建 `data/coca_20000.csv`
- 新建 `backend/scripts/import_coca.py`
- 修改 `backend/models/entities.py`（可选字段：`tags`, `source`）

---

#### 4.2 批量估算 API（作业明确要求的后端示例）

**改进点**

作业要求后端支持如下输入：

> 单词 A，认识；单词 B，不认识；单词 C，不认识…… → 输出估算词汇量

当前 `/api/batch/estimate/default` 仅为**预设概率模拟**，需新增真实批量接口。

**思路**

1. 定义请求体：`[{ "word": "apple", "known": true }, ...]`
2. 对每个词查词表得 `rank` / `level`
3. 按层级聚合认识率，调用与交互测试**同一套** `estimator` 逻辑
4. 返回点估计、区间、置信度、未匹配词列表

**推荐 API 设计**

```http
POST /api/batch/estimate-from-answers
Content-Type: application/json

{
  "answers": [
    { "word": "the", "known": true },
    { "word": "ambiguous", "known": false }
  ],
  "algorithm": "stratified"   // 可选，便于后续多算法
}
```

**推荐技术**

- Pydantic 模型：`BatchWordAnswer`, `BatchEstimateFromAnswersRequest`
- 服务层：重构 `estimator.py`，抽取 `estimate_from_level_responses(level → [bool])`，供 session 与 batch 共用
- 词形：初期 exact match；可选 `nltk.stem` / 小写规范化

**涉及文件**

- 修改 `backend/services/estimator.py`
- 修改 `backend/schemas.py`
- 修改 `backend/routers/batch.py`
- 新建 `backend/services/word_lookup.py`

---

#### 4.3 学生实测与报告模块（小组必做）

**改进点**

- 记录学生 **姓名、CET-4、CET-6**
- 同一学生完成 **3–5 次**测试
- 导出测试记录，做 **四六级分数 vs 估算词汇量** 的相关分析

**思路**

1. 新增数据表：
   - `students`：`id`, `name`, `cet4_score`, `cet6_score`, `created_at`
   - 扩展 `test_sessions`：增加 `student_id`, `algorithm`, `point_estimate` 等冗余字段便于查询
2. 前端流程：登记信息 → 开始测试 → 自动关联 `student_id`
3. 测试完成后写入结果；同一学生可多次测试
4. 统计接口：
   - 每名学生多次测试的均值 / 标准差
   - Pearson / Spearman 相关系数（CET-4 vs 词汇量、CET-6 vs 词汇量）
5. 导出 CSV + 散点图（写入报告）

**推荐技术**

| 用途 | 技术 |
|------|------|
| ORM | SQLAlchemy 新模型 `Student` |
| 统计 | `scipy.stats.pearsonr`, `spearmanr` |
| 数据处理 | `pandas` |
| 可视化 | `matplotlib` / `plotly`；前端 `Chart.js` |
| API | `GET /api/report/correlation`, `GET /api/students/{id}/history` |

**涉及文件**

- 修改 `backend/models/entities.py`
- 新建 `backend/routers/students.py`, `backend/routers/report.py`
- 新建 `backend/services/statistics.py`
- 修改 `frontend/` 增加登记页、历史页、图表页

---

#### 4.4 第二种估算算法（满足「一种或多种」）

**改进点**

目前只有**算法 A：分层固定抽样 + 比例估计**。至少再实现一种，并在报告中对比精度、题量、稳定性。

**思路概览**

| 算法 | 核心思想 | 优点 | 实现难度 |
|------|----------|------|----------|
| **A. 分层比例估计**（已有） | 各层认识率 × 层内词数 | 简单可解释 | 低 |
| **B. IRT 自适应测试（CAT）** | 用能力 θ 选题，收敛后映射词汇量 | 题少、精度高 | 中 |
| **C. 贝叶斯分层估计** | 每层 Beta 后验，汇总后验区间 | 小样本区间更合理 | 中 |

**推荐**：保留 A 作为基线，**优先实现 B（CAT）** 作为对比算法；C 可作为加分。

**涉及文件**

- 新建 `backend/services/estimator_cat.py`
- 新建 `backend/services/estimator_bayes.py`（可选）
- 修改 `backend/routers/test.py` 支持 `algorithm` 参数
- 新建 `docs/ALGORITHMS.md`（算法说明，可写入最终报告）

---

### P1 — 验证与对比（作业明确要求）

---

#### 4.5 准确性验证方案

**改进点**

需在设计报告/代码中回答：**如何证明估算结果是可信的？**

**思路（可组合使用）**

| 方法 | 做法 | 输出指标 |
|------|------|----------|
| 交叉验证 | 将答题样本拆为估计集 / 验证集 | MAE、RMSE |
| 留层验证 | 去掉某一层数据，观察总估计变化 | 稳定性 |
| 锚点对比 | 与 CET-4（~4500）、CET-6（~5500）词表规模对照 | 偏差说明 |
| 人工金标准 | 随机 100 词人工标注 vs 系统推断 | Precision / Recall |

**推荐技术**

- `sklearn.metrics.mean_absolute_error`
- 新建 `backend/services/validation.py`
- 新建 `backend/scripts/run_validation.py`
- Jupyter Notebook：`notebooks/validation_report.ipynb`

---

#### 4.6 与 testyourvocab.com 对比

**改进点**

课程建议以 <http://testyourvocab.com/> 为主要对标产品，可用浏览器自动化抓取结果做对比。

**思路**

1. **禁止**把爬虫或 LLM 当作核心估算逻辑
2. 准备若干组固定模拟答题（或真人测一次）
3. 用 Playwright 在 testyourvocab 完成同样答题流程，记录对方结果
4. 与本系统同输入下的结果对比：MAE、相关系数、散点图
5. 报告中分析差异原因（词表来源、分层方式、算法不同）

**推荐技术**

| 用途 | 技术 |
|------|------|
| 浏览器自动化 | `playwright`（Python） |
| 结果存储 | `benchmark_results` 表或 CSV |
| 脚本 | `backend/scripts/benchmark_testyourvocab.py` |

**注意**

- 遵守目标网站使用条款，控制请求频率
- 百词斩、扇贝等难以批量验证，可在报告中**文字对比**即可

---

#### 4.7 LLM 辅助验证（不能作为核心算法）

**改进点**

可使用大模型 Prompt 或在线 API 对结果做**辅助校验**，但必须在报告中声明：**LLM 仅用于验证，不参与核心估算**。

**思路**

1. 输入：估算词汇量、各层认识率、学生四六级、抽样词列表
2. Prompt 示例：「根据以下认识率分布，该估算值是否与四级水平一致？请指出不合理之处。」
3. 输出：定性评语 + 一致性评分（人工阅读写入报告）
4. 可选：与 testyourvocab 结果一并交给 LLM 做三方对比摘要

**推荐技术**

- OpenAI API / 通义 / DeepSeek 等
- 新建 `backend/services/llm_validator.py`
- 环境变量存 API Key：`.env`（勿提交 git）

---

### P2 — 功能完善与加分项

---

#### 4.8 基于文本的词汇量 / 难度估算

**改进点**

满足「**基于所给文本**，估算不同类别学生的词汇量水平」。

**思路**

1. 输入：英文文章或词表文件
2. 分词 → 与词库匹配 → 统计各频率层覆盖率
3. 输出两种解读（报告中需明确语义）：
   - **文本词汇量**：该文本含多少不同难词（type-token 层面的「文本难度」）
   - **读懂文本所需词汇量**：覆盖率达 95% 对应的 rank 阈值
4. 对不同「学生类型」：用其认识率模型模拟能读懂的比例

**推荐技术**

- 分词：`nltk`, `spaCy`, 或简单正则 `\b[a-z]+\b`
- API：`POST /api/text/estimate`
- 服务：`backend/services/text_analyzer.py`

---

#### 4.9 抽样与会话持久化

**改进点**

- 真随机抽样
- 会话题目与进度持久化

**思路**

- SQLite：`ORDER BY RANDOM() LIMIT n`，或 Python `random.sample`
- 新建表 `session_questions(session_id, word_id, question_order)`
- 去掉 `test_store.py` 内存字典；或生产环境用 Redis

**推荐技术**

- SQLAlchemy 新模型
- 可选：`redis` + `aioredis`

---

#### 4.10 前端与报告导出

**改进点**

- 学生登记、测试历史、相关分析图表
- 一键导出 CSV / PDF 供报告使用

**推荐技术**

- 图表：`Chart.js` 或 `ECharts`
- PDF：`reportlab` 或浏览器打印
- 页面：在现有 `frontend/` 上扩展多页，或引入 Vue 3（按需）

---

## 5. 算法设计详解

### 5.1 算法 A：分层比例估计（当前实现，需增强）

**流程**

```text
词表按 rank 分为 L1…L5
    → 每层抽取 n 题（建议随机）
    → 认识率 p = know_count / n
    → 该层掌握词数 ≈ (rank_end - rank_start + 1) × p
    → 总词汇量 V = Σ 各层掌握词数
    → 置信区间：基于二项分布方差聚合
```

**待改进**

1. **「不确定」处理**（三选一，报告需说明）：
   - 方案 1：计 0.5 题认识
   - 方案 2：单独参数 λ，做敏感性分析
   - 方案 3：仅统计 know / (know + unknown)，忽略 unsure
2. **置信区间**：改用 **Wilson 区间** 或 **Beta 后验区间**，替代简单正态近似
3. **Wilson 公式（每层）**：

   ```text
   p̂ = (know + z²/2) / (n + z²)
   margin = z × sqrt(p̂(1-p̂)/n + z²/(4n²))
   ```

4. 总区间：各层区间相加（独立假设）或 Monte Carlo 聚合

**技术**：`numpy`, `scipy.stats.beta`

---

### 5.2 算法 B：IRT 计算机自适应测试（推荐新增）

**动机**

固定 50 题效率低；testyourvocab 类网站通常采用自适应选题。IRT（Item Response Theory）是心理测量经典方法。

**模型（2PL）**

```text
P(认识 | θ, a, b) = 1 / (1 + exp(-a(θ - b)))
```

- `θ`：用户语言能力（ latent trait ）
- `b`：单词难度（由 rank 映射，如 b = log(rank)）
- `a`：区分度（可设为常数 1.0）

**流程**

```text
初始化 θ = 0
循环直到标准误 SE(θ) < 阈值 或 达到最大题数:
    选择对当前 θ 信息量最大的单词
    用户答题 → 更新 θ（MLE 或 EAP）
将 θ 映射为词汇量 V = f(θ)
```

**θ → 词汇量映射示例**

```text
V = V_max / (1 + exp(-k(θ - θ₀)))
```

参数 `V_max`, `k`, `θ₀` 用历史实测数据或 CET 锚点拟合。

**技术**

- `numpy` 牛顿法求 MLE
- 可选库：`girth`（IRT 拟合）
- 新建 `backend/services/estimator_cat.py`
- 选题：Fisher Information 最大

---

### 5.3 算法 C：贝叶斯分层估计（可选加分）

**思路**

每层认识率 `p_l ~ Beta(α, β)`，观测到 `know` 与 `unknown` 后更新后验；总词汇量 `V = Σ N_l × p_l` 的后验区间用 Monte Carlo 抽样估计。

**优点**

- 小样本下区间比正态近似更稳
- 可融入先验（如「四级生 L3 认识率先验均值 0.5」）

**技术**

- `numpy.random.beta` 做 MCMC 或直接 Beta 抽样
- 可选：`PyMC`（报告需控制篇幅）

---

### 5.4 文本覆盖率算法（对应文本输入要求）

**思路**

```text
文本 T → 词集合 W_T
对每个 w ∈ W_T，查 rank(w)
统计：rank ≤ R 的覆盖率 C(R)
找到最小 R* 使 C(R*) ≥ 0.95 → 对应词汇量约 R*
```

对不同学生：用其各层认识率，估算阅读 T 时「预期认识比例」。

---

## 6. 验证体系总览

```text
                    ┌─────────────────┐
                    │  本系统估算结果  │
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
  │ 内部统计验证  │   │ 外部产品对比  │   │ LLM 辅助评审  │
  │ CV / 留层    │   │ testyourvocab │   │ 定性一致性    │
  └──────────────┘   └──────────────┘   └──────────────┘
         │                   │                   │
         └───────────────────┼───────────────────┘
                             ▼
                    ┌─────────────────┐
                    │ 学生实测 + 四六级 │
                    │ Pearson/Spearman │
                    └─────────────────┘
```

**报告建议呈现**

- 表格：本系统 vs testyourvocab vs CET 锚点
- 散点图：CET-4 分数 vs 估算词汇量（含相关系数 p 值）
- 文字：LLM 校验样例 2–3 条（不作核心依据）

---

## 7. 推荐技术栈汇总

| 层次 | 现有 | 建议新增 |
|------|------|----------|
| 后端框架 | FastAPI | 不变 |
| 数据库 | SQLite | 不变；数据量大时可迁 PostgreSQL |
| 词表处理 | CSV | `pandas` |
| 数值 / 统计 | 手写公式 | `numpy`, `scipy`, `pandas` |
| IRT | 无 | `numpy` 自实现 或 `girth` |
| 验证 | 无 | `sklearn.metrics`, `playwright` |
| LLM 验证 | 无 | OpenAI SDK / 国内大模型 API |
| 分词 | 无 | `nltk` / 正则 |
| 可视化 | 无 | `matplotlib`, `Chart.js` |
| 测试 | 无 | `pytest`, FastAPI `TestClient` |
| 报告 | 无 | Jupyter Notebook |

**建议 `requirements-dev.txt` 片段**

```text
pandas>=2.0
numpy>=1.24
scipy>=1.11
scikit-learn>=1.3
playwright>=1.40
matplotlib>=3.8
python-dotenv>=1.0
pytest>=7.4
httpx>=0.27
```

---

## 8. 实施路线图

| 阶段 | 任务 | 优先级 | 预估工时 |
|------|------|--------|----------|
| 1 | 导入 COCA 词表 + 真随机抽样 | P0 | 1–2 天 |
| 2 | 重构 estimator + `estimate-from-answers` API | P0 | 1 天 |
| 3 | Student 模型 + 3–5 次测试 + 相关分析 | P0 | 2 天 |
| 4 | Wilson 区间 + unsure 策略 | P0 | 0.5 天 |
| 5 | IRT 自适应算法 B | P0/P1 | 2–3 天 |
| 6 | 内部验证脚本 + 图表 | P1 | 1 天 |
| 7 | testyourvocab Playwright 对比 | P1 | 1–2 天 |
| 8 | LLM 辅助验证接口 | P1 | 0.5–1 天 |
| 9 | 文本估算 API | P2 | 1 天 |
| 10 | 前端历史 / 报告 / 导出 | P2 | 1–2 天 |

---

## 9. 建议目录结构（改进后）

```text
vocab-estimator/
├── backend/
│   ├── routers/
│   │   ├── test.py
│   │   ├── batch.py          # + estimate-from-answers
│   │   ├── students.py       # 新建
│   │   ├── report.py         # 新建
│   │   └── text.py           # 新建（可选）
│   ├── services/
│   │   ├── estimator.py      # 增强
│   │   ├── estimator_cat.py  # 新建
│   │   ├── word_lookup.py    # 新建
│   │   ├── statistics.py     # 新建
│   │   ├── validation.py     # 新建
│   │   ├── llm_validator.py  # 新建
│   │   └── text_analyzer.py  # 新建
│   └── scripts/
│       ├── import_coca.py
│       ├── run_validation.py
│       └── benchmark_testyourvocab.py
├── docs/
│   ├── IMPROVEMENTS.md       # 本文档
│   └── ALGORITHMS.md         # 算法专章（可选）
├── notebooks/
│   └── validation_report.ipynb
└── data/
    ├── sample_words.csv
    └── coca_20000.csv
```

---

## 10. 团队分工建议（与改进项对应）

| 成员角色 | 主要负责改进项 | 产出物 |
|----------|----------------|--------|
| 架构 / 后端 | 4.2 批量 API、4.9 持久化 | API 文档、接口实现 |
| 算法 | 4.4 多算法、第 5 章算法说明 | `ALGORITHMS.md`、对比实验 |
| 数据 | 4.1 词表导入 | COCA 词表、导入脚本 |
| 验证 | 4.5–4.7 | 验证报告、benchmark 数据 |
| 前端 | 4.3 学生实测 UI、4.10 图表 | 页面、导出功能 |
| 测试 / 报告 | 4.3 实测组织、相关性分析 | 实测表格、散点图、最终报告 |

---

## 11. 验收自检清单

完成改进后，可按下列项自检是否满足课程要求：

- [ ] 使用真实词频表（非仅演示数据）
- [ ] 至少 **2 种**估算算法，并有对比说明
- [ ] 提供 **单词+认识/不认识** 的批量后端接口
- [ ] 支持 **基于文本** 的分析（至少一种指标）
- [ ] 有 **准确性验证** 方案与实验数据
- [ ] 与 **testyourvocab.com** 有对比结果
- [ ] 有 **LLM 辅助验证**（且明确非核心算法）
- [ ] 收集 **≥3 名学生**，每人 **3–5 次**测试
- [ ] 记录 **四六级成绩** 并完成 **相关性分析**
- [ ] 有完整设计报告 + 工作量分配表（100%）

---

## 12. 参考资源

- COCA 词频：<https://www.wordfrequency.info/>
- testyourvocab：<http://testyourvocab.com/>
- IRT / CAT 概述：Baker & Kim, *The Basics of Item Response Theory*
- Wilson 区间：Brown et al., interval estimation for binomial proportion
- 四六级词汇量锚点：CET-4 ~4500 词，CET-6 ~5500 词（报告引用需注明来源）

---

*文档版本：v1.0 | 对应项目骨架 commit 初始版 | 如有任务变更请同步更新本节与第 8 章路线图。*
