-- ============================================================================
-- 03 RFM 用户分层：打分 → 分群 → 分群贡献统计
-- ----------------------------------------------------------------------------
-- 对应产出：notebooks/03_rfm_analysis.ipynb 的纯 SQL 复刻
-- 口径说明：
--   * 用户身份：customer_unique_id（真实用户，绝不能用订单级的 customer_id）
--   * 订单口径：仅 order_status = 'delivered'
--   * 参考日期：数据集中最后购买日 + 1 天（与 notebook 一致）
--   * 打分方法：五分位分箱，完整复现 pandas qcut(duplicates='drop') 语义——
--     当某一维度分位点重合时自动并箱（如 97% 用户 frequency=1，
--     F 的 4 个切点全部退化为 1，最终并成 1 个箱，全体 F 得分 = 1）
--   * 分群方法：中位数阈值法（得分 >= 该维度中位数 => "高"），8 群
-- SQL 技术点：
--   * 多层 CTE 链：reference_date → customer_orders → rfm_base → cuts
--     → scored → thresholds → segmented（每段查询独立自洽，可单独执行）
--   * QUANTILE_CONT 分位数 + CASE WHEN 链实现分箱打分
--   * MEDIAN() + CROSS JOIN 阈值 + CASE WHEN 分群
--   * 聚合窗口函数：SUM(COUNT(*)) OVER () 算分群人数占比 / GMV 占比
-- 运行方式：在 sql_and_bi/sql_work/ 目录下，用本目录的 sql_workbook.ipynb
--           逐段执行；每段以 "-- QUERY:" 开头的注释分隔
-- ============================================================================

-- QUERY: 03-1 RFM 基础表规模与描述统计（用户级聚合）
WITH reference_date AS (
    SELECT MAX(CAST(order_purchase_timestamp AS DATE)) + INTERVAL '1 day' AS today
    FROM '../../data/raw/olist_orders_dataset.csv'
),
customer_orders AS (
    SELECT
        c.customer_unique_id,
        o.order_id,
        CAST(o.order_purchase_timestamp AS DATE) AS purchase_date,
        SUM(oi.price) AS order_amount
    FROM '../../data/raw/olist_customers_dataset.csv' c
    JOIN '../../data/raw/olist_orders_dataset.csv' o
        ON c.customer_id = o.customer_id
    JOIN '../../data/raw/olist_order_items_dataset.csv' oi
        ON o.order_id = oi.order_id
    WHERE o.order_status = 'delivered'
    GROUP BY c.customer_unique_id, o.order_id, purchase_date
),
rfm_base AS (
    SELECT
        customer_unique_id,
        DATEDIFF('day', MAX(purchase_date), (SELECT today FROM reference_date)) AS recency,
        COUNT(DISTINCT order_id) AS frequency,
        ROUND(SUM(order_amount), 2) AS monetary
    FROM customer_orders
    GROUP BY customer_unique_id
)
SELECT
    COUNT(*)                   AS user_cnt,
    ROUND(AVG(recency), 2)     AS avg_recency,
    MEDIAN(recency)            AS median_recency,
    MIN(recency)               AS min_recency,
    MAX(recency)               AS max_recency,
    ROUND(AVG(frequency), 2)   AS avg_frequency,
    MEDIAN(frequency)          AS median_frequency,
    MAX(frequency)             AS max_frequency,
    ROUND(AVG(monetary), 2)    AS avg_monetary,
    MEDIAN(monetary)           AS median_monetary,
    MAX(monetary)              AS max_monetary
FROM rfm_base;

