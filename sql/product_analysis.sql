-- MarketLens: Product Performance & Category Analytics
-- Purpose: Evaluate product ratings, returns risk, and size economics

-- 1. Category Review Score & Volume Matrix
SELECT 
    COALESCE(t.product_category_name_english, p.product_category_name, 'Uncategorized') AS category_name,
    COUNT(DISTINCT oi.order_id) AS total_orders,
    ROUND(AVG(r.review_score)::NUMERIC, 2) AS avg_review_score,
    COUNT(CASE WHEN r.review_score <= 2 THEN 1 END) AS low_rated_reviews,
    ROUND((COUNT(CASE WHEN r.review_score <= 2 THEN 1 END)::NUMERIC / COUNT(r.review_score) * 100), 2) AS bad_review_pct
FROM products p
JOIN order_items oi ON p.product_id = oi.product_id
JOIN order_reviews r ON oi.order_id = r.order_id
LEFT JOIN product_category_translation t ON p.product_category_name = t.product_category_name
GROUP BY 1
HAVING COUNT(DISTINCT oi.order_id) >= 100
ORDER BY avg_review_score ASC
LIMIT 15;


-- 2. Weight vs Freight Cost Correlation Matrix
SELECT 
    CASE 
        WHEN p.product_weight_g < 500 THEN '1. Light (< 500g)'
        WHEN p.product_weight_g BETWEEN 500 AND 2000 THEN '2. Medium (500g - 2kg)'
        WHEN p.product_weight_g BETWEEN 2000 AND 5000 THEN '3. Heavy (2kg - 5kg)'
        ELSE '4. Very Heavy (> 5kg)'
    END AS weight_tier,
    COUNT(oi.order_item_id) AS total_items_sold,
    ROUND(AVG(oi.price)::NUMERIC, 2) AS avg_item_price,
    ROUND(AVG(oi.freight_value)::NUMERIC, 2) AS avg_freight_cost,
    ROUND((AVG(oi.freight_value) / NULLIF(AVG(oi.price), 0) * 100)::NUMERIC, 2) AS freight_to_price_ratio_pct
FROM products p
JOIN order_items oi ON p.product_id = oi.product_id
WHERE p.product_weight_g IS NOT NULL
GROUP BY 1
ORDER BY 1;