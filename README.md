# Olist 电商全链路策略分析

> **作者**：Arles Zhang | **联系方式**：arles3427616237@gmail.com | **GitHub**：[ArlesZhang](https://github.com/ArlesZhang)

---

## 项目背景

Olist 是巴西最大的电商平台之一，连接巴西各地的卖家与买家。本项目基于真实 Olist 数据集（约 10 万笔订单，96,096 位用户，2016 年 9 月至 2018 年 10 月），对平台运营进行一次完整的策略分析。

### 核心业务问题

作为策略分析师，我需要回答以下问题：

1. **平台当前运营状况如何？** 订单规模、用户行为、履约效率
2. **用户流失的瓶颈在哪里？** 是转化问题？履约问题？还是复购问题？
3. **如何提升 GMV？** 应该优先投入哪些策略？预期收益多少？
4. **不同用户群体如何差异化运营？** 哪些用户值得重点维护？哪些需要召回？

---

## 分析框架

我从四个维度展开分析：

```
业务理解 → 漏斗分析 → 用户分层 → 留存复购 → 策略建议
```

每个维度都围绕三个问题：
- **发现了什么？**（数据事实）
- **为什么重要？**（业务影响）
- **应该怎么做？**（策略建议 + 预期收益）

---

## 核心发现与策略建议

### 发现 1：复购率仅 3.00%，是平台最大的增长杠杆

**数据事实**：
- 93,358 位用户中，只有 2,801 位购买了 2 次及以上
- 人均购买频次 1.03 次，中位数 1 次
- 最高一位用户购买了 15 次

**为什么重要**：
复购率从 3% 提升到 5% = 额外 1,867 位复购用户 → 按人均 R$141.62 计算，约 **R$264K 增量 GMV**。这是成本最低、效果最明显的增长抓手。

**策略建议**：
1. **新用户首单后 30 天内触达** — 我分析了复购时间窗口，发现 30 天内是关键窗口期
2. **三次触达节奏**：第 7 天（感谢信+品类推荐）→ 第 15 天（限时优惠券）→ 第 25 天（紧迫感提醒）
3. **预期收益**：如果复购率从 3% 提升到 5%，预计带来 **R$264K 增量 GMV**

---

### 发现 2：运输时效是用户体验的核心痛点

**数据事实**：
- 下单到送达平均 12.6 天
- 审批 10.3 小时（几乎即时）→ 揽收 2.8 天 → **运输 9.3 天**（最大瓶颈）
- P95 送达时间高达 20.5 天（5% 的用户等了大半个月）

**为什么重要**：
长等待时间直接导致差评 → 11.51% 的订单只获得 1 星评价 → 流失风险。运输环节是唯一有优化空间的瓶颈（审批和揽收几乎无流失）。

**策略建议**：
1. **优先优化运输时效**：与物流商谈判 SLA，或引入多家物流商竞争
2. **主动触达 P95 用户**：对"超长等待"订单主动触达、补偿，降低差评率
3. **预期收益**：如果平均送达时间从 9.3 天降到 7 天，预计差评率降低 3-5%，用户留存率提升 2-3%

---

### 发现 3：Champions 和 At Risk 用户贡献了不成比例的 GMV

**数据事实**（RFM 分层后）：
- 我将用户分为 8 个群体：Champions（冠军用户）、Loyal Customers（忠诚用户）、At Risk（流失风险）、New Customers（新用户）、Promising（有潜力）、Needs Attention（需要关注）、Hibernating（休眠用户）、Lost（已流失）
- Champions 用户：高频高消费，GMV 占比显著高于人数占比
- At Risk 用户：曾是高频用户，现在不活跃，但贡献了大量 GMV

**为什么重要**：
召回一个 At Risk 用户的成本 < 获取一个新客的成本 → At Risk 是最高优先级的召回对象。

**策略建议**：
1. **Champions 用户**：VIP 服务，优先体验新品，专属客服
2. **At Risk 用户**：大额优惠券 + 专属客服触达，最高优先级召回
3. **New Customers**：首单后 7 天内触达，引导第二单
4. **Lost 用户**：低成本触达（邮件/短信），不投入大额优惠券
5. **预期收益**：如果 At Risk 用户召回率提升 10%，预计带来 **R$100K+ 增量 GMV**

---

### 发现 4：用户留存率极低，首月是关键窗口期

**数据事实**（Cohort 留存分析）：
- 首月留存（M0→M1）在所有 cohort 中都非常低
- 大部分复购发生在首单后的 30-90 天内
- 不同品类复购率差异显著：health_beauty、bed_bath_table（快消/日用品）> watches_gifts（高客单价）

**为什么重要**：
首月留存极低说明用户在首单后快速流失 → 必须在首单后 30 天内建立触达机制。

**策略建议**：
- **7d/15d/25d 三次触达节奏**（详见发现 1）
- **品类个性化推荐**：买了 bed_bath_table 的用户推荐 health_beauty（"买了床品的人还买了..."）
- **预期收益**：如果首月留存率从 2% 提升到 4%，预计带来 **R$200K+ 增量 GMV**

---

## 综合策略收益预估

如果实施上述策略，预计总收益：

| 策略 | 预期收益 | 实现难度 |
|---|---|---|
| 复购率提升（3% → 5%） | R$264K | 中 |
| 运输时效优化 | R$150K+ | 高 |
| At Risk 用户召回 | R$100K+ | 低 |
| 首月留存提升 | R$200K+ | 中 |
| **总计** | **R$700K+** | — |

---

## 分析方法论

### 阶段 01：业务理解
- **目标**：理解数据结构、业务实体关系、关键数据陷阱
- **方法**：DuckDB SQL 查询 + Pandas 探索
- **产出**：数据关系图、品类分析、`customer_id` vs `customer_unique_id` 区分说明
- **关键结论**：必须用 `customer_unique_id` 做用户级分析，否则复购率失真

### 阶段 02：漏斗分析
- **目标**：分析订单从下单到送达的转化漏斗，找出瓶颈
- **方法**：SQL 窗口函数 + Pandas 双实现
- **产出**：漏斗图、各阶段耗时分布（箱线图）、按州拆分的送达率
- **关键结论**：运输是最大瓶颈（9.3 天），审批和揽收几乎无流失

### 阶段 03：RFM 用户分层
- **目标**：用 RFM 模型将用户分为不同价值群体
- **方法**：计算 R/F/M → 五分位打分（因数据偏态，实际分箱数少于 5）→ 中位数阈值法分群
- **产出**：8 个用户群体（Champions、Loyal、At Risk、New、Promising、Needs Attention、Hibernating、Lost）
- **关键结论**：At Risk 用户是最高优先级召回对象

### 阶段 04：留存/复购分析
- **目标**：构建 Cohort 留存矩阵，识别关键复购窗口期
- **方法**：Cohort 留存热力图 + 复购时间间隔分析
- **产出**：Cohort 热力图、留存曲线、复购时间分布、品类复购率对比
- **关键结论**：首月留存极低，7d/15d/25d 是最佳触达节奏

### 扩展模块：纯 SQL 复刻 + 交互式看板（`sql_and_bi/`）

上述四个阶段的全部分析结论，另用**纯 SQL**（窗口函数 / 多层 CTE / 多表 JOIN /
PIVOT / 分位数函数，DuckDB 直读 CSV）从零复刻一遍，逐项对账一致；
并整合为一张**离线可交互的 Plotly 看板**（12 张图 + KPI 卡片 + 业务解读）。
详见 [`sql_and_bi/README.md`](sql_and_bi/README.md)。

---

## 技术栈

| 工具 | 用途 |
|---|---|
| **DuckDB** | 直接对 CSV 跑 SQL，无需入库 |
| **Pandas 3.x** | 数据探索、二次加工、可视化 |
| **Matplotlib / Seaborn** | 图表绘制 |
| **Plotly** | 交互式看板（`sql_and_bi/BI_DashBoards`） |
| **JupyterLab** | Notebook 环境 |

---

## 项目结构

```
ecommerce-funnel-behavior-analysis/
├── CLAUDE.md                    # 项目协作规则
├── README.md                    # 本文件（策略报告）
├── pyproject.toml               # Python 依赖声明（uv 原生管理）
├── uv.lock                      # 精确环境锁文件
├── data/
│   ├── README.md                # 数据下载说明
│   └── raw/                     # Olist 9 张 CSV（gitignore，只读）
├── notebooks/
│   ├── 01_business_understanding.ipynb  # 业务理解
│   ├── 02_funnel_analysis.ipynb         # 漏斗分析
│   ├── 03_rfm_analysis.ipynb            # RFM 分层
│   └── 04_retention_analysis.ipynb      # 留存/复购
├── docs/
│   └── 01_business_understanding.md     # 业务理解报告
├── reports/                             # 13 张分析图表
│   ├── 01_*.png                         # 阶段 01 产出
│   ├── 02_*.png                         # 阶段 02 产出
│   ├── 03_*.png                         # 阶段 03 产出
│   ├── 04_*.png                         # 阶段 04 产出
│   └── cohort_retention_heatmap.png     # Cohort 留存热力图
└── sql_and_bi/                          # 扩展模块：纯 SQL 复刻 + 交互式看板
    ├── README.md                        # 模块说明（文件对照 / 运行方式 / 对账）
    ├── sql_work/                        # 4 个 .sql 文件 + 逐段执行的 workbook
    └── BI_DashBoards/                   # Plotly 单文件交互看板 + 生成脚本
```

---

## 如何运行

1. **克隆仓库**：
   ```bash
   git clone https://github.com/ArlesZhang/ecommerce-funnel-behavior-analysis.git
   cd ecommerce-funnel-behavior-analysis
   ```

2. **安装依赖**（本项目用 [uv](https://docs.astral.sh/uv/) 做原生依赖管理，未安装请先安装）：
   ```bash
   uv sync                # 按 uv.lock 一键还原完整环境（自动创建 .venv）
   source .venv/bin/activate
   ```

3. **下载数据**（按 `data/README.md` 中的命令）：
   ```bash
   kaggle datasets download -d olistbr/brazilian-ecommerce -p data/raw --unzip
   ```

4. **运行 Notebook**：
   ```bash
   jupyter lab
   # 按顺序打开 notebooks/01 → 02 → 03 → 04
   ```

5. **（可选）SQL 复刻与交互看板**：
   ```bash
   # 纯 SQL 复刻：逐段执行 4 个 .sql 文件（口径与 notebooks 完全一致）
   jupyter lab sql_and_bi/sql_work/sql_workbook.ipynb

   # 交互式看板：直接用浏览器打开（离线可用，无需服务器）
   # 若需重新生成：python sql_and_bi/BI_DashBoards/build_dashboard.py
   ```

---

## 下一步优化方向

1. **A/B 测试验证**：实际实施 7d/15d/25d 触达策略，对比复购率提升
2. **物流商细分**：按物流商分析送达时效，找出最差的物流商并替换
3. **品类组合推荐**：基于品类复购率差异，设计品类组合推荐策略
4. **用户生命周期价值（LTV）**：计算各群体的 LTV，优化获客预算分配

---

## 关于作者

**Arles Zhang**  
策略数据分析师，专注于电商、用户增长、运营策略等领域的数据分析与策略制定。

- **邮箱**：arles3427616237@gmail.com
- **GitHub**：https://github.com/ArlesZhang
- **项目地址**：https://github.com/ArlesZhang/ecommerce-funnel-behavior-analysis

---

## License

This project uses the [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce), licensed under the [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