-- QUERY: 03-2 五分位切点（观察 frequency 切点退化：4 个切点全部 = 1）
WITH reference_date AS (
    SELECT MAX(CAST(order_purchase_timestamp AS DATE)) + INTERVAL '1 day' AS today
    FROM '../../data/raw/olist_orders_dataset.csv'
),
customer_orders AS (
    SELECT
        c.customer_unique_id,
        o.order_id,
        CAST(o.order_purchase_timestamp AS DATE) AS purchase_date,
        SUM(oi.price) AS order_amount
    FROM '../../data/raw/olist_customers_dataset.csv' c
    JOIN '../../data/raw/olist_orders_dataset.csv' o
        ON c.customer_id = o.customer_id
    JOIN '../../data/raw/olist_order_items_dataset.csv' oi
        ON o.order_id = oi.order_id
    WHERE o.order_status = 'delivered'
    GROUP BY c.customer_unique_id, o.order_id, purchase_date
),
rfm_base AS (
    SELECT
        customer_unique_id,
        DATEDIFF('day', MAX(purchase_date), (SELECT today FROM reference_date)) AS recency,
        COUNT(DISTINCT order_id) AS frequency,
        ROUND(SUM(order_amount), 2) AS monetary
    FROM customer_orders
    GROUP BY customer_unique_id
)
SELECT
    QUANTILE_CONT(recency,   0.2) AS r_q20, QUANTILE_CONT(recency,   0.4) AS r_q40,
    QUANTILE_CONT(recency,   0.6) AS r_q60, QUANTILE_CONT(recency,   0.8) AS r_q80,
    QUANTILE_CONT(frequency, 0.2) AS f_q20, QUANTILE_CONT(frequency, 0.4) AS f_q40,
    QUANTILE_CONT(frequency, 0.6) AS f_q60, QUANTILE_CONT(frequency, 0.8) AS f_q80,
    QUANTILE_CONT(monetary,  0.2) AS m_q20, QUANTILE_CONT(monetary,  0.4) AS m_q40,
    QUANTILE_CONT(monetary,  0.6) AS m_q60, QUANTILE_CONT(monetary,  0.8) AS m_q80
FROM rfm_base;

-- QUERY: 03-3 RFM 打分（分位数分箱）与各维度得分分布
-- 打分算法（与 pandas qcut duplicates='drop' 完全等价）：
--   切点序列 e0=min, e1..e4=五个分位点, e5=max；去重后严格递增；
--   箱号 = 严格小于当前值的"去重切点"个数（e0=min 不计入，因 min 恒不 < x）；
--   F/M 得分 = 箱号 + 1；R 反向（最近购买 = 高分）= 总箱数 - 箱号。
WITH reference_date AS (
    SELECT MAX(CAST(order_purchase_timestamp AS DATE)) + INTERVAL '1 day' AS today
    FROM '../../data/raw/olist_orders_dataset.csv'
),
customer_orders AS (
    SELECT
        c.customer_unique_id,
        o.order_id,
        CAST(o.order_purchase_timestamp AS DATE) AS purchase_date,
        SUM(oi.price) AS order_amount
    FROM '../../data/raw/olist_customers_dataset.csv' c
    JOIN '../../data/raw/olist_orders_dataset.csv' o
        ON c.customer_id = o.customer_id
    JOIN '../../data/raw/olist_order_items_dataset.csv' oi
        ON o.order_id = oi.order_id
    WHERE o.order_status = 'delivered'
    GROUP BY c.customer_unique_id, o.order_id, purchase_date
),
rfm_base AS (
    SELECT
        customer_unique_id,
        DATEDIFF('day', MAX(purchase_date), (SELECT today FROM reference_date)) AS recency,
        COUNT(DISTINCT order_id) AS frequency,
        ROUND(SUM(order_amount), 2) AS monetary
    FROM customer_orders
    GROUP BY customer_unique_id
),
cuts AS (
    SELECT
        MIN(recency)   AS r_e0, QUANTILE_CONT(recency, 0.2)   AS r_e1, QUANTILE_CONT(recency, 0.4) AS r_e2,
        QUANTILE_CONT(recency, 0.6) AS r_e3, QUANTILE_CONT(recency, 0.8) AS r_e4, MAX(recency) AS r_e5,
        MIN(frequency) AS f_e0, QUANTILE_CONT(frequency, 0.2) AS f_e1, QUANTILE_CONT(frequency, 0.4) AS f_e2,
        QUANTILE_CONT(frequency, 0.6) AS f_e3, QUANTILE_CONT(frequency, 0.8) AS f_e4, MAX(frequency) AS f_e5,
        MIN(monetary)  AS m_e0, QUANTILE_CONT(monetary, 0.2)  AS m_e1, QUANTILE_CONT(monetary, 0.4) AS m_e2,
        QUANTILE_CONT(monetary, 0.6) AS m_e3, QUANTILE_CONT(monetary, 0.8) AS m_e4, MAX(monetary) AS m_e5
    FROM rfm_base
),
scored AS (
    SELECT
        b.customer_unique_id,
        -- R：箱号 = 去重切点中严格小于 recency 的个数（e0 恒不 < x，只需数 e1..e5）
        (CASE WHEN c.r_e1 < b.recency AND c.r_e1 > c.r_e0 THEN 1 ELSE 0 END
       + CASE WHEN c.r_e2 < b.recency AND c.r_e2 > c.r_e1 THEN 1 ELSE 0 END
       + CASE WHEN c.r_e3 < b.recency AND c.r_e3 > c.r_e2 THEN 1 ELSE 0 END
       + CASE WHEN c.r_e4 < b.recency AND c.r_e4 > c.r_e3 THEN 1 ELSE 0 END
       + CASE WHEN c.r_e5 < b.recency AND c.r_e5 > c.r_e4 THEN 1 ELSE 0 END) AS r_bin,
        -- 总箱数 = 去重后相邻切点的"上升"次数
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
    FROM rfm_base b
    CROSS JOIN cuts c
),
final_scores AS (
    SELECT
        customer_unique_id,
        r_bins - r_bin AS R_score,   -- R 反向：最近购买 => 高分
        f_bin + 1      AS F_score,
        m_bin + 1      AS M_score
    FROM scored
)
SELECT 'R (Recency)'  AS dim, R_score AS score, COUNT(*) AS user_cnt FROM final_scores GROUP BY 2
UNION ALL
SELECT 'F (Frequency)', F_score, COUNT(*) FROM final_scores GROUP BY 2
UNION ALL
SELECT 'M (Monetary)',  M_score, COUNT(*) FROM final_scores GROUP BY 2
ORDER BY dim, score;

