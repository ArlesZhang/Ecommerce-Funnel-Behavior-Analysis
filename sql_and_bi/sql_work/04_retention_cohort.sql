-- ============================================================================
-- 04 留存/复购分析：复购率 → Cohort 留存矩阵 → 复购窗口期 → 品类复购
-- ----------------------------------------------------------------------------
-- 对应产出：notebooks/04_retention_analysis.ipynb 的纯 SQL 复刻
-- 口径说明：
--   * 用户身份：customer_unique_id；订单口径：仅 order_status = 'delivered'
--   * Cohort 定义：用户首次购买所在月；留存 = 该 cohort 用户在第 N 个月
--     仍有购买；Cohort 留存矩阵仅保留首月用户数 >= 50 的 cohort（与
--     notebook 一致，过滤样本过少的早期月份）
-- SQL 技术点：
--   * CTE 链 + MIN() 定首购月 + DATEDIFF('month') 算 cohort offset
--   * 窗口函数 FIRST_VALUE()：以 offset=0 的用户数为基准算留存率
--   * PIVOT ... ON ... IN：长表透视成留存矩阵宽表
--   * 窗口函数 ROW_NUMBER() OVER (PARTITION BY ...)：定位首单/第二单
--   * 5 表 JOIN：customers ⋈ orders ⋈ order_items ⋈ products ⋈ translation
-- 运行方式：在 sql_and_bi/sql_work/ 目录下，用本目录的 sql_workbook.ipynb
--           逐段执行；每段以 "-- QUERY:" 开头的注释分隔
-- ============================================================================

