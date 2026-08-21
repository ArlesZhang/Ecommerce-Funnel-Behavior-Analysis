# CLAUDE.md — Olist 电商全链路策略分析项目

## 项目定位

这是一个面向 **策略运营数据分析师** 能力建设的实战型作品集项目，不是单纯的技术练习，也不追求复杂模型或工程化。

基于真实 Olist 巴西电商数据集，完成完整链路：

> 业务理解 → 数据理解 → 数据分析 → 指标体系 → 用户分析 → 留存/复购 → 洞察 → 策略建议

核心原则：**目标明确、边界明确、路线明确、产出明确，但实现方式保持开放。**

最终产出要能支撑：学习方法论、训练 SQL/Python/Pandas、训练业务分析与策略判断、构建专业作品集、展示策略分析能力。

## 三层目标

1. **项目目标**：从业务问题出发，经过数据处理与分析，形成有业务价值的策略结论。
2. **能力目标**：
   - 数据分析闭环：业务问题 → 数据 → 指标 → 分析 → 洞察 → 策略
   - 技术能力：在真实业务场景中使用 SQL / DuckDB / Python / Pandas / 可视化
   - 策略分析：不只回答"发生了什么"，还要回答 ——
     - "为什么值得关注？"
     - "应该优先解决什么？"
     - "可以采取什么策略？"
     - "如何验证策略是否有效？"
3. **可迁移目标**：把分析框架、指标思维、SQL Pattern、Pandas Pattern、用户分析 / 留存分析 / 策略分析方法提炼成通用能力，可迁移到电商、物流、游戏、用户增长、营销、运营策略等业务。

## 学习模式与协作规则（重要）

本项目采用 **以战养战、以战促学、AI 辅助执行、人工逆向掌握** 的模式，不是"先学完再做"。

学习闭环：

```text
AI 辅助快速跑通 → 理解整体结构 → 逆向拆解核心分析 → 建立知识框架
→ 人工重新 Coding → 改变实现方式 → 举一反三 → 提炼可复用能力 → 迁移到新业务
```

Claude 必须根据用户所处阶段切换协作方式：

- **执行/跑通模式**（用户说"帮我实现/跑通这个分析"）：
  产出完整可运行代码，同时必须附上：业务逻辑说明、关键决策的原因、以及至少一种可替换的实现思路（如 SQL 窗口函数版 vs Pandas 版）。
- **逆向/学习模式**（用户说"我自己重写/给我提示/为什么这样写"）：
  只给思路、提示、检查点，**不给完整答案**；用户写完后对比点评、指出差距。
- 不确定用户处于哪种模式时，先问一句再动手。

底线原则：

- 一切以"把业务问题讲清楚"为准，不炫技、不上复杂模型。
- 每个分析必须配 **业务解读（含具体数字）+ 策略建议**，禁止只甩图表或裸数字。
- 数字必须来自真实查询结果，禁止编造。

## 项目结构

```
ecommerce-funnel-behavior-analysis/
├── CLAUDE.md                    # 本文件
├── README.md                    # 最终要写成策略报告风格（不是代码罗列）
├── requirements.txt
├── .venv/                       # 虚拟环境（gitignore，勿提交）
├── data/
│   ├── README.md                # 数据下载说明（kaggle 命令）
│   └── raw/                     # Olist 9 张 CSV（gitignore，只读，禁止修改）
├── notebooks/
│   ├── Olist电商.ipynb           # 草稿 / 总规划本
│   ├── 01_business_understanding.ipynb  # 业务理解 + 数据结构
│   ├── 02_funnel_analysis.ipynb         # 订单转化漏斗（窗口函数实战）
│   ├── 03_rfm_analysis.ipynb            # RFM 用户分层
│   └── 04_retention_analysis.ipynb      # 留存 / 复购 + Cohort
├── docs/                        # 分析报告 md 产出（按需创建）
└── reports/                     # 图表产出（如 cohort_retention_heatmap.png）
```

## 分析路线与产出物

| 阶段 | Notebook | 核心业务问题 | 产出要求 |
|---|---|---|---|
| 1 业务理解 | 01 | 哪些品类销量最高？可能的原因？ | `docs/01_business_understanding.md`：数据关系图 + `customer_id`/`customer_unique_id` 区分说明 |
| 2 漏斗分析 | 02 | 下单→送达转化率多少？哪一步流失最严重？ | SQL 窗口函数版 + Pandas 版双实现；业务解读格式："XX 环节转化率仅 XX%，建议优先优化" |
| 3 RFM 分层 | 03 | 用户如何分群？各群贡献多少 GMV？ | RFM 打分/分群/策略映射；把结果翻译成运营动作（如"冠军用户贡献 XX% GMV，建议重点维护；沉睡冠军金额占比高，建议启动召回"） |
| 4 留存复购 | 04 | 复购率多少？留存曲线什么形状？ | 复购率 + Cohort 留存矩阵 + `reports/cohort_retention_heatmap.png`；给出关键窗口期与触达节奏建议（如第 7/15/25 天触达） |
| 5 整合输出 | — | 从数据到策略的完整叙事 | README 写成策略报告风格 + 整理代码 + GitHub 提交 |

