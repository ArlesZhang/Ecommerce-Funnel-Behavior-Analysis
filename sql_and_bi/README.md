# sql_and_bi — SQL 实战 + 交互式看板

> 本模块是 `notebooks/01-04` 全部分析结论的**纯 SQL 复刻**与**BI 可视化呈现**，
> 与主分析共用同一套口径与同一批数字，不引入任何新的统计口径。
> 主分析叙事请看根目录 `README.md` 与 `notebooks/`，本模块回答的是：
> **"同样的结论，能不能用纯 SQL 从零写出来？能不能放进一张可交互的看板？"**

## 目录结构

```
sql_and_bi/
├── README.md                          # 本文件
├── sql_work/                          # 纯 SQL 复刻（DuckDB 直读 CSV，无需入库）
│   ├── 01_business_overview.sql       # 业务理解：10 段查询
│   ├── 02_funnel_analysis.sql         # 订单漏斗：4 段查询
│   ├── 03_rfm_segmentation.sql        # RFM 分层：5 段查询
│   ├── 04_retention_cohort.sql        # 留存/复购：7 段查询
│   └── sql_workbook.ipynb             # 逐段执行全部 .sql + 对账锚点（已含运行输出）
└── BI_DashBoards/
    ├── build_dashboard.py             # 看板生成脚本（DuckDB 查询 → Plotly → 单文件 HTML）
    └── olist_strategy_dashboard.html  # 生成产物：离线可用的交互式看板（5 MB）
```

## sql_work：每个分析阶段的纯 SQL 实现

每个 `.sql` 文件内部以 `-- QUERY:` 注释分段，每段独立自洽、可单独执行；
文件头部写明了对应 notebook、口径说明与本段用到的 SQL 技术。

| SQL 文件 | 对应 notebook | 核心 SQL 技术点 |
|---|---|---|
| `01_business_overview.sql` | `01_business_understanding` | 聚合窗口函数 `SUM(COUNT(*)) OVER ()` 一次算占比；3 表 JOIN（明细 ⋈ 商品 ⋈ 品类翻译）；`GROUP BY ... HAVING` 筛复购用户；标量子查询拼 KPI 行 |
| `02_funnel_analysis.sql` | `02_funnel_analysis` | 多层 CTE；`FIRST_VALUE()` 算整体转化率、`LAG()` 算环节转化率；`PERCENTILE_CONT() WITHIN GROUP` 算平均/中位/P95 耗时；按州拆分漏斗（JOIN + HAVING 过滤小样本） |
| `03_rfm_segmentation.sql` | `03_rfm_analysis` | 8 层 CTE 链；`QUANTILE_CONT` 分位切点 + `CASE WHEN` 链实现分箱打分，**完整等价复现 pandas `qcut(duplicates='drop')` 语义**（F 维度切点退化时自动并箱）；`MEDIAN()` + `CROSS JOIN` 阈值分群；`SUM(SUM(monetary)) OVER ()` 算 GMV 占比 |
| `04_retention_cohort.sql` | `04_retention_analysis` | `MIN()` 定首购月 + `DATEDIFF('month')` 算 cohort 偏移；`FIRST_VALUE() OVER (PARTITION BY cohort)` 定留存基准；`PIVOT ... ON ... IN` 透视留存矩阵；`ROW_NUMBER() OVER (PARTITION BY user)` 定位首单/第二单算复购间隔；5 表 JOIN 算品类复购率 |

**口径（与 notebooks 完全一致）**：
- 用户身份一律用 `customer_unique_id`（`customer_id` 是订单级身份）
- GMV / RFM / 留存 / 复购口径 = 仅 `order_status = 'delivered'`
- RFM 参考日期 = 数据集中最后购买日 + 1 天
- Cohort 矩阵仅保留首月用户数 ≥ 50 的月份

**怎么跑**：

```bash
uv sync && source .venv/bin/activate
jupyter lab sql_and_bi/sql_work/sql_workbook.ipynb   # 全量执行，逐段打印结果
```

workbook 的 markdown 单元格里列出了每个阶段的**对账锚点**（如订单 99,441 笔、
送达 97.02%、复购 2,801 人、Champions 贡献 53.04% GMV），执行输出与之逐项一致。
若只想跑单段查询，把 `-- QUERY:` 分段内的 SQL 粘进任意 DuckDB 客户端即可
（如 `duckdb` CLI：`duckdb -c "$(cat 02_funnel_analysis.sql)"`，注意相对路径要在本目录下执行）。

## BI_DashBoards：交互式策略看板

`olist_strategy_dashboard.html` 把四个阶段的核心产出整合为一张看板：
顶部 6 个 KPI 卡片（订单数、用户数、GMV、客单价、复购率、关键分群占比），
下方 12 张交互图 + 3 段业务解读（洞察框内所有数字均由 DuckDB 实时查询插值，
不硬编码任何业务数字）：

1. **业务概览**：月度订单趋势、订单状态分布、品类 Top 15（可按订单数/销售额切换排序）、用户地理分布
2. **漏斗**：下单→审批→揽收→送达转化漏斗、各阶段耗时（平均/中位/P95）、按州送达率
3. **用户**：RFM 分群人数占比 vs GMV 占比、分群运营策略表
4. **留存**：Cohort 留存热力图、平均留存曲线、复购时间窗口（柱线双轴）、品类复购率

**怎么跑**：

```bash
# 直接用浏览器打开生成好的看板（无需服务器、无需网络，plotly.js 已内联）：
xdg-open sql_and_bi/BI_DashBoards/olist_strategy_dashboard.html   # 或双击打开

# 数据更新后重新生成：
source .venv/bin/activate
python sql_and_bi/BI_DashBoards/build_dashboard.py
```

看板中所有数字来自 `build_dashboard.py` 内的 DuckDB 查询（与 `sql_work` 同一口径），
修改查询即可联动更新全部卡片、图表与洞察文案。

## 对账说明

本模块全部数字已与 `notebooks/01-04` 的运行输出逐项核对（22 个锚点全过）：
漏斗四阶段 99,441 → 99,281 → 97,658 → 96,476（整体送达 97.02%）、
RFM 四群人数与 GMV 占比（Champions 33,316 人 / 53.04% GMV）、
复购 2,801 人（3.0%）、复购窗口 0-7 天 1,028 人（36.7%）等。
用户级打分（93,358 人的 R/F/M 得分）做过全量比对，与 pandas 实现 0 不一致。

## 可替换的实现思路

BI 看板：当前是 Plotly 单文件。若要可筛选/联动更强，可换 Dash（Plotly 官方框架，支持回调）或 Streamlit（代码更少、适合快速原型）；追求零代码可导出到 Metabase/Tableau。
SQL 执行：当前用 DuckDB 直读 CSV。若数据量大或需复用，可先 CREATE TABLE ... AS 落成 .duckdb 库文件再查。