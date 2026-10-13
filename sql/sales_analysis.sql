-- Phase 4: Sales Performance & Revenue Dynamics

-- 1. High-Level KPI Summary (Total Revenue, Total Orders, Total Items, Overall AOV)
SELECT 
    COUNT(DISTINCT o.order_id) AS total_orders,
    COUNT(oi.order_item_id) AS total_items_sold,
    ROUND(SUM(oi.price)::NUMERIC, 2) AS total_item_revenue,
    ROUND(SUM(oi.freight_value)::NUMERIC, 2) AS total_freight_value,
    ROUND(SUM(oi.price + oi.freight_value)::NUMERIC, 2) AS gross_sales_value,
    ROUND(AVG(order_totals.order_val)::NUMERIC, 2) AS avg_order_value
FROM orders o
JOIN order_items oi ON o.order_id = oi.order_id
JOIN (
    SELECT order_id, SUM(price + freight_value) AS order_val
    FROM order_items
    GROUP BY order_id
) order_totals ON o.order_id = order_totals.order_id
WHERE o.order_status = 'delivered';


-- 2. Monthly Revenue Trend & Month-over-Month (MoM) Growth Rate
WITH monthly_metrics AS (
    SELECT 
        TO_CHAR(DATE_TRUNC('month', o.order_purchase_timestamp), 'YYYY-MM') AS sales_month,
        COUNT(DISTINCT o.order_id) AS total_orders,
        ROUND(SUM(oi.price)::NUMERIC, 2) AS monthly_revenue
    FROM orders o
    JOIN order_items oi ON o.order_id = oi.order_id
    WHERE o.order_status = 'delivered'
    GROUP BY 1
)
SELECT 
    sales_month,
    total_orders,
    monthly_revenue,
    LAG(monthly_revenue, 1) OVER (ORDER BY sales_month) AS prev_month_revenue,
    ROUND(
        ((monthly_revenue - LAG(monthly_revenue, 1) OVER (ORDER BY sales_month)) 
        / NULLIF(LAG(monthly_revenue, 1) OVER (ORDER BY sales_month), 0) * 100)::NUMERIC, 
        2
    ) AS mom_growth_pct
FROM monthly_metrics
ORDER BY sales_month;


-- 3. Top 10 Product Categories by Revenue & Volume Share
WITH category_sales AS (
    SELECT 
        COALESCE(t.product_category_name_english, p.product_category_name, 'Uncategorized') AS category_name,
        COUNT(oi.order_item_id) AS total_units_sold,
        ROUND(SUM(oi.price)::NUMERIC, 2) AS category_revenue
    FROM order_items oi
    JOIN products p ON oi.product_id = p.product_id
    LEFT JOIN product_category_translation t ON p.product_category_name = t.product_category_name
    JOIN orders o ON oi.order_id = o.order_id
    WHERE o.order_status = 'delivered'
    GROUP BY 1
),
total_pool AS (
    SELECT SUM(category_revenue) AS grand_total_revenue FROM category_sales
)
SELECT 
    cs.category_name,
    cs.total_units_sold,
    cs.category_revenue,
    ROUND((cs.category_revenue / tp.grand_total_revenue * 100)::NUMERIC, 2) AS revenue_contribution_pct
FROM category_sales cs
CROSS JOIN total_pool tp
ORDER BY cs.category_revenue DESC
LIMIT 10;