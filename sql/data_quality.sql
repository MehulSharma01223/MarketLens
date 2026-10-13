-- MarketLens: Data Quality & Integrity Audit
-- Purpose: Verify completeness, uniqueness, and consistency

-- 1. Check for Duplicate Primary Keys
SELECT 'orders' AS table_name, COUNT(*) - COUNT(DISTINCT order_id) AS duplicate_count FROM orders
UNION ALL
SELECT 'customers', COUNT(*) - COUNT(DISTINCT customer_id) FROM customers
UNION ALL
SELECT 'products', COUNT(*) - COUNT(DISTINCT product_id) FROM products
UNION ALL
SELECT 'sellers', COUNT(*) - COUNT(DISTINCT seller_id) FROM sellers;


-- 2. Check for Missing Critical Values in Delivered Orders
SELECT 
    COUNT(CASE WHEN order_purchase_timestamp IS NULL THEN 1 END) AS null_purchase_date,
    COUNT(CASE WHEN order_delivered_customer_date IS NULL THEN 1 END) AS null_delivered_date,
    COUNT(CASE WHEN order_estimated_delivery_date IS NULL THEN 1 END) AS null_estimated_date
FROM orders
WHERE order_status = 'delivered';


-- 3. Check for Orphan Records (Referential Integrity)
SELECT COUNT(*) AS orphan_order_items
FROM order_items oi
LEFT JOIN orders o ON oi.order_id = o.order_id
WHERE o.order_id IS NULL;


-- 4. Check for Business Logic Violations (Negative Values & Timing Inconsistencies)
SELECT 
    COUNT(CASE WHEN price <= 0 THEN 1 END) AS invalid_prices,
    COUNT(CASE WHEN freight_value < 0 THEN 1 END) AS invalid_freights
FROM order_items;

SELECT 
    COUNT(*) AS delivered_before_purchase
FROM orders
WHERE order_delivered_customer_date < order_purchase_timestamp;