"""
MarketLens: Feature Engineering Pipeline
Purpose: Create delivery delay flags, temporal features, and order metrics.
"""

import pandas as pd

def engineer_order_features(df):
    print("[Feature Engineering] Processing features...")
    
    # Create delivery delay flag if date columns exist
    if 'order_delivered_customer_date' in df.columns and 'order_estimated_delivery_date' in df.columns:
        df['is_delayed'] = (
            df['order_delivered_customer_date'] > df['order_estimated_delivery_date']
        ).astype(int)
    
    # Extract temporal features from purchase timestamp
    if 'order_purchase_timestamp' in df.columns:
        df['order_purchase_timestamp'] = pd.to_datetime(df['order_purchase_timestamp'])
        df['purchase_month'] = df['order_purchase_timestamp'].dt.month
        df['purchase_dow'] = df['order_purchase_timestamp'].dt.dayofweek
        df['purchase_hour'] = df['order_purchase_timestamp'].dt.hour
        
    print("[Feature Engineering] Features generated successfully!")
    return df