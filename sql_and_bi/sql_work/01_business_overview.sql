-- ============================================================================
-- 01 业务理解：数据规模 / 订单状态 / 品类 / 用户身份 / 地理 / 支付评价
-- ----------------------------------------------------------------------------
-- 对应产出：notebooks/01_business_understanding.ipynb 的纯 SQL 复刻
-- 口径说明：与 notebook 完全一致（全量订单，不做状态过滤；用户级统计用
--           customer_unique_id）
-- SQL 技术点：
--   * 聚合窗口函数：SUM(COUNT(*)) OVER () 一次扫描算占比
--   * 多表 JOIN：order_items ⋈ products ⋈ category_translation（3 表）
--   * GROUP BY ... HAVING：筛出重复购买用户
--   * 标量子查询：单行 KPI 汇总
-- 运行方式：在 sql_and_bi/sql_work/ 目录下，用本目录的 sql_workbook.ipynb
--           逐段执行；每段以 "-- QUERY:" 开头的注释分隔
-- ============================================================================

-- QUERY: 01-1 数据规模总览（9 张表的行数对比）
SELECT 'orders'               AS table_name, COUNT(*) AS row_cnt FROM '../../data/raw/olist_orders_dataset.csv'
UNION ALL
SELECT 'customers',            COUNT(*) FROM '../../data/raw/olist_customers_dataset.csv'
UNION ALL
SELECT 'order_items',          COUNT(*) FROM '../../data/raw/olist_order_items_dataset.csv'
UNION ALL
SELECT 'order_payments',       COUNT(*) FROM '../../data/raw/olist_order_payments_dataset.csv'
UNION ALL
SELECT 'order_reviews',        COUNT(*) FROM '../../data/raw/olist_order_reviews_dataset.csv'
UNION ALL
SELECT 'products',             COUNT(*) FROM '../../data/raw/olist_products_dataset.csv'
UNION ALL
SELECT 'sellers',              COUNT(*) FROM '../../data/raw/olist_sellers_dataset.csv'
UNION ALL
SELECT 'geolocation',          COUNT(*) FROM '../../data/raw/olist_geolocation_dataset.csv'
UNION ALL
SELECT 'category_translation', COUNT(*) FROM '../../data/raw/product_category_name_translation.csv'
ORDER BY row_cnt DESC;

-- QUERY: 01-2 订单状态分布（窗口函数一次算出各状态占比）
SELECT
    order_status,
    COUNT(*) AS order_cnt,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct
FROM '../../data/raw/olist_orders_dataset.csv'
GROUP BY order_status
ORDER BY order_cnt DESC;

-- QUERY: 01-3 月度订单趋势（口径：仅 delivered 订单）
SELECT
    STRFTIME(CAST(order_purchase_timestamp AS TIMESTAMP), '%Y-%m') AS month,
    COUNT(*) AS order_cnt
FROM '../../data/raw/olist_orders_dataset.csv'
WHERE order_status = 'delivered'
GROUP BY 1
ORDER BY 1;

-- QUERY: 01-4 品类表现 Top 20（3 表 JOIN：明细 ⋈ 商品 ⋈ 品类翻译）
-- 品类名为葡萄牙语，展示前必须 LEFT JOIN 翻译表；翻译缺失时保留葡语原名
SELECT
    COALESCE(t.product_category_name_english, p.product_category_name) AS category,
    COUNT(DISTINCT oi.order_id)   AS order_cnt,
    ROUND(SUM(oi.price), 2)       AS total_revenue,
    ROUND(AVG(oi.price), 2)       AS avg_price,
    COUNT(DISTINCT oi.product_id) AS product_cnt
FROM '../../data/raw/olist_order_items_dataset.csv' oi
JOIN '../../data/raw/olist_products_dataset.csv' p
    ON oi.product_id = p.product_id
LEFT JOIN '../../data/raw/product_category_name_translation.csv' t
    ON p.product_category_name = t.product_category_name