-- QUERY: 03-4 RFM 分群统计（中位数阈值法 + 窗口函数算人数/GMV 占比）
-- 与 notebook 完全一致的 8 群定义：
--   R高F高M高=Champions | R高F高M低=Loyal | R高F低M高=Potential Loyalists
--   R高F低M低=New | R低F高M高=At Risk | R低F高M低=Hibernating
--   R低F低M高=Promising | R低F低M低=Lost
-- 注：本数据集 97% 用户只买 1 次 => F 中位数 = 1 => "F高"对全体成立，
--     实际只有 4 个群体非空（与 notebook 结果一致）
WITH reference_date AS (
    SELECT MAX(CAST(order_purchase_timestamp AS DATE)) + INTERVAL '1 day' AS today
    FROM '../../data/raw/olist_orders_dataset.csv'
),
customer_orders AS (
    SELECT
        c.customer_unique_id,
        o.order_id,
        CAST(o.order_purchase_timestamp AS DATE) AS purchase_date,
        SUM(oi.price) AS order_amount
    FROM '../../data/raw/olist_customers_dataset.csv' c
    JOIN '../../data/raw/olist_orders_dataset.csv' o
        ON c.customer_id = o.customer_id
    JOIN '../../data/raw/olist_order_items_dataset.csv' oi
        ON o.order_id = oi.order_id
    WHERE o.order_status = 'delivered'
    GROUP BY c.customer_unique_id, o.order_id, purchase_date
),
rfm_base AS (
    SELECT
        customer_unique_id,
        DATEDIFF('day', MAX(purchase_date), (SELECT today FROM reference_date)) AS recency,
        COUNT(DISTINCT order_id) AS frequency,
        ROUND(SUM(order_amount), 2) AS monetary
    FROM customer_orders
    GROUP BY customer_unique_id
),
cuts AS (
    SELECT
        MIN(recency)   AS r_e0, QUANTILE_CONT(recency, 0.2)   AS r_e1, QUANTILE_CONT(recency, 0.4) AS r_e2,
        QUANTILE_CONT(recency, 0.6) AS r_e3, QUANTILE_CONT(recency, 0.8) AS r_e4, MAX(recency) AS r_e5,
        MIN(frequency) AS f_e0, QUANTILE_CONT(frequency, 0.2) AS f_e1, QUANTILE_CONT(frequency, 0.4) AS f_e2,
        QUANTILE_CONT(frequency, 0.6) AS f_e3, QUANTILE_CONT(frequency, 0.8) AS f_e4, MAX(frequency) AS f_e5,
        MIN(monetary)  AS m_e0, QUANTILE_CONT(monetary, 0.2)  AS m_e1, QUANTILE_CONT(monetary, 0.4) AS m_e2,
        QUANTILE_CONT(monetary, 0.6) AS m_e3, QUANTILE_CONT(monetary, 0.8) AS m_e4, MAX(monetary) AS m_e5
    FROM rfm_base
),
scored AS (
    SELECT
        b.*,
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
    FROM rfm_base b
    CROSS JOIN cuts c
),
final_scores AS (
    SELECT
        customer_unique_id, recency, frequency, monetary,
        r_bins - r_bin AS R_score,
        f_bin + 1      AS F_score,
        m_bin + 1      AS M_score
    FROM scored
),
thresholds AS (
    SELECT MEDIAN(R_score) AS r_med, MEDIAN(F_score) AS f_med, MEDIAN(M_score) AS m_med
    FROM final_scores
),
segmented AS (
    SELECT
        f.*,
        CASE
            WHEN f.R_score >= t.r_med AND f.F_score >= t.f_med AND f.M_score >= t.m_med THEN 'Champions（冠军用户）'
            WHEN f.R_score >= t.r_med AND f.F_score >= t.f_med AND f.M_score <  t.m_med THEN 'Loyal Customers（忠诚用户）'
            WHEN f.R_score >= t.r_med AND f.F_score <  t.f_med AND f.M_score >= t.m_med THEN 'Potential Loyalists（潜力忠诚）'
            WHEN f.R_score >= t.r_med AND f.F_score <  t.f_med AND f.M_score <  t.m_med THEN 'New Customers（新用户）'
            WHEN f.R_score <  t.r_med AND f.F_score >= t.f_med AND f.M_score >= t.m_med THEN 'At Risk（流失风险）'
            WHEN f.R_score <  t.r_med AND f.F_score >= t.f_med AND f.M_score <  t.m_med THEN 'Hibernating（休眠用户）'
            WHEN f.R_score <  t.r_med AND f.F_score <  t.f_med AND f.M_score >= t.m_med THEN 'Promising（有潜力）'
            ELSE 'Lost（已流失）'
        END AS segment
    FROM final_scores f
    CROSS JOIN thresholds t
)
SELECT
    segment,
    COUNT(*) AS user_cnt,
    ROUND(AVG(recency), 1)   AS avg_recency,
    ROUND(AVG(frequency), 2) AS avg_frequency,
    ROUND(AVG(monetary), 2)  AS avg_monetary,
    ROUND(SUM(monetary), 2)  AS total_gmv,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS user_pct,
    ROUND(SUM(monetary) * 100.0 / SUM(SUM(monetary)) OVER (), 2) AS gmv_pct