## 数据说明（Olist Brazilian E-Commerce）

- 来源：Kaggle `olistbr/brazilian-ecommerce`；若 `data/raw/` 缺数据，按 `data/README.md` 中的命令下载。
- 规模：约 10 万笔订单，2016-09 ~ 2018-08，巴西市场。
- 9 张表均为 CSV，直接读取，**不得修改**。

表关系与 join key：

| 表 | 关键字段 / join key |
|---|---|
| orders | `order_id`（主键）、`customer_id`、`order_status`、各阶段时间戳（purchase/approved/carrier/customer/estimated） |
| order_items | `order_id` + `order_item_id`、`product_id`、`seller_id`、`price`、`freight_value` |
| order_payments | `order_id` + `payment_sequential`、`payment_type`、`payment_installments`、`payment_value` |
| order_reviews | `order_id`、`review_score`、`review_comment_message` |
| customers | `customer_id`（订单级）→ `customer_unique_id`（用户级）、`customer_zip_code_prefix`、city/state |
| sellers | `seller_id`、`seller_zip_code_prefix`、city/state |
| products | `product_id`、`product_category_name`（葡语）、重量/尺寸 |
| geolocation | `zip_code_prefix` → lat/lng（同一 prefix 多条记录，需先去重/聚合） |
| product_category_name_translation | 品类葡语 → 英文翻译 |

关联路径：`customers →(customer_id)→ orders →(order_id)→ order_items / order_payments / order_reviews`；`order_items →(product_id)→ products`、`→(seller_id)→ sellers`；地理信息经 `zip_code_prefix` 关联 geolocation。

关键数据陷阱：

- **`customer_id` vs `customer_unique_id`**：`customer_id` 是订单级身份（1 订单 1 个），`customer_unique_id` 才是真实用户身份。复购/留存/RFM 必须用 `customer_unique_id`，否则出现"人人只买 1 次"的失真结果。
- `order_status` 取值：created / invoiced / approved / processing / shipped / delivered / canceled / unavailable，另有少量空值。漏斗与 GMV 口径要先定义清楚（如剔除 canceled/unavailable），并在分析中显式说明口径。
- 一个 order 可能对应多条 order_items、多条 payments，聚合前注意粒度。
- 品类名为葡萄牙语，展示前 join `product_category_name_translation`。
- 时间字段是字符串，使用前转 datetime；注意时区/空值（canceled 单常无送达时间）。

## 技术栈与环境

- Python 环境：项目内 `.venv/`，激活 `source .venv/bin/activate`，依赖见 `requirements.txt`。
- 核心工具：
  - **DuckDB**：可直接对 CSV 跑 SQL，无需入库：`duckdb.sql("SELECT ... FROM '../data/raw/xxx.csv'")`
  - **Pandas 3.x**：注意新版 API（如 copy-on-write 默认开启，链式赋值失效等）
  - **Matplotlib / Seaborn / Plotly**：可视化
  - **JupyterLab**：`jupyter lab` 启动
- 工具选择原则：聚合/窗口计算优先 DuckDB SQL，二次加工与展示用 Pandas；以"清晰表达分析逻辑"为准。

## 编码与写作约定

- 语言：交流、notebook markdown、业务解读用 **中文**；代码、变量名、SQL 关键字用 **英文**。
- 每个 notebook 遵循结构：业务问题 → 口径定义 → 实现 → 结果 → 业务解读 → 策略建议。
- 图表：中文标签清晰可读，保存时 `bbox_inches='tight'`，存入 `reports/`。
- Notebook 产出标准：**可以直接用于专业汇报** —— 有具体数字、有逻辑、有明确的优化建议方向。
- 分析中主动回答策略四问：为什么值得关注 → 优先解决什么 → 采取什么策略 → 如何验证效果。

## 禁止事项

- ❌ 修改或提交 `data/raw/` 原始数据
- ❌ 追求模型复杂度或工程化炫技，一切以"把业务问题讲清楚"为准
- ❌ 输出没有业务解读的裸数字 / 裸图表
- ❌ 编造或猜测数字，一切以真实查询为准
