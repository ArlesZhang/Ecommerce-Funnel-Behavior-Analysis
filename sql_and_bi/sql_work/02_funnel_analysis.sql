-- ============================================================================
-- 02 订单转化漏斗：下单 → 审批 → 揽收 → 送达
-- ----------------------------------------------------------------------------
-- 对应产出：notebooks/02_funnel_analysis.ipynb 的纯 SQL 复刻
-- 口径说明：漏斗以"各阶段时间戳是否非空"判定订单是否到达该阶段
--           （与 notebook 的 SQL 实现完全一致）
-- SQL 技术点：
--   * 多层 CTE：order_stages → funnel_stats → 最终窗口计算
--   * 窗口函数：FIRST_VALUE() 算整体转化率、LAG() 算环节转化率
--   * PERCENTILE_CONT() WITHIN GROUP：平均 / 中位 / P95 耗时
--   * CTE + 多表 JOIN + HAVING：按州拆分漏斗
-- 运行方式：在 sql_and_bi/sql_work/ 目录下，用本目录的 sql_workbook.ipynb
--           逐段执行；每段以 "-- QUERY:" 开头的注释分隔
-- ============================================================================

-- QUERY: 02-1 订单漏斗（CTE + FIRST_VALUE/LAG 窗口函数）
-- 整体转化率 = 当前阶段订单数 / 首阶段订单数（FIRST_VALUE）
-- 环节转化率 = 当前阶段订单数 / 上一阶段订单数（LAG）
WITH order_stages AS (
    SELECT
        order_id,
        order_status,
        -- 标记每个订单到达了哪些阶段
        CASE WHEN order_purchase_timestamp        IS NOT NULL THEN 1 ELSE 0 END AS is_purchased,
        CASE WHEN order_approved_at               IS NOT NULL THEN 1 ELSE 0 END AS is_approved,
        CASE WHEN order_delivered_carrier_date    IS NOT NULL THEN 1 ELSE 0 END AS is_carrier,
        CASE WHEN order_delivered_customer_date   IS NOT NULL THEN 1 ELSE 0 END AS is_delivered
    FROM '../../data/raw/olist_orders_dataset.csv'
),
funnel_stats AS (
    SELECT '1. Purchase'      AS stage, SUM(is_purchased) AS passed FROM order_stages
    UNION ALL
    SELECT '2. Approved',      SUM(is_approved)  FROM order_stages
    UNION ALL
    SELECT '3. Carrier Pickup', SUM(is_carrier)  FROM order_stages
    UNION ALL
    SELECT '4. Delivered',     SUM(is_delivered) FROM order_stages
)
SELECT
    stage,
    passed AS order_cnt,
    ROUND(passed * 100.0 / FIRST_VALUE(passed) OVER (ORDER BY stage), 2) AS overall_rate,
    ROUND(passed * 100.0 / LAG(passed)        OVER (ORDER BY stage), 2) AS step_rate
FROM funnel_stats
ORDER BY stage;

-- QUERY: 02-2 各阶段耗时统计（平均 / 中位 / P95，PERCENTILE_CONT）
SELECT
    'purchase→approve' AS stage,
    ROUND(AVG(EPOCH(CAST(order_approved_at AS TIMESTAMP)
                  - CAST(order_purchase_timestamp AS TIMESTAMP)) / 3600), 1) AS avg_hours,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY
        EPOCH(CAST(order_approved_at AS TIMESTAMP)
            - CAST(order_purchase_timestamp AS TIMESTAMP)) / 3600), 1) AS median_hours,
    ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY
        EPOCH(CAST(order_approved_at AS TIMESTAMP)
            - CAST(order_purchase_timestamp AS TIMESTAMP)) / 3600), 1) AS p95_hours
FROM '../../data/raw/olist_orders_dataset.csv'
WHERE order_approved_at IS NOT NULL
UNION ALL
SELECT
    'approve→carrier',
    ROUND(AVG(EPOCH(CAST(order_delivered_carrier_date AS TIMESTAMP)
                  - CAST(order_approved_at AS TIMESTAMP)) / 86400), 1),
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY
        EPOCH(CAST(order_delivered_carrier_date AS TIMESTAMP)
            - CAST(order_approved_at AS TIMESTAMP)) / 86400), 1),
    ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY
        EPOCH(CAST(order_delivered_carrier_date AS TIMESTAMP)
            - CAST(order_approved_at AS TIMESTAMP)) / 86400), 1)
FROM '../../data/raw/olist_orders_dataset.csv'
WHERE order_delivered_carrier_date IS NOT NULL
UNION ALL
SELECT
    'carrier→customer',
    ROUND(AVG(EPOCH(CAST(order_delivered_customer_date AS TIMESTAMP)
                  - CAST(order_delivered_carrier_date AS TIMESTAMP)) / 86400), 1),
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY
        EPOCH(CAST(order_delivered_customer_date AS TIMESTAMP)
            - CAST(order_delivered_carrier_date AS TIMESTAMP)) / 86400), 1),
    ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY
        EPOCH(CAST(order_delivered_customer_date AS TIMESTAMP)
            - CAST(order_delivered_carrier_date AS TIMESTAMP)) / 86400), 1)
FROM '../../data/raw/olist_orders_dataset.csv'
WHERE order_delivered_customer_date IS NOT NULL;

-- QUERY: 02-3 交叉分析：各状态订单卡在哪个环节（各阶段平均耗时）
SELECT
    order_status,
    COUNT(*) AS order_cnt,
    ROUND(AVG(EPOCH(CAST(order_approved_at AS TIMESTAMP)
                  - CAST(order_purchase_timestamp AS TIMESTAMP)) / 3600), 1) AS avg_hr_to_approve,
    ROUND(AVG(EPOCH(CAST(order_delivered_carrier_date AS TIMESTAMP)
                  - CAST(order_approved_at AS TIMESTAMP)) / 86400), 1) AS avg_days_to_carrier
FROM '../../data/raw/olist_orders_dataset.csv'
GROUP BY order_status
ORDER BY order_cnt DESC;

-- QUERY: 02-4 按州拆分漏斗（CTE + 多表 JOIN + HAVING 过滤小样本州）
WITH order_stages AS (
    SELECT
        c.customer_state,
        CASE WHEN o.order_purchase_timestamp      IS NOT NULL THEN 1 ELSE 0 END AS is_purchased,
        CASE WHEN o.order_approved_at             IS NOT NULL THEN 1 ELSE 0 END AS is_approved,
        CASE WHEN o.order_delivered_carrier_date  IS NOT NULL THEN 1 ELSE 0 END AS is_carrier,
        CASE WHEN o.order_delivered_customer_date IS NOT NULL THEN 1 ELSE 0 END AS is_delivered
    FROM '../../data/raw/olist_orders_dataset.csv' o
    JOIN '../../data/raw/olist_customers_dataset.csv' c
        ON o.customer_id = c.customer_id
)
SELECT
    customer_state,
    COUNT(*) AS total_orders,
    ROUND(SUM(is_delivered) * 100.0 / SUM(is_purchased), 2) AS delivery_rate,
    ROUND(SUM(is_carrier)   * 100.0 / SUM(is_approved),  2) AS carrier_rate
FROM order_stages
GROUP BY customer_state
HAVING COUNT(*) >= 100
ORDER BY total_orders DESC
LIMIT 10;
