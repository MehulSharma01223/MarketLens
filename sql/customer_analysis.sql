-- MarketLens: E-Commerce Analytics Engine
-- Phase 4: Customer Distribution & Retention Metrics

-- 1. Repeat Purchase Rate (Customer Level Retention)
WITH customer_order_counts AS (
    SELECT 
        c.customer_unique_id,
        COUNT(DISTINCT o.order_id) AS total_orders
    FROM customers c
    JOIN orders o ON c.customer_id = o.customer_id
    WHERE o.order_status = 'delivered'
    GROUP BY c.customer_unique_id
)
SELECT 
    COUNT(*) AS total_unique_customers,
    COUNT(CASE WHEN total_orders > 1 THEN 1 END) AS repeat_customers,
    ROUND(
        (COUNT(CASE WHEN total_orders > 1 THEN 1 END)::NUMERIC / COUNT(*) * 100), 
        2
    ) AS repeat_purchase_rate_pct
FROM customer_order_counts;


-- 2. State-Wise Customer Revenue & Order Volume
SELECT 
    c.customer_state,
    COUNT(DISTINCT o.order_id) AS total_orders,
    COUNT(DISTINCT c.customer_unique_id) AS unique_customers,
    ROUND(SUM(oi.price)::NUMERIC, 2) AS total_spend,
    ROUND(AVG(oi.price)::NUMERIC, 2) AS avg_item_price
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
JOIN order_items oi ON o.order_id = oi.order_id
WHERE o.order_status = 'delivered'
GROUP BY c.customer_state
ORDER BY total_spend DESC
LIMIT 10;


-- 3. Delivery Speed & SLA Delay Analysis by Top 5 States
SELECT 
    c.customer_state,
    ROUND(AVG(EXTRACT(EPOCH FROM (o.order_delivered_customer_date::timestamp - o.order_purchase_timestamp::timestamp)) / 86400)::NUMERIC, 1) AS avg_delivery_days,
    ROUND(AVG(EXTRACT(EPOCH FROM (o.order_estimated_delivery_date::timestamp - o.order_delivered_customer_date::timestamp)) / 86400)::NUMERIC, 1) AS avg_days_ahead_of_estimate,
    COUNT(CASE WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date THEN 1 END) AS delayed_orders,
    ROUND(
        (COUNT(CASE WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date THEN 1 END)::NUMERIC / COUNT(*) * 100),
        2
    ) AS delay_rate_pct
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
WHERE o.order_status = 'delivered'
  AND o.order_delivered_customer_date IS NOT NULL
GROUP BY c.customer_state
ORDER BY COUNT(o.order_id) DESC
LIMIT 5;