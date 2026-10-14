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

# --- Section 5: Machine Learning Delivery Delay Predictor ---
st.divider()
st.subheader("5. 🤖 Predictive Analytics: Order Delivery Delay Predictor")
st.markdown("Enter order details to predict whether it will be delivered on time or delayed.")

import joblib
from pathlib import Path

MODEL_DIR = Path(__file__).resolve().parent.parent / "models"
try:
    model = joblib.load(MODEL_DIR / "delivery_delay_model.pkl")
    le_cust = joblib.load(MODEL_DIR / "le_customer_state.pkl")
    le_sell = joblib.load(MODEL_DIR / "le_seller_state.pkl")
    
    col_p1, col_p2, col_p3 = st.columns(3)
    with col_p1:
        p_price = st.number_input("Product Price ($)", min_value=1.0, value=100.0)
        p_freight = st.number_input("Freight Value ($)", min_value=0.0, value=20.0)
        p_weight = st.number_input("Product Weight (g)", min_value=10.0, value=1000.0)
    with col_p2:
        p_len = st.number_input("Length (cm)", min_value=1.0, value=30.0)
        p_height = st.number_input("Height (cm)", min_value=1.0, value=10.0)
        p_width = st.number_input("Width (cm)", min_value=1.0, value=20.0)
    with col_p3:
        cust_st = st.selectbox("Customer State", le_cust.classes_)
        sell_st = st.selectbox("Seller State", le_sell.classes_)
        p_month = st.slider("Purchase Month", 1, 12, 6)
        p_dow = st.slider("Purchase Day of Week (0=Mon)", 0, 6, 2)

    if st.button("Predict Delay Risk"):
        # Encode categorical inputs safely
        c_enc = le_cust.transform([cust_st])[0] if cust_st in le_cust.classes_ else 0
        s_enc = le_sell.transform([sell_st])[0] if sell_st in le_sell.classes_ else 0
        
        input_data = [[
            p_price, p_freight, p_weight, p_len, p_height, p_width,
            c_enc, s_enc, p_month, p_dow
        ]]
        
        prediction = model.predict(input_data)[0]
        probability = model.predict_proba(input_data)[0][1]
        
        if prediction == 1:
            st.error(f"⚠️ High Risk: This order is predicted to be **DELAYED**! (Probability: {probability:.1%})")
        else:
            st.success(f"✅ Low Risk: This order is predicted to be delivered **ON TIME**. (Delay Probability: {probability:.1%})")
            
except Exception as e:
    st.warning(f"Model files not found or failed to load. Make sure `train_delay_model.py` has been run successfully. Error: {e}")