GROUP BY 1
ORDER BY order_cnt DESC
LIMIT 20;

-- QUERY: 01-5 customer_id vs customer_unique_id（本项目最重要的数据陷阱）
-- customer_id 是订单级身份（1 订单 1 个），customer_unique_id 才是真实用户。
-- 两者的差值 = 拥有多个订单级身份的复购用户贡献的身份数。
SELECT
    COUNT(DISTINCT customer_id)        AS distinct_customer_ids,
    COUNT(DISTINCT customer_unique_id) AS distinct_unique_ids,
    COUNT(*)                           AS total_rows,
    COUNT(DISTINCT customer_id) - COUNT(DISTINCT customer_unique_id) AS duplicated_ids
FROM '../../data/raw/olist_customers_dataset.csv';

-- QUERY: 01-6 重复购买用户分布（GROUP BY + HAVING + 窗口占比 + 合计行）
-- 一个 customer_unique_id 对应多个 customer_id => 该用户购买过多次；
-- 末尾合计行 = 复购用户总数（对应 notebook 中的 2,997 人）
WITH repeat_users AS (
    SELECT
        customer_unique_id,
        COUNT(DISTINCT customer_id) AS id_count
    FROM '../../data/raw/olist_customers_dataset.csv'
    GROUP BY customer_unique_id
    HAVING COUNT(DISTINCT customer_id) > 1
),
dist AS (
    SELECT
        id_count,
        COUNT(*) AS user_cnt,
        ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct
    FROM repeat_users
    GROUP BY id_count
),
combined AS (
    SELECT CAST(id_count AS VARCHAR) AS id_count, user_cnt, pct, id_count AS sort_key
    FROM dist
    UNION ALL
    SELECT '合计', COUNT(*), 100.00, 9999
    FROM repeat_users
)
SELECT id_count, user_cnt, pct
FROM combined
ORDER BY sort_key;

-- QUERY: 01-7 用户地理分布（按州去重用户数 + 窗口占比）
SELECT
    customer_state,
    COUNT(DISTINCT customer_unique_id) AS customer_cnt,
    ROUND(COUNT(DISTINCT customer_unique_id) * 100.0
        / SUM(COUNT(DISTINCT customer_unique_id)) OVER (), 2) AS pct
FROM '../../data/raw/olist_customers_dataset.csv'
GROUP BY customer_state
ORDER BY customer_cnt DESC;

-- QUERY: 01-8 支付方式分布
SELECT
    payment_type,
    COUNT(*) AS pay_cnt,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct,
    ROUND(AVG(payment_value), 2) AS avg_value
FROM '../../data/raw/olist_order_payments_dataset.csv'
GROUP BY payment_type
ORDER BY pay_cnt DESC;

-- QUERY: 01-9 评价分数分布
SELECT
    review_score,
    COUNT(*) AS review_cnt,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct
FROM '../../data/raw/olist_order_reviews_dataset.csv'
GROUP BY review_score
ORDER BY review_score;

-- QUERY: 01-10 平台关键业务指标汇总（标量子查询拼成单行 KPI）
SELECT
    (SELECT COUNT(*) FROM '../../data/raw/olist_orders_dataset.csv'
     WHERE order_status = 'delivered') AS delivered_orders,
    (SELECT COUNT(DISTINCT customer_unique_id)
     FROM '../../data/raw/olist_customers_dataset.csv') AS unique_customers,
    (SELECT ROUND(AVG(order_total), 2) FROM (
        SELECT order_id, SUM(price) AS order_total
        FROM '../../data/raw/olist_order_items_dataset.csv'
        GROUP BY order_id)) AS avg_order_value,
    (SELECT ROUND(AVG(item_cnt), 2) FROM (
        SELECT order_id, COUNT(*) AS item_cnt
        FROM '../../data/raw/olist_order_items_dataset.csv'
        GROUP BY order_id)) AS avg_items_per_order;