-- QUERY: 04-1 整体复购率概览
WITH user_orders AS (
    SELECT
        c.customer_unique_id,
        COUNT(DISTINCT o.order_id) AS order_cnt
    FROM '../../data/raw/olist_customers_dataset.csv' c
    JOIN '../../data/raw/olist_orders_dataset.csv' o
        ON c.customer_id = o.customer_id
    WHERE o.order_status = 'delivered'
    GROUP BY c.customer_unique_id
)
SELECT
    COUNT(*)                                            AS total_users,
    SUM(CASE WHEN order_cnt >= 2 THEN 1 ELSE 0 END)     AS repurchase_users,
    SUM(CASE WHEN order_cnt >= 3 THEN 1 ELSE 0 END)     AS three_plus_users,
    ROUND(SUM(CASE WHEN order_cnt >= 2 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS repurchase_rate,
    ROUND(AVG(order_cnt), 2)                            AS avg_orders_per_user,
    MAX(order_cnt)                                      AS max_orders
FROM user_orders;

-- QUERY: 04-2 Cohort 购买明细（长表：cohort 月 × 购买偏移月 × 用户数）
WITH user_purchases AS (
    SELECT
        c.customer_unique_id,
        DATE_TRUNC('month', CAST(o.order_purchase_timestamp AS TIMESTAMP)) AS purchase_month
    FROM '../../data/raw/olist_customers_dataset.csv' c
    JOIN '../../data/raw/olist_orders_dataset.csv' o
        ON c.customer_id = o.customer_id
    WHERE o.order_status = 'delivered'
),
first_purchase AS (
    SELECT
        customer_unique_id,
        MIN(purchase_month) AS cohort_month
    FROM user_purchases
    GROUP BY customer_unique_id
),
cohort_offsets AS (
    SELECT
        fp.cohort_month,
        fp.customer_unique_id,
        DATEDIFF('month', fp.cohort_month, up.purchase_month) AS offset_month
    FROM first_purchase fp
    JOIN user_purchases up
        ON fp.customer_unique_id = up.customer_unique_id
)
SELECT
    CAST(cohort_month AS DATE) AS cohort_month,
    offset_month,
    COUNT(DISTINCT customer_unique_id) AS user_cnt
FROM cohort_offsets
GROUP BY 1, 2
ORDER BY 1, 2;

-- QUERY: 04-3 Cohort 留存率（长表 + FIRST_VALUE 窗口函数定基准）
-- 仅保留首月用户数 >= 50 的 cohort；留存率 = 当月活跃用户 / 首月用户数
WITH user_purchases AS (
    SELECT
        c.customer_unique_id,
        DATE_TRUNC('month', CAST(o.order_purchase_timestamp AS TIMESTAMP)) AS purchase_month
    FROM '../../data/raw/olist_customers_dataset.csv' c
    JOIN '../../data/raw/olist_orders_dataset.csv' o
        ON c.customer_id = o.customer_id
    WHERE o.order_status = 'delivered'
),
first_purchase AS (
    SELECT customer_unique_id, MIN(purchase_month) AS cohort_month
    FROM user_purchases
    GROUP BY customer_unique_id
),
cohort_counts AS (
    SELECT
        fp.cohort_month,
        DATEDIFF('month', fp.cohort_month, up.purchase_month) AS offset_month,
        COUNT(DISTINCT fp.customer_unique_id) AS user_cnt
    FROM first_purchase fp
    JOIN user_purchases up
        ON fp.customer_unique_id = up.customer_unique_id
    GROUP BY 1, 2
),
valid_cohorts AS (
    SELECT cohort_month
    FROM cohort_counts
    WHERE offset_month = 0 AND user_cnt >= 50
)
SELECT
    CAST(cc.cohort_month AS DATE) AS cohort_month,
    cc.offset_month,
    cc.user_cnt,
    ROUND(cc.user_cnt * 100.0
        / FIRST_VALUE(cc.user_cnt) OVER (
            PARTITION BY cc.cohort_month
            ORDER BY cc.offset_month
        ), 2) AS retention_pct
FROM cohort_counts cc
JOIN valid_cohorts vc ON cc.cohort_month = vc.cohort_month
ORDER BY cc.cohort_month, cc.offset_month;

-- QUERY: 04-4 Cohort 留存矩阵（PIVOT 透视宽表，单位 %；列 = 购后第 N 月）
WITH user_purchases AS (
    SELECT
        c.customer_unique_id,
        DATE_TRUNC('month', CAST(o.order_purchase_timestamp AS TIMESTAMP)) AS purchase_month
    FROM '../../data/raw/olist_customers_dataset.csv' c
    JOIN '../../data/raw/olist_orders_dataset.csv' o
        ON c.customer_id = o.customer_id
    WHERE o.order_status = 'delivered'
),
first_purchase AS (
    SELECT customer_unique_id, MIN(purchase_month) AS cohort_month
    FROM user_purchases
    GROUP BY customer_unique_id
),
cohort_counts AS (
    SELECT
        fp.cohort_month,
        DATEDIFF('month', fp.cohort_month, up.purchase_month) AS offset_month,
        COUNT(DISTINCT fp.customer_unique_id) AS user_cnt
    FROM first_purchase fp
    JOIN user_purchases up
        ON fp.customer_unique_id = up.customer_unique_id
    GROUP BY 1, 2
),
valid_cohorts AS (
    SELECT cohort_month
    FROM cohort_counts
    WHERE offset_month = 0 AND user_cnt >= 50
),
retention_long AS (
    SELECT
        STRFTIME(cc.cohort_month, '%Y-%m') AS cohort_month,
        cc.offset_month,
        ROUND(cc.user_cnt * 100.0
            / FIRST_VALUE(cc.user_cnt) OVER (
                PARTITION BY cc.cohort_month
                ORDER BY cc.offset_month
            ), 1) AS retention_pct
    FROM cohort_counts cc
    JOIN valid_cohorts vc ON cc.cohort_month = vc.cohort_month
)
PIVOT retention_long
ON offset_month IN (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11)
USING MAX(retention_pct)
GROUP BY cohort_month
ORDER BY cohort_month;

-- QUERY: 04-5 平均留存曲线（各偏移月在所有 cohort 上的平均留存率）
WITH user_purchases AS (
    SELECT
        c.customer_unique_id,
        DATE_TRUNC('month', CAST(o.order_purchase_timestamp AS TIMESTAMP)) AS purchase_month
    FROM '../../data/raw/olist_customers_dataset.csv' c
    JOIN '../../data/raw/olist_orders_dataset.csv' o
        ON c.customer_id = o.customer_id
    WHERE o.order_status = 'delivered'
),
first_purchase AS (
    SELECT customer_unique_id, MIN(purchase_month) AS cohort_month
    FROM user_purchases
    GROUP BY customer_unique_id
),
cohort_counts AS (
    SELECT
        fp.cohort_month,
        DATEDIFF('month', fp.cohort_month, up.purchase_month) AS offset_month,
        COUNT(DISTINCT fp.customer_unique_id) AS user_cnt
    FROM first_purchase fp
    JOIN user_purchases up
        ON fp.customer_unique_id = up.customer_unique_id
    GROUP BY 1, 2
),
valid_cohorts AS (
    SELECT cohort_month
    FROM cohort_counts
    WHERE offset_month = 0 AND user_cnt >= 50
),
retention_long AS (
    SELECT
        cc.offset_month,
        cc.user_cnt * 100.0
            / FIRST_VALUE(cc.user_cnt) OVER (
                PARTITION BY cc.cohort_month
                ORDER BY cc.offset_month
            ) AS retention_pct
    FROM cohort_counts cc
    JOIN valid_cohorts vc ON cc.cohort_month = vc.cohort_month
)
SELECT
    offset_month,
    ROUND(AVG(retention_pct), 2) AS avg_retention_pct
FROM retention_long
GROUP BY offset_month
ORDER BY offset_month;

-- QUERY: 04-6 复购时间窗口（ROW_NUMBER 定位首单/第二单 + 间隔分桶）
-- 业务结论锚点：首单后 7 天内复购占比最高 => 7d/15d/25d 触达节奏的依据
WITH user_purchases AS (
    SELECT
        c.customer_unique_id,
        CAST(o.order_purchase_timestamp AS DATE) AS purchase_date,
        ROW_NUMBER() OVER (
            PARTITION BY c.customer_unique_id
            ORDER BY CAST(o.order_purchase_timestamp AS DATE)
        ) AS purchase_rank
    FROM '../../data/raw/olist_customers_dataset.csv' c
    JOIN '../../data/raw/olist_orders_dataset.csv' o
        ON c.customer_id = o.customer_id
    WHERE o.order_status = 'delivered'
),
purchase_gaps AS (
    SELECT
        a.customer_unique_id,
        DATEDIFF('day', a.purchase_date, b.purchase_date) AS days_to_repurchase
    FROM user_purchases a
    JOIN user_purchases b
        ON a.customer_unique_id = b.customer_unique_id
        AND a.purchase_rank = 1
        AND b.purchase_rank = 2
)
SELECT
    CASE
        WHEN days_to_repurchase <= 7   THEN '0-7 days'
        WHEN days_to_repurchase <= 14  THEN '8-14 days'
        WHEN days_to_repurchase <= 30  THEN '15-30 days'
        WHEN days_to_repurchase <= 60  THEN '31-60 days'
        WHEN days_to_repurchase <= 90  THEN '61-90 days'
        WHEN days_to_repurchase <= 180 THEN '91-180 days'
        ELSE '180+ days'
    END AS window_group,
    COUNT(*) AS user_cnt,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct,
    ROUND(AVG(days_to_repurchase), 1) AS avg_days
FROM purchase_gaps
GROUP BY 1
ORDER BY MIN(days_to_repurchase);

-- QUERY: 04-7 品类复购率 Top 15（5 表 JOIN + 条件去重计数）
-- 口径：同一用户在同一品类下有 >= 2 笔 delivered 订单 => 该品类复购用户
WITH cat_users AS (
    SELECT
        c.customer_unique_id,
        COALESCE(t.product_category_name_english, p.product_category_name) AS category,
        COUNT(DISTINCT o.order_id) AS order_cnt
    FROM '../../data/raw/olist_customers_dataset.csv' c
    JOIN '../../data/raw/olist_orders_dataset.csv' o
        ON c.customer_id = o.customer_id
    JOIN '../../data/raw/olist_order_items_dataset.csv' oi
        ON o.order_id = oi.order_id
    JOIN '../../data/raw/olist_products_dataset.csv' p
        ON oi.product_id = p.product_id
    LEFT JOIN '../../data/raw/product_category_name_translation.csv' t
        ON p.product_category_name = t.product_category_name
    WHERE o.order_status = 'delivered'
    GROUP BY c.customer_unique_id, category
)
SELECT
    category,
    COUNT(DISTINCT customer_unique_id) AS total_buyers,
    COUNT(DISTINCT CASE WHEN order_cnt >= 2 THEN customer_unique_id END) AS repurchase_buyers,
    ROUND(COUNT(DISTINCT CASE WHEN order_cnt >= 2 THEN customer_unique_id END) * 100.0
        / COUNT(DISTINCT customer_unique_id), 2) AS repurchase_rate
FROM cat_users
GROUP BY category
HAVING COUNT(DISTINCT customer_unique_id) >= 500
ORDER BY repurchase_rate DESC
LIMIT 15;
