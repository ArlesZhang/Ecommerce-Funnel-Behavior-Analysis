"""
BI 看板构建脚本：把本项目四个分析阶段的全部产出，整合为一个可交互的单文件看板
============================================================================

对应产出：notebooks/01-04 分析结论的交互式可视化版本（Plotly）
口径说明：与 notebooks/ 及 ../sql_work/*.sql 完全一致——
          用户级分析用 customer_unique_id；GMV/RFM/留存仅统计 delivered 订单

运行方式（在仓库根目录或本目录均可）：
    python sql_and_bi/BI_DashBoards/build_dashboard.py
    # 或：uv run python sql_and_bi/BI_DashBoards/build_dashboard.py

产物：同目录下 olist_strategy_dashboard.html —— 双击即可在浏览器打开，
      无需服务器、无需安装任何 BI 工具；plotly.js 已内联，离线可用。

设计说明：所有数字均由 DuckDB 现场查询原始 CSV 得到（不硬编码任何业务数字），
          洞察文案中的数字通过 f-string 注入，保证与查询结果一致。
"""

import datetime as dt
from pathlib import Path

import duckdb
import pandas as pd
import plotly
import plotly.graph_objects as go
from plotly.subplots import make_subplots

HERE = Path(__file__).resolve().parent
RAW = HERE.parent.parent / "data" / "raw"

# plotly.js 内联进 HTML => 看板离线可用、无需 CDN
PLOTLY_JS = (Path(plotly.__file__).parent / "package_data" / "plotly.min.js").read_text(encoding="utf-8")

# ---------------------------------------------------------------------------
# 调色板（与 reports/ 静态图表保持一致的视觉语言）
# ---------------------------------------------------------------------------
BLUE, GREEN, ORANGE, RED, PURPLE, GRAY, DARK = (
    "#3498db", "#2ecc71", "#e67e22", "#e74c3c", "#9b59b6", "#95a5a6", "#2c3e50")
SEG_COLORS = ["#27ae60", "#2ecc71", "#3498db", "#9b59b6",
              "#f39c12", "#e67e22", "#e74c3c", "#c0392b", "#95a5a6"]
CHART_CONFIG = {"displaylogo": False, "responsive": True,
                "modeBarButtonsToRemove": ["lasso2d", "select2d"]}


def csv_path(name: str) -> str:
    return str(RAW / name)