FROM segmented
GROUP BY segment
ORDER BY total_gmv DESC;

-- QUERY: 03-5 购买频次分布（验证"97% 用户只买 1 次"）
WITH reference_date AS (
    SELECT MAX(CAST(order_purchase_timestamp AS DATE)) + INTERVAL '1 day' AS today
    FROM '../../data/raw/olist_orders_dataset.csv'
),
customer_orders AS (
    SELECT
        c.customer_unique_id,
        o.order_id,
        CAST(o.order_purchase_timestamp AS DATE) AS purchase_date,
        SUM(oi.price) AS order_amount
    FROM '../../data/raw/olist_customers_dataset.csv' c
    JOIN '../../data/raw/olist_orders_dataset.csv' o
        ON c.customer_id = o.customer_id
    JOIN '../../data/raw/olist_order_items_dataset.csv' oi
        ON o.order_id = oi.order_id
    WHERE o.order_status = 'delivered'
    GROUP BY c.customer_unique_id, o.order_id, purchase_date
),
rfm_base AS (
    SELECT
        customer_unique_id,
        COUNT(DISTINCT order_id) AS frequency
    FROM customer_orders
    GROUP BY customer_unique_id
)
SELECT
    frequency,
    COUNT(*) AS user_cnt,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct
FROM rfm_base
GROUP BY frequency
ORDER BY frequency;
