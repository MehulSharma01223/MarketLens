"""
MarketLens: Interactive E-Commerce Analytics Dashboard
Phase 5: Streamlit Application
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import text
from db_connection import get_db_engine

st.set_page_config(page_title="MarketLens Analytics", layout="wide")

st.title("📊 MarketLens: E-Commerce Executive Dashboard")
st.markdown("PostgreSQL Analytics & Business Intelligence Engine")

engine = get_db_engine()

# --- Section 1: KPI Summary ---
st.subheader("1. Core Performance Metrics")
kpi_query = """
SELECT 
    COUNT(DISTINCT o.order_id) AS total_orders,
    COUNT(oi.order_item_id) AS total_items,
    ROUND(SUM(oi.price)::NUMERIC, 2) AS total_revenue,
    ROUND(AVG(order_totals.order_val)::NUMERIC, 2) AS avg_order_val
FROM orders o
JOIN order_items oi ON o.order_id = oi.order_id
JOIN (
    SELECT order_id, SUM(price + freight_value) AS order_val
    FROM order_items
    GROUP BY order_id
) order_totals ON o.order_id = order_totals.order_id
WHERE o.order_status = 'delivered';
"""

with engine.connect() as conn:
    kpi_df = pd.read_sql_query(text(kpi_query), conn)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Delivered Orders", f"{kpi_df['total_orders'][0]:,}")
col2.metric("Total Items Sold", f"{kpi_df['total_items'][0]:,}")
col3.metric("Total Net Revenue", f"${kpi_df['total_revenue'][0]:,.2f}")
col4.metric("Average Order Value (AOV)", f"${kpi_df['avg_order_val'][0]:,.2f}")

st.divider()

# --- Section 2: Monthly Revenue & Growth Trend ---
st.subheader("2. Revenue Dynamics (Monthly Trend)")
revenue_query = """
WITH monthly_metrics AS (
    SELECT 
        TO_CHAR(DATE_TRUNC('month', o.order_purchase_timestamp), 'YYYY-MM') AS sales_month,
        ROUND(SUM(oi.price)::NUMERIC, 2) AS monthly_revenue
    FROM orders o
    JOIN order_items oi ON o.order_id = oi.order_id
    WHERE o.order_status = 'delivered'
    GROUP BY 1
)
SELECT sales_month, monthly_revenue
FROM monthly_metrics
ORDER BY sales_month;
"""

with engine.connect() as conn:
    rev_df = pd.read_sql_query(text(revenue_query), conn)

fig_rev = px.line(
    rev_df,
    x="sales_month",
    y="monthly_revenue",
    markers=True,
    title="Monthly Revenue Trend (Delivered Orders)",
    labels={"sales_month": "Month", "monthly_revenue": "Revenue ($)"}
)
fig_rev.update_traces(line_color="#1f77b4", line_width=3)
st.plotly_chart(fig_rev, use_container_width=True)

st.divider()

# --- Section 3: Categories & RFM Distribution ---
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("3. Top 10 Product Categories by Revenue")
    cat_query = """
    SELECT 
        COALESCE(t.product_category_name_english, p.product_category_name, 'Uncategorized') AS category_name,
        ROUND(SUM(oi.price)::NUMERIC, 2) AS category_revenue
    FROM order_items oi
    JOIN products p ON oi.product_id = p.product_id
    LEFT JOIN product_category_translation t ON p.product_category_name = t.product_category_name
    JOIN orders o ON oi.order_id = o.order_id
    WHERE o.order_status = 'delivered'
    GROUP BY 1
    ORDER BY category_revenue DESC
    LIMIT 10;
    """
    with engine.connect() as conn:
        cat_df = pd.read_sql_query(text(cat_query), conn)
    
    fig_cat = px.bar(
        cat_df,
        x="category_revenue",
        y="category_name",
        orientation="h",
        title="Top 10 Categories",
        labels={"category_revenue": "Revenue ($)", "category_name": "Category"},
        color="category_revenue",
        color_continuous_scale="Blues"
    )
    fig_cat.update_layout(yaxis=dict(autorange="reversed"))
    st.plotly_chart(fig_cat, use_container_width=True)

with col_right:
    st.subheader("4. RFM Customer Segments")
    rfm_query = """
    WITH reference_date AS (
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
            monetary_value,
            NTILE(5) OVER (ORDER BY recency_days DESC) AS r_score,
            NTILE(5) OVER (ORDER BY frequency ASC) AS f_score,
            NTILE(5) OVER (ORDER BY monetary_value ASC) AS m_score
        FROM customer_rfm_raw
    ),
    customer_segments AS (
        SELECT 
            customer_unique_id,
            monetary_value,
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
    SELECT 
        segment,
        COUNT(customer_unique_id) AS customer_count,
        ROUND(SUM(monetary_value)::NUMERIC, 2) AS total_segment_revenue
    FROM customer_segments
    GROUP BY segment
    ORDER BY total_segment_revenue DESC;
    """
    with engine.connect() as conn:
        rfm_df = pd.read_sql_query(text(rfm_query), conn)

    fig_rfm = px.pie(
        rfm_df,
        values="total_segment_revenue",
        names="segment",
        title="Revenue Distribution by RFM Segment",
        hole=0.4
    )
    st.plotly_chart(fig_rfm, use_container_width=True)