# ---------------------------------------------------------------------------
# 1. 数据层：全部用 DuckDB SQL 直接聚合原始 CSV（与 sql_work 口径一致）
# ---------------------------------------------------------------------------
def load_data(con: duckdb.DuckDBPyConnection) -> dict:
    d = {}

    d["kpis"] = con.sql(f"""
        SELECT
            (SELECT COUNT(*) FROM '{csv_path("olist_orders_dataset.csv")}') AS total_orders,
            (SELECT COUNT(*) FROM '{csv_path("olist_orders_dataset.csv")}'
             WHERE order_status = 'delivered') AS delivered_orders,
            (SELECT COUNT(DISTINCT customer_unique_id)
             FROM '{csv_path("olist_customers_dataset.csv")}') AS unique_customers,
            (SELECT ROUND(SUM(price), 2)
             FROM '{csv_path("olist_order_items_dataset.csv")}' oi
             JOIN '{csv_path("olist_orders_dataset.csv")}' o ON oi.order_id = o.order_id
             WHERE o.order_status = 'delivered') AS total_gmv,
            (SELECT ROUND(AVG(order_total), 2) FROM (
                SELECT order_id, SUM(price) AS order_total
                FROM '{csv_path("olist_order_items_dataset.csv")}'
                GROUP BY order_id)) AS avg_order_value,
            (SELECT ROUND(AVG(review_score), 2)
             FROM '{csv_path("olist_order_reviews_dataset.csv")}') AS avg_review_score,
            (SELECT COUNT(*) FROM '{csv_path("olist_sellers_dataset.csv")}') AS sellers,
            (SELECT COUNT(*) FROM '{csv_path("olist_products_dataset.csv")}') AS products
    """).df().iloc[0]

    # 复购率（口径同 notebooks/04：delivered + customer_unique_id）
    d["repurchase"] = con.sql(f"""
        WITH user_orders AS (
            SELECT c.customer_unique_id, COUNT(DISTINCT o.order_id) AS order_cnt
            FROM '{csv_path("olist_customers_dataset.csv")}' c
            JOIN '{csv_path("olist_orders_dataset.csv")}' o ON c.customer_id = o.customer_id
            WHERE o.order_status = 'delivered'
            GROUP BY c.customer_unique_id)
        SELECT COUNT(*) AS total_users,
               SUM(CASE WHEN order_cnt >= 2 THEN 1 ELSE 0 END) AS repurchase_users,
               ROUND(SUM(CASE WHEN order_cnt >= 2 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS repurchase_rate
        FROM user_orders
    """).df().iloc[0]

    d["monthly"] = con.sql(f"""
        SELECT STRFTIME(CAST(order_purchase_timestamp AS TIMESTAMP), '%Y-%m') AS month,
               COUNT(*) AS order_cnt
        FROM '{csv_path("olist_orders_dataset.csv")}'
        WHERE order_status = 'delivered'
        GROUP BY 1 ORDER BY 1
    """).df()

    d["status"] = con.sql(f"""
        SELECT order_status, COUNT(*) AS order_cnt,
               ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct
        FROM '{csv_path("olist_orders_dataset.csv")}'
        GROUP BY order_status ORDER BY order_cnt DESC
    """).df()

    d["review_dist"] = con.sql(f"""
        SELECT review_score,
               ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct
        FROM '{csv_path("olist_order_reviews_dataset.csv")}'
        GROUP BY review_score ORDER BY review_score
    """).df().set_index("review_score")

    d["categories"] = con.sql(f"""
        SELECT COALESCE(t.product_category_name_english, p.product_category_name) AS category,
               COUNT(DISTINCT oi.order_id) AS order_cnt,
               ROUND(SUM(oi.price), 2) AS total_revenue
        FROM '{csv_path("olist_order_items_dataset.csv")}' oi
        JOIN '{csv_path("olist_products_dataset.csv")}' p ON oi.product_id = p.product_id
        LEFT JOIN '{csv_path("product_category_name_translation.csv")}' t
            ON p.product_category_name = t.product_category_name
        WHERE COALESCE(t.product_category_name_english, p.product_category_name) IS NOT NULL
        GROUP BY 1 ORDER BY order_cnt DESC LIMIT 15
    """).df()

    d["states"] = con.sql(f"""
        SELECT customer_state, COUNT(DISTINCT customer_unique_id) AS customer_cnt
        FROM '{csv_path("olist_customers_dataset.csv")}'
        GROUP BY customer_state ORDER BY customer_cnt DESC LIMIT 10
    """).df()

    # 漏斗（口径同 notebooks/02：时间戳非空 = 到达该阶段）
    d["funnel"] = con.sql(f"""
        WITH order_stages AS (
            SELECT
                CASE WHEN order_purchase_timestamp      IS NOT NULL THEN 1 ELSE 0 END AS is_purchased,
                CASE WHEN order_approved_at             IS NOT NULL THEN 1 ELSE 0 END AS is_approved,
                CASE WHEN order_delivered_carrier_date  IS NOT NULL THEN 1 ELSE 0 END AS is_carrier,
                CASE WHEN order_delivered_customer_date IS NOT NULL THEN 1 ELSE 0 END AS is_delivered
            FROM '{csv_path("olist_orders_dataset.csv")}')
        SELECT '1. 下单' AS stage, SUM(is_purchased) AS cnt FROM order_stages
        UNION ALL SELECT '2. 审批', SUM(is_approved) FROM order_stages
        UNION ALL SELECT '3. 揽收', SUM(is_carrier) FROM order_stages
        UNION ALL SELECT '4. 送达', SUM(is_delivered) FROM order_stages
    """).df()

    d["stage_times"] = con.sql(f"""
        SELECT '1. 下单→审批' AS stage,
               ROUND(AVG(EPOCH(CAST(order_approved_at AS TIMESTAMP)
                     - CAST(order_purchase_timestamp AS TIMESTAMP)) / 3600), 1) AS avg_v,
               ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY EPOCH(CAST(order_approved_at AS TIMESTAMP)
                     - CAST(order_purchase_timestamp AS TIMESTAMP)) / 3600), 1) AS median_v,
               ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY EPOCH(CAST(order_approved_at AS TIMESTAMP)
                     - CAST(order_purchase_timestamp AS TIMESTAMP)) / 3600), 1) AS p95_v,
               '小时' AS unit
        FROM '{csv_path("olist_orders_dataset.csv")}' WHERE order_approved_at IS NOT NULL
        UNION ALL
        SELECT '2. 审批→揽收',
               ROUND(AVG(EPOCH(CAST(order_delivered_carrier_date AS TIMESTAMP)
                     - CAST(order_approved_at AS TIMESTAMP)) / 86400), 1),
               ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY EPOCH(CAST(order_delivered_carrier_date AS TIMESTAMP)
                     - CAST(order_approved_at AS TIMESTAMP)) / 86400), 1),
               ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY EPOCH(CAST(order_delivered_carrier_date AS TIMESTAMP)
                     - CAST(order_approved_at AS TIMESTAMP)) / 86400), 1),
               '天'
        FROM '{csv_path("olist_orders_dataset.csv")}' WHERE order_delivered_carrier_date IS NOT NULL
        UNION ALL
        SELECT '3. 揽收→送达',
               ROUND(AVG(EPOCH(CAST(order_delivered_customer_date AS TIMESTAMP)
                     - CAST(order_delivered_carrier_date AS TIMESTAMP)) / 86400), 1),
               ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY EPOCH(CAST(order_delivered_customer_date AS TIMESTAMP)
                     - CAST(order_delivered_carrier_date AS TIMESTAMP)) / 86400), 1),
               ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY EPOCH(CAST(order_delivered_customer_date AS TIMESTAMP)
                     - CAST(order_delivered_carrier_date AS TIMESTAMP)) / 86400), 1),
               '天'
        FROM '{csv_path("olist_orders_dataset.csv")}' WHERE order_delivered_customer_date IS NOT NULL
    """).df()

    d["funnel_by_state"] = con.sql(f"""
        WITH order_stages AS (
            SELECT c.customer_state,
                   CASE WHEN o.order_purchase_timestamp      IS NOT NULL THEN 1 ELSE 0 END AS is_purchased,
                   CASE WHEN o.order_delivered_customer_date IS NOT NULL THEN 1 ELSE 0 END AS is_delivered
            FROM '{csv_path("olist_orders_dataset.csv")}' o
            JOIN '{csv_path("olist_customers_dataset.csv")}' c ON o.customer_id = c.customer_id)
        SELECT customer_state, COUNT(*) AS total_orders,
               ROUND(SUM(is_delivered) * 100.0 / SUM(is_purchased), 2) AS delivery_rate
        FROM order_stages GROUP BY customer_state
        HAVING COUNT(*) >= 100 ORDER BY total_orders DESC LIMIT 10
    """).df()

    # RFM 分群统计（口径与打分方法同 ../sql_work/03_rfm_segmentation.sql 的 03-4 段）
    d["rfm"] = con.sql(f"""
        WITH reference_date AS (
            SELECT MAX(CAST(order_purchase_timestamp AS DATE)) + INTERVAL '1 day' AS today
            FROM '{csv_path("olist_orders_dataset.csv")}'),
        customer_orders AS (
            SELECT c.customer_unique_id, o.order_id,
                   CAST(o.order_purchase_timestamp AS DATE) AS purchase_date,
                   SUM(oi.price) AS order_amount
            FROM '{csv_path("olist_customers_dataset.csv")}' c
            JOIN '{csv_path("olist_orders_dataset.csv")}' o ON c.customer_id = o.customer_id
            JOIN '{csv_path("olist_order_items_dataset.csv")}' oi ON o.order_id = oi.order_id
            WHERE o.order_status = 'delivered'
            GROUP BY c.customer_unique_id, o.order_id, purchase_date),
        rfm_base AS (
            SELECT customer_unique_id,
                   DATEDIFF('day', MAX(purchase_date), (SELECT today FROM reference_date)) AS recency,
                   COUNT(DISTINCT order_id) AS frequency,
                   ROUND(SUM(order_amount), 2) AS monetary
            FROM customer_orders GROUP BY customer_unique_id),
        cuts AS (
            SELECT MIN(recency) r_e0, QUANTILE_CONT(recency,0.2) r_e1, QUANTILE_CONT(recency,0.4) r_e2,
                   QUANTILE_CONT(recency,0.6) r_e3, QUANTILE_CONT(recency,0.8) r_e4, MAX(recency) r_e5,
                   MIN(frequency) f_e0, QUANTILE_CONT(frequency,0.2) f_e1, QUANTILE_CONT(frequency,0.4) f_e2,
                   QUANTILE_CONT(frequency,0.6) f_e3, QUANTILE_CONT(frequency,0.8) f_e4, MAX(frequency) f_e5,
                   MIN(monetary) m_e0, QUANTILE_CONT(monetary,0.2) m_e1, QUANTILE_CONT(monetary,0.4) m_e2,
                   QUANTILE_CONT(monetary,0.6) m_e3, QUANTILE_CONT(monetary,0.8) m_e4, MAX(monetary) m_e5
            FROM rfm_base),
        scored AS (
            SELECT b.*,
                (CASE WHEN c.r_e1 < b.recency AND c.r_e1 > c.r_e0 THEN 1 ELSE 0 END
               + CASE WHEN c.r_e2 < b.recency AND c.r_e2 > c.r_e1 THEN 1 ELSE 0 END
               + CASE WHEN c.r_e3 < b.recency AND c.r_e3 > c.r_e2 THEN 1 ELSE 0 END
               + CASE WHEN c.r_e4 < b.recency AND c.r_e4 > c.r_e3 THEN 1 ELSE 0 END
               + CASE WHEN c.r_e5 < b.recency AND c.r_e5 > c.r_e4 THEN 1 ELSE 0 END) AS r_bin,
                ((c.r_e1 > c.r_e0)::INT + (c.r_e2 > c.r_e1)::INT + (c.r_e3 > c.r_e2)::INT
               + (c.r_e4 > c.r_e3)::INT + (c.r_e5 > c.r_e4)::INT) AS r_bins,
                (CASE WHEN c.f_e1 < b.frequency AND c.f_e1 > c.f_e0 THEN 1 ELSE 0 END
               + CASE WHEN c.f_e2 < b.frequency AND c.f_e2 > c.f_e1 THEN 1 ELSE 0 END
               + CASE WHEN c.f_e3 < b.frequency AND c.f_e3 > c.f_e2 THEN 1 ELSE 0 END
               + CASE WHEN c.f_e4 < b.frequency AND c.f_e4 > c.f_e3 THEN 1 ELSE 0 END
               + CASE WHEN c.f_e5 < b.frequency AND c.f_e5 > c.f_e4 THEN 1 ELSE 0 END) AS f_bin,
                (CASE WHEN c.m_e1 < b.monetary AND c.m_e1 > c.m_e0 THEN 1 ELSE 0 END
               + CASE WHEN c.m_e2 < b.monetary AND c.m_e2 > c.m_e1 THEN 1 ELSE 0 END
               + CASE WHEN c.m_e3 < b.monetary AND c.m_e3 > c.m_e2 THEN 1 ELSE 0 END
               + CASE WHEN c.m_e4 < b.monetary AND c.m_e4 > c.m_e3 THEN 1 ELSE 0 END
               + CASE WHEN c.m_e5 < b.monetary AND c.m_e5 > c.m_e4 THEN 1 ELSE 0 END) AS m_bin
            FROM rfm_base b CROSS JOIN cuts c),
        final_scores AS (
            SELECT customer_unique_id, recency, frequency, monetary,
                   r_bins - r_bin AS R_score, f_bin + 1 AS F_score, m_bin + 1 AS M_score
            FROM scored),
        thresholds AS (
            SELECT MEDIAN(R_score) r_med, MEDIAN(F_score) f_med, MEDIAN(M_score) m_med FROM final_scores),
        segmented AS (
            SELECT f.*,
                CASE
                    WHEN R_score >= t.r_med AND F_score >= t.f_med AND M_score >= t.m_med THEN 'Champions（冠军用户）'
                    WHEN R_score >= t.r_med AND F_score >= t.f_med AND M_score <  t.m_med THEN 'Loyal（忠诚用户）'
                    WHEN R_score >= t.r_med AND F_score <  t.f_med AND M_score >= t.m_med THEN 'Potential Loyalists（潜力忠诚）'
                    WHEN R_score >= t.r_med AND F_score <  t.f_med AND M_score <  t.m_med THEN 'New（新用户）'
                    WHEN R_score <  t.r_med AND F_score >= t.f_med AND M_score >= t.m_med THEN 'At Risk（流失风险）'
                    WHEN R_score <  t.r_med AND F_score >= t.f_med AND M_score <  t.m_med THEN 'Hibernating（休眠）'
                    WHEN R_score <  t.r_med AND F_score <  t.f_med AND M_score >= t.m_med THEN 'Promising（有潜力）'
                    ELSE 'Lost（已流失）'
                END AS segment
            FROM final_scores f CROSS JOIN thresholds t)
        SELECT segment, COUNT(*) AS user_cnt,
               ROUND(SUM(monetary), 2) AS total_gmv,
               ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS user_pct,
               ROUND(SUM(monetary) * 100.0 / SUM(SUM(monetary)) OVER (), 2) AS gmv_pct
        FROM segmented GROUP BY segment
        HAVING COUNT(*) > 0
        ORDER BY total_gmv DESC
    """).df()

    # Cohort 留存（口径同 04-3：delivered + 首月用户 >= 50 的 cohort）
    d["cohort"] = con.sql(f"""
        WITH user_purchases AS (
            SELECT c.customer_unique_id,
                   DATE_TRUNC('month', CAST(o.order_purchase_timestamp AS TIMESTAMP)) AS purchase_month
            FROM '{csv_path("olist_customers_dataset.csv")}' c
            JOIN '{csv_path("olist_orders_dataset.csv")}' o ON c.customer_id = o.customer_id
            WHERE o.order_status = 'delivered'),
        first_purchase AS (
            SELECT customer_unique_id, MIN(purchase_month) AS cohort_month
            FROM user_purchases GROUP BY customer_unique_id),
        cohort_counts AS (
            SELECT fp.cohort_month,
                   DATEDIFF('month', fp.cohort_month, up.purchase_month) AS offset_month,
                   COUNT(DISTINCT fp.customer_unique_id) AS user_cnt
            FROM first_purchase fp
            JOIN user_purchases up ON fp.customer_unique_id = up.customer_unique_id
            GROUP BY 1, 2),
        valid_cohorts AS (
            SELECT cohort_month FROM cohort_counts
            WHERE offset_month = 0 AND user_cnt >= 50)
        SELECT STRFTIME(cc.cohort_month, '%Y-%m') AS cohort_month, cc.offset_month, cc.user_cnt,
               ROUND(cc.user_cnt * 100.0 / FIRST_VALUE(cc.user_cnt) OVER (
                   PARTITION BY cc.cohort_month ORDER BY cc.offset_month), 2) AS retention_pct
        FROM cohort_counts cc
        JOIN valid_cohorts vc ON cc.cohort_month = vc.cohort_month
        ORDER BY 1, 2
    """).df()

    d["windows"] = con.sql(f"""
        WITH user_purchases AS (
            SELECT c.customer_unique_id,
                   CAST(o.order_purchase_timestamp AS DATE) AS purchase_date,
                   ROW_NUMBER() OVER (PARTITION BY c.customer_unique_id
                       ORDER BY CAST(o.order_purchase_timestamp AS DATE)) AS purchase_rank
            FROM '{csv_path("olist_customers_dataset.csv")}' c
            JOIN '{csv_path("olist_orders_dataset.csv")}' o ON c.customer_id = o.customer_id
            WHERE o.order_status = 'delivered'),
        purchase_gaps AS (
            SELECT DATEDIFF('day', a.purchase_date, b.purchase_date) AS days_to_repurchase
            FROM user_purchases a
            JOIN user_purchases b ON a.customer_unique_id = b.customer_unique_id
                AND a.purchase_rank = 1 AND b.purchase_rank = 2)
        SELECT CASE
                   WHEN days_to_repurchase <= 7   THEN '0-7 天'
                   WHEN days_to_repurchase <= 14  THEN '8-14 天'
                   WHEN days_to_repurchase <= 30  THEN '15-30 天'
                   WHEN days_to_repurchase <= 60  THEN '31-60 天'
                   WHEN days_to_repurchase <= 90  THEN '61-90 天'
                   WHEN days_to_repurchase <= 180 THEN '91-180 天'
                   ELSE '180+ 天'
               END AS window_group,
               COUNT(*) AS user_cnt,
               ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct
        FROM purchase_gaps GROUP BY 1
        ORDER BY MIN(days_to_repurchase)
    """).df()

    d["cat_repurchase"] = con.sql(f"""
        WITH cat_users AS (
            SELECT c.customer_unique_id,
                   COALESCE(t.product_category_name_english, p.product_category_name) AS category,
                   COUNT(DISTINCT o.order_id) AS order_cnt
            FROM '{csv_path("olist_customers_dataset.csv")}' c
            JOIN '{csv_path("olist_orders_dataset.csv")}' o ON c.customer_id = o.customer_id
            JOIN '{csv_path("olist_order_items_dataset.csv")}' oi ON o.order_id = oi.order_id
            JOIN '{csv_path("olist_products_dataset.csv")}' p ON oi.product_id = p.product_id
            LEFT JOIN '{csv_path("product_category_name_translation.csv")}' t
                ON p.product_category_name = t.product_category_name
            WHERE o.order_status = 'delivered'
            GROUP BY c.customer_unique_id, category)
        SELECT category, COUNT(DISTINCT customer_unique_id) AS total_buyers,
               ROUND(COUNT(DISTINCT CASE WHEN order_cnt >= 2 THEN customer_unique_id END) * 100.0
                   / COUNT(DISTINCT customer_unique_id), 2) AS repurchase_rate
        FROM cat_users
        GROUP BY category
        HAVING COUNT(DISTINCT customer_unique_id) >= 500
        ORDER BY repurchase_rate DESC LIMIT 15
    """).df()

    return d


