-- MarketLens: E-Commerce Analytics Engine
-- Phase 4: RFM (Recency, Frequency, Monetary) Segmentation

WITH reference_date AS (
    -- Reference baseline: 1 day after the latest order in the dataset
    SELECT (MAX(order_purchase_timestamp)::timestamp + INTERVAL '1 day') AS snapshot_date
    FROM orders
    WHERE order_status = 'delivered'
),
customer_rfm_raw AS (
    SELECT 
        c.customer_unique_id,
        ROUND(EXTRACT(EPOCH FROM (ref.snapshot_date - MAX(o.order_purchase_timestamp)::timestamp)) / 86400) AS recency_days,
        COUNT(DISTINCT o.order_id) AS frequency,
        ROUND(SUM(oi.price)::NUMERIC, 2) AS monetary_value
    FROM customers c
    JOIN orders o ON c.customer_id = o.customer_id
    JOIN order_items oi ON o.order_id = oi.order_id
    CROSS JOIN reference_date ref
    WHERE o.order_status = 'delivered'
    GROUP BY c.customer_unique_id, ref.snapshot_date
),
rfm_scores AS (
    SELECT 
        customer_unique_id,
        recency_days,
        frequency,
        monetary_value,
        -- Lower recency days = Higher R score (1 to 5)
        NTILE(5) OVER (ORDER BY recency_days DESC) AS r_score,
        -- Frequency distribution (most customers have 1 order, so NTILE handles ranking)
        NTILE(5) OVER (ORDER BY frequency ASC) AS f_score,
        -- Higher spend = Higher M score (1 to 5)
        NTILE(5) OVER (ORDER BY monetary_value ASC) AS m_score
    FROM customer_rfm_raw
),
customer_segments AS (
    SELECT 
        customer_unique_id,
        recency_days,
        frequency,
        monetary_value,
        r_score,
        f_score,
        m_score,
        CASE 
            WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN 'Champions'
            WHEN r_score >= 3 AND f_score >= 3 THEN 'Loyal Customers'
            WHEN r_score >= 4 AND f_score <= 2 THEN 'Recent New Customers'
            WHEN r_score <= 2 AND f_score >= 3 THEN 'At Risk / Churning High Value'
            WHEN r_score <= 2 AND f_score <= 2 AND m_score <= 2 THEN 'Lost Customers'
            ELSE 'Potential / Average Spenders'
        END AS segment
    FROM rfm_scores
)
-- 1. Segment-Level Aggregation & Value Contribution
SELECT 
    segment,
    COUNT(customer_unique_id) AS customer_count,
    ROUND((COUNT(customer_unique_id)::NUMERIC / (SELECT COUNT(*) FROM customer_segments) * 100), 2) AS pct_of_customers,
    ROUND(AVG(recency_days)::NUMERIC, 1) AS avg_recency_days,
    ROUND(AVG(frequency)::NUMERIC, 2) AS avg_frequency,
    ROUND(AVG(monetary_value)::NUMERIC, 2) AS avg_monetary_spend,
    ROUND(SUM(monetary_value)::NUMERIC, 2) AS total_segment_revenue
FROM customer_segments
GROUP BY segment
ORDER BY total_segment_revenue DESC;