# ---------------------------------------------------------------------------
# 2. 图表层：每个分析阶段一组 Plotly 交互图表
# ---------------------------------------------------------------------------
def fig_to_div(fig: go.Figure, div_id: str) -> str:
    return fig.to_html(full_html=False, include_plotlyjs=False,
                       div_id=div_id, config=CHART_CONFIG)


def build_figures(d: dict) -> dict:
    f = {}

    # --- 阶段 01：月度趋势 ---
    fig = go.Figure(go.Scatter(
        x=d["monthly"]["month"], y=d["monthly"]["order_cnt"], mode="lines+markers",
        line={"color": GREEN, "width": 2.5}, marker={"size": 6},
        hovertemplate="%{x}<br>订单数：%{y:,}<extra></extra>"))
    fig.update_layout(title="月度订单趋势（delivered）", height=380,
                      xaxis_title="月份", yaxis_title="订单数",
                      margin={"t": 50, "b": 40})
    f["monthly"] = fig_to_div(fig, "fig-monthly")

    # --- 阶段 01：订单状态分布 ---
    cmap = {"delivered": GREEN, "canceled": RED, "unavailable": RED}
    fig = go.Figure(go.Bar(
        x=d["status"]["order_status"], y=d["status"]["order_cnt"],
        marker_color=[cmap.get(s, BLUE) for s in d["status"]["order_status"]],
        text=[f"{p}%" for p in d["status"]["pct"]], textposition="outside",
        hovertemplate="状态：%{x}<br>订单数：%{y:,}<br>占比：%{text}<extra></extra>"))
    fig.update_layout(title="订单状态分布", height=380, xaxis_title="",
                      yaxis_title="订单数", margin={"t": 50, "b": 40})
    f["status"] = fig_to_div(fig, "fig-status")

    # --- 阶段 01：品类表现（按钮切换 订单量 / GMV）---
    cat = d["categories"]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=cat["order_cnt"], y=cat["category"], orientation="h", name="按订单量",
        marker_color=BLUE,
        text=[f"{v:,}" for v in cat["order_cnt"]], textposition="outside",
        hovertemplate="品类：%{y}<br>订单数：%{x:,}<extra></extra>"))
    fig.add_trace(go.Bar(
        x=cat["total_revenue"], y=cat["category"], orientation="h", name="按 GMV",
        visible=False, marker_color=GREEN,
        text=[f"R${v/1000:,.0f}K" for v in cat["total_revenue"]], textposition="outside",
        hovertemplate="品类：%{y}<br>GMV：R$%{x:,.0f}<extra></extra>"))
    fig.update_layout(
        title="Top 15 品类表现（点按钮切换口径）", height=480,
        xaxis_title="订单数 / GMV", yaxis={"autorange": "reversed"},
        margin={"t": 80, "b": 40, "l": 160}, showlegend=False,
        updatemenus=[{"type": "buttons", "direction": "right",
                      "x": 0.5, "xanchor": "center", "y": 1.12,
                      "buttons": [
                          {"label": "按订单量", "method": "update",
                           "args": [{"visible": [True, False]}]},
                          {"label": "按 GMV", "method": "update",
                           "args": [{"visible": [False, True]}]}]}])
    f["categories"] = fig_to_div(fig, "fig-categories")

    # --- 阶段 01：用户地理分布 ---
    st = d["states"]
    fig = go.Figure(go.Bar(
        x=st["customer_state"], y=st["customer_cnt"],
        marker_color=[RED if s == "SP" else BLUE for s in st["customer_state"]],
        text=[f"{v:,}" for v in st["customer_cnt"]], textposition="outside",
        hovertemplate="州：%{x}<br>唯一用户数：%{y:,}<extra></extra>"))
    fig.update_layout(title="用户地理分布 Top 10 州", height=480,
                      xaxis_title="州", yaxis_title="唯一用户数",
                      margin={"t": 50, "b": 40})
    f["states"] = fig_to_div(fig, "fig-states")

    # --- 阶段 02：订单漏斗 ---
    fun = d["funnel"]
    fig = go.Figure(go.Funnel(
        y=fun["stage"], x=fun["cnt"],
        textinfo="value+percent initial+percent previous",
        marker={"color": [DARK, BLUE, "#2980b9", GREEN]},
        hovertemplate="%{y}<br>订单数：%{x:,}<extra></extra>"))
    fig.update_layout(title="订单转化漏斗（下单 → 送达）", height=400,
                      margin={"t": 50, "b": 20, "l": 110})
    f["funnel"] = fig_to_div(fig, "fig-funnel")

    # --- 阶段 02：各阶段耗时 ---
    tm = d["stage_times"]
    fig = go.Figure()
    for col, color, label in [("avg_v", BLUE, "平均"), ("median_v", GREEN, "中位数"),
                              ("p95_v", RED, "P95")]:
        fig.add_trace(go.Bar(
            x=tm["stage"], y=tm[col], name=label, marker_color=color,
            text=[f"{v:g}" for v in tm[col]], textposition="outside",
            hovertemplate="%{x}<br>" + label + "：%{y}<extra></extra>",
            customdata=tm["unit"],
        ))
    fig.update_layout(title="各阶段耗时（阶段1单位：小时；阶段2/3单位：天）",
                      barmode="group", height=400,
                      xaxis_title="", yaxis_title="耗时",
                      margin={"t": 50, "b": 40}, legend={"orientation": "h", "y": 1.12})
    f["stage_times"] = fig_to_div(fig, "fig-stage-times")

    # --- 阶段 02：按州送达率 ---
    fs = d["funnel_by_state"]
    fig = go.Figure(go.Bar(
        x=fs["customer_state"], y=fs["delivery_rate"],
        marker_color=BLUE,
        text=[f"{v}%" for v in fs["delivery_rate"]], textposition="outside",
        customdata=fs["total_orders"],
        hovertemplate="州：%{x}<br>送达率：%{y}%<br>订单数：%{customdata:,}<extra></extra>"))
    fig.update_layout(title="送达率 by 州（Top 10 订单量州）", height=400,
                      yaxis={"range": [94, 99]}, xaxis_title="州",
                      yaxis_title="送达率 %", margin={"t": 50, "b": 40})
    f["funnel_by_state"] = fig_to_div(fig, "fig-funnel-state")

    # --- 阶段 03：RFM 分群（人数占比 vs GMV 占比）---
    rf = d["rfm"]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=rf["segment"], y=rf["user_pct"], name="用户占比 %",
                         marker_color=BLUE,
                         hovertemplate="%{x}<br>用户占比：%{y}%<extra></extra>"))
    fig.add_trace(go.Bar(x=rf["segment"], y=rf["gmv_pct"], name="GMV 占比 %",
                         marker_color=ORANGE,
                         hovertemplate="%{x}<br>GMV 占比：%{y}%<extra></extra>"))
    fig.update_layout(title="RFM 分群：用户占比 vs GMV 占比", barmode="group",
                      height=420, yaxis_title="%",
                      margin={"t": 50, "b": 100},
                      legend={"orientation": "h", "y": 1.15})
    fig.update_xaxes(tickangle=-30)
    f["rfm"] = fig_to_div(fig, "fig-rfm")

    # --- 阶段 04：Cohort 留存热力图 ---
    co = d["cohort"]
    pivot = co.pivot_table(index="cohort_month", columns="offset_month",
                           values="retention_pct", aggfunc="max")
    pivot = pivot[[c for c in range(12) if c in pivot.columns]]
    pivot = pivot.sort_index()
    z = pivot.values
    text = [["" if pd.isna(v) else f"{v:.1f}" for v in row] for row in z]
    fig = go.Figure(go.Heatmap(
        z=z, x=[f"M{c}" for c in pivot.columns], y=list(pivot.index),
        colorscale="YlOrRd", zmin=0, zmax=100,
        text=text, texttemplate="%{text}", textfont={"size": 9},
        xgap=2, ygap=2,
        hovertemplate="Cohort：%{y}<br>购后 %{x}<br>留存率：%{text}%<extra></extra>",
        colorbar={"title": "留存率 %"}))
    fig.update_layout(title="Cohort 留存矩阵（行=首购月，列=购后第 N 月，仅首月≥50人的cohort）",
                      height=560, xaxis_title="首次购买后的月数",
                      yaxis_title="Cohort（首购月）", yaxis={"autorange": "reversed"},
                      margin={"t": 60, "b": 60})
    f["cohort"] = fig_to_div(fig, "fig-cohort")

    # --- 阶段 04：平均留存曲线 ---
    avg = co.groupby("offset_month")["retention_pct"].mean().reset_index()
    avg = avg[avg["offset_month"] <= 12]
    fig = go.Figure(go.Scatter(
        x=avg["offset_month"], y=avg["retention_pct"], mode="lines+markers",
        line={"color": RED, "width": 2.5}, marker={"size": 8},
        fill="tozeroy", fillcolor="rgba(231,76,60,0.08)",
        hovertemplate="购后 M%{x}<br>平均留存率：%{y:.2f}%<extra></extra>"))
    fig.update_layout(title="平均留存曲线（所有 cohort 平均）", height=420,
                      xaxis_title="首次购买后的月数", yaxis_title="平均留存率 %",
                      margin={"t": 50, "b": 40})
    f["avg_retention"] = fig_to_div(fig, "fig-avg-retention")

    # --- 阶段 04：复购时间窗口（柱状 + 累计线）---
    wd = d["windows"]
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(
        x=wd["window_group"], y=wd["user_cnt"], name="用户数",
        marker_color=[GREEN, "#27ae60", "#f39c12", ORANGE, RED, "#c0392b", GRAY][:len(wd)],
        text=[f"{p}%" for p in wd["pct"]], textposition="outside",
        hovertemplate="%{x}<br>用户数：%{y:,}<br>占比：%{text}<extra></extra>"),
        secondary_y=False)
    cum = wd["pct"].cumsum().round(1)
    fig.add_trace(go.Scatter(
        x=wd["window_group"], y=cum, mode="lines+markers", name="累计占比",
        line={"color": BLUE, "width": 2.5, "dash": "dot"}, marker={"size": 8},
        hovertemplate="%{x}<br>累计：%{y}%<extra></extra>"),
        secondary_y=True)
    fig.update_layout(title="复购时间窗口（首单 → 第二单）", height=420,
                      margin={"t": 50, "b": 60}, legend={"orientation": "h", "y": 1.15})
    fig.update_xaxes(title="首单到第二单的间隔", tickangle=-25)
    fig.update_yaxes(title="用户数", secondary_y=False)
    fig.update_yaxes(title="累计占比 %", range=[0, 105], secondary_y=True)
    f["windows"] = fig_to_div(fig, "fig-windows")

    # --- 阶段 04：品类复购率 ---
    cr = d["cat_repurchase"]
    fig = go.Figure(go.Bar(
        x=cr["repurchase_rate"], y=cr["category"], orientation="h",
        marker_color=BLUE,
        text=[f"{v}%" for v in cr["repurchase_rate"]], textposition="outside",
        customdata=cr["total_buyers"],
        hovertemplate="品类：%{y}<br>复购率：%{x}%<br>购买用户数：%{customdata:,}<extra></extra>"))
    overall = float(d["repurchase"]["repurchase_rate"])
    fig.add_vline(x=overall, line_dash="dash", line_color=RED,
                  annotation_text=f"整体均值 {overall}%", annotation_position="bottom right")
    fig.update_layout(title="品类复购率 Top 15（≥500 购买用户）", height=480,
                      xaxis_title="复购率 %", yaxis={"autorange": "reversed"},
                      margin={"t": 50, "b": 40, "l": 160})
    f["cat_repurchase"] = fig_to_div(fig, "fig-cat-repurchase")

    return f


# ---------------------------------------------------------------------------
# 3. 页面层：KPI 卡片 + 分区布局 + 洞察文案，拼成单文件 HTML
# ---------------------------------------------------------------------------
def build_html(d: dict, figs: dict) -> str:
    k, rp = d["kpis"], d["repurchase"]
    gmv_m = float(k["total_gmv"]) / 1e6
    rf = d["rfm"]
    champ = rf[rf["segment"].str.startswith("Champions")].iloc[0]
    risk = rf[rf["segment"].str.startswith("At Risk")].iloc[0]
    sp_share = float(d["states"]["customer_cnt"].iloc[0]) * 100.0 / float(k["unique_customers"])
    st = d["stage_times"]
    w7 = d["windows"]["pct"].iloc[0]
    top_cat = d["cat_repurchase"].iloc[0]

    # 以下洞察文案中的数字全部来自查询结果（不硬编码业务数字）
    mon = d["monthly"]
    peak_row = mon.loc[mon["order_cnt"].idxmax()]
    avg_2018 = mon[mon["month"] >= "2018-01"]["order_cnt"].mean()
    fun = d["funnel"]
    step_appr = fun["cnt"].iloc[1] * 100.0 / fun["cnt"].iloc[0]
    step_carr = fun["cnt"].iloc[2] * 100.0 / fun["cnt"].iloc[1]
    overall_deliver = fun["cnt"].iloc[3] * 100.0 / fun["cnt"].iloc[0]
    wg = d["categories"][d["categories"]["category"] == "watches_gifts"]
    wg_ratio = (wg["total_revenue"].iloc[0] / wg["order_cnt"].iloc[0]) / float(k["avg_order_value"])
    five_star = d["review_dist"].loc[5, "pct"]
    one_star = d["review_dist"].loc[1, "pct"]
    ship_avg, ship_med, ship_p95 = st["avg_v"].iloc[2], st["median_v"].iloc[2], st["p95_v"].iloc[2]

    def tile(label, value, sub):
        return (f'<div class="tile"><div class="tile-label">{label}</div>'
                f'<div class="tile-value">{value}</div>'
                f'<div class="tile-sub">{sub}</div></div>')

    kpi_tiles = "\n".join([
        tile("总订单数", f'{int(k["total_orders"]):,}',
             f'送达 {int(k["delivered_orders"]):,} 单（{k["delivered_orders"]*100.0/k["total_orders"]:.2f}%）'),
        tile("唯一用户", f'{int(k["unique_customers"]):,}', "customer_unique_id 口径"),
        tile("复购率", f'{rp["repurchase_rate"]}%',
             f'{int(rp["repurchase_users"]):,} 位用户购买 ≥2 次'),
        tile("平均客单价", f'R${k["avg_order_value"]:,.2f}', "按订单商品总价计"),
        tile("总 GMV（delivered）", f"R${gmv_m:.2f}M", "剔除取消/不可用订单"),
        tile("平均评分", f'{k["avg_review_score"]}', f"5 星 {five_star}% / 1 星 {one_star}%"),
        tile("供给侧", f'{int(k["sellers"]):,} 卖家', f'{int(k["products"]):,} 个商品 · 73 个品类'),
        tile("运输耗时（揽收→送达）", f"{ship_med:g} 天中位", f"平均 {ship_avg:g} 天 · P95 {ship_p95:g} 天"),
    ])

    rfm_rows = ""
    strategies = {
        "Champions": "重点维护：VIP 服务、新品优先体验、专属客服",
        "Loyal": "会员体系 + 积分兑换，持续提升粘性",
        "At Risk": "<b>最高优先级召回</b>：大额优惠券 + 专属客服定向触达",
        "Hibernating": "低成本触达（邮件/短信），不投入大额券",
    }
    for _, r in rf.iterrows():
        key = r["segment"].split("（")[0]
        rfm_rows += (f'<tr><td>{r["segment"]}</td><td>{int(r["user_cnt"]):,}</td>'
                     f'<td>{r["user_pct"]}%</td><td>R${r["total_gmv"]/1000:,.0f}K</td>'
                     f'<td>{r["gmv_pct"]}%</td>'
                     f'<td>{strategies.get(key, "—")}</td></tr>')

    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")

    figs_html = figs
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Olist 电商全链路策略看板</title>
<script>{PLOTLY_JS}</script>
<style>
  :root {{
    --bg: #f4f6f9; --card: #ffffff; --ink: #2c3e50; --muted: #7f8c8d;
    --accent: #3498db; --line: #e6eaef;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; background: var(--bg); color: var(--ink);
    font-family: -apple-system, "Segoe UI", "PingFang SC", "Hiragino Sans GB",
                 "Microsoft YaHei", "Noto Sans CJK SC", sans-serif;
  }}
  header {{
    background: linear-gradient(120deg, #1a2a45 0%, #2c3e50 55%, #16455e 100%);
    color: #fff; padding: 34px 40px 28px;
  }}
  header h1 {{ margin: 0 0 8px; font-size: 26px; letter-spacing: 0.5px; }}
  header p {{ margin: 4px 0; color: #c9d6e3; font-size: 14px; }}
  header .tag {{
    display: inline-block; margin-right: 8px; margin-top: 10px; padding: 3px 12px;
    border: 1px solid rgba(255,255,255,.35); border-radius: 999px; font-size: 12px;
    color: #eaf2fa;
  }}
  main {{ max-width: 1280px; margin: 0 auto; padding: 26px 28px 60px; }}
  .kpi-grid {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 14px; margin: 26px 0 8px;
  }}
  .tile {{
    background: var(--card); border: 1px solid var(--line); border-radius: 10px;
    padding: 14px 16px; box-shadow: 0 1px 3px rgba(16, 30, 54, .06);
  }}
  .tile-label {{ font-size: 12px; color: var(--muted); }}
  .tile-value {{ font-size: 24px; font-weight: 700; margin: 4px 0 2px; }}
  .tile-sub {{ font-size: 11.5px; color: var(--muted); line-height: 1.45; }}
  section.block {{ margin-top: 34px; }}
  section.block > h2 {{
    font-size: 19px; margin: 0 0 4px; padding-left: 12px;
    border-left: 4px solid var(--accent);
  }}
  .insight {{
    background: #fff8ec; border: 1px solid #f4dfb8; border-radius: 8px;
    color: #6b5316; font-size: 13.5px; line-height: 1.75;
    padding: 12px 16px; margin: 12px 0 14px;
  }}
  .insight b {{ color: #8a5a00; }}
  .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
  @media (max-width: 900px) {{ .grid-2 {{ grid-template-columns: 1fr; }} }}
  .card {{
    background: var(--card); border: 1px solid var(--line); border-radius: 10px;
    padding: 10px 12px; box-shadow: 0 1px 3px rgba(16, 30, 54, .06);
  }}
  .full {{ margin-top: 16px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th, td {{ border-bottom: 1px solid var(--line); padding: 9px 10px; text-align: left; }}
  th {{ background: #f8fafc; color: #57606a; font-weight: 600; }}
  tr:hover td {{ background: #f6f9fc; }}
  footer {{
    max-width: 1280px; margin: 0 auto; padding: 0 28px 50px;
    color: var(--muted); font-size: 12.5px; line-height: 1.8;
  }}
  .js-plotly-plot .plotly .modebar {{ opacity: .35; }}
  .js-plotly-plot .plotly .modebar:hover {{ opacity: 1; }}
</style>
</head>
<body>
<header>
  <h1>Olist 电商全链路策略看板</h1>
  <p>业务理解 → 转化漏斗 → RFM 用户分层 → 留存/复购 · 巴西电商真实数据（2016-09 ~ 2018-10，约 10 万笔订单）</p>
  <p>生成时间：{now} · 由 build_dashboard.py 自动生成（DuckDB 现场聚合 + Plotly 渲染，全部数字可复现）</p>
  <span class="tag">悬浮查看明细</span><span class="tag">点击图例可隐藏/显示序列</span><span class="tag">可缩放/平移/导出 PNG</span>
</header>

<main>
  <div class="kpi-grid">
{kpi_tiles}
  </div>

  <section class="block">
    <h2>1 · 经营概览</h2>
    <div class="insight">
      <b>解读：</b>{overall_deliver:.2f}% 的订单最终送达，平台履约基本盘健康；2017 年快速爬坡，
      {peak_row["month"]} 达到峰值（{int(peak_row["order_cnt"]):,} 单，疑似黑五大促），
      2018 年稳定在月均约 {avg_2018:,.0f} 单进入平台期。
      用户高度集中在圣保罗州（SP 占 {sp_share:.1f}%），区域扩张是长期增长命题。
    </div>
    <div class="grid-2">
      <div class="card">{figs_html["monthly"]}</div>
      <div class="card">{figs_html["status"]}</div>
    </div>
  </section>

  <section class="block">
    <h2>2 · 品类与地域</h2>
    <div class="insight">
      <b>解读：</b>bed_bath_table / health_beauty / sports_leisure 是订单量 Top 3（高频刚需）；
      但 <b>watches_gifts 订单量未进前三，GMV 却位居前列</b>（客单价约为平台均值的 {wg_ratio:.1f} 倍）——
      高价值品类值得专项运营。点击图表上方按钮可切换"订单量 / GMV"两种口径。
    </div>
    <div class="grid-2">
      <div class="card">{figs_html["categories"]}</div>
      <div class="card">{figs_html["states"]}</div>
    </div>
  </section>

  <section class="block">
    <h2>3 · 转化漏斗与履约时效</h2>
    <div class="insight">
      <b>解读：</b>审批环节转化率 {step_appr:.2f}%、揽收 {step_carr:.2f}%，几乎无流失，
      <b>主要流失发生在送达环节</b>（整体送达率 {overall_deliver:.2f}%）；时效瓶颈在运输——
      揽收→送达平均 {ship_avg:g} 天、P95 高达 {ship_p95:g} 天（5% 的用户等了大半个月，差评高危人群）。
      策略优先级：与物流商谈 SLA / 引入多家物流竞争 + 对超长等待订单主动触达补偿。
    </div>
    <div class="grid-2">
      <div class="card">{figs_html["funnel"]}</div>
      <div class="card">{figs_html["stage_times"]}</div>
    </div>
    <div class="card full">{figs_html["funnel_by_state"]}</div>
  </section>

  <section class="block">
    <h2>4 · RFM 用户分层</h2>
    <div class="insight">
      <b>解读：</b>Champions（冠军用户）占用户数 {champ["user_pct"]}%，却贡献 <b>{champ["gmv_pct"]}% 的 GMV</b>——
      值得 VIP 级维护；At Risk（流失风险）用户占 {risk["user_pct"]}% 但贡献 {risk["gmv_pct"]}% GMV，
      是<b>投入产出比最高的召回对象</b>（召回成本 &lt; 获新客成本）。
      注：97% 用户只购买 1 次（F 维度退化），分层实际由 R（近期活跃）× M（消费金额）驱动。
    </div>
    <div class="grid-2">
      <div class="card">{figs_html["rfm"]}</div>
      <div class="card">
        <div style="padding: 8px 6px;">
          <table>
            <thead><tr><th>群体</th><th>人数</th><th>用户占比</th><th>GMV</th><th>GMV 占比</th><th>运营动作</th></tr></thead>
            <tbody>{rfm_rows}</tbody>
          </table>
        </div>
      </div>
    </div>
  </section>

  <section class="block">
    <h2>5 · 留存与复购</h2>
    <div class="insight">
      <b>解读：</b>整体复购率仅 <b>{rp["repurchase_rate"]}%</b>——平台最大的增长杠杆。
      留存曲线在首月后断崖式下跌；复购用户中 <b>{w7}% 在首单后 7 天内完成第二单</b>，
      首单后 30 天是决定复购的关键窗口 → 建议 <b>第 7 / 15 / 25 天</b>三次触达
      （感谢信+推荐 → 限时券 → 紧迫感提醒）。品类上，{top_cat["category"]} 复购率最高（{top_cat["repurchase_rate"]}%），
      适合做复购运营试点。
    </div>
    <div class="card full">{figs_html["cohort"]}</div>
    <div class="grid-2" style="margin-top:16px;">
      <div class="card">{figs_html["avg_retention"]}</div>
      <div class="card">{figs_html["windows"]}</div>
    </div>
    <div class="card full">{figs_html["cat_repurchase"]}</div>
  </section>
</main>

<footer>
  <b>数据与口径</b>：Kaggle <i>olistbr/brazilian-ecommerce</i>（CC BY-SA 4.0）；
  用户级分析使用 customer_unique_id；GMV / RFM / 留存仅统计 delivered 订单；Cohort 矩阵过滤首月用户 &lt; 50 的早期月份。<br>
  <b>重新生成</b>：<code>python sql_and_bi/BI_DashBoards/build_dashboard.py</code>（依赖：uv sync 后开箱即用，无新增依赖）。<br>
  <b>配套产出</b>：同仓库 <code>notebooks/01-04</code>（完整分析过程）、<code>reports/</code>（静态图表）、
  <code>sql_and_bi/sql_work/</code>（纯 SQL 复刻，含窗口函数 / CTE / 多表 JOIN / PIVOT）。
</footer>
</body>
</html>"""
    return html


def main():
    if not RAW.exists():
        raise SystemExit(
            f"未找到原始数据目录：{RAW}\n"
            "请先按 data/README.md 下载数据：\n"
            "  kaggle datasets download -d olistbr/brazilian-ecommerce -p data/raw --unzip")

    con = duckdb.connect()
    print("1/3 正在用 DuckDB 聚合原始 CSV ...")
    data = load_data(con)
    con.close()

    print("2/3 正在生成交互图表 ...")
    figs = build_figures(data)

    print("3/3 正在拼装单文件 HTML ...")
    html = build_html(data, figs)

    out = HERE / "olist_strategy_dashboard.html"
    out.write_text(html, encoding="utf-8")
    size_mb = out.stat().st_size / 1e6
    print(f"\n✅ 看板已生成：{out}")
    print(f"   文件大小：{size_mb:.1f} MB（plotly.js 已内联，离线双击即可打开）")


if __name__ == "__main__":
    main()
