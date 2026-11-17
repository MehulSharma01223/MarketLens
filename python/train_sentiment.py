"""
MarketLens: Customer Review Sentiment Model Training Script
Trains a TF-IDF + LogisticRegression model on order_reviews text messages.
"""

from pathlib import Path
import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from sqlalchemy import text
from db_connection import get_db_engine

CURRENT_DIR = Path(__file__).resolve().parent
MODEL_DIR = CURRENT_DIR.parent / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

def train_sentiment_model():
    engine = get_db_engine()
    
    query = """
    SELECT review_score, review_comment_message 
    FROM order_reviews 
    WHERE review_comment_message IS NOT NULL 
      AND TRIM(review_comment_message) != ''
    """
    
    with engine.connect() as conn:
        df = pd.read_sql_query(text(query), conn)
        
    def map_sentiment(score):
        if score >= 4:
            return 'Positive'
        elif score == 3:
            return 'Neutral'
        else:
            return 'Negative'
            
    df['sentiment'] = df['review_score'].apply(map_sentiment)
    
    X = df['review_comment_message']
    y = df['sentiment']
    
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    vectorizer = TfidfVectorizer(max_features=5000)
    X_train_vec = vectorizer.fit_transform(X_train)
    X_test_vec = vectorizer.transform(X_test)
    
    model = LogisticRegression(max_iter=1000, class_weight='balanced')
    model.fit(X_train_vec, y_train)
    
    preds = model.predict(X_test_vec)
    print("Classification Report:")
    print(classification_report(y_test, preds))
    
    joblib.dump(model, MODEL_DIR / "sentiment_model.pkl")
    joblib.dump(vectorizer, MODEL_DIR / "tfidf_vectorizer.pkl")
    print("Sentiment model and vectorizer saved successfully in models/ directory.")

if __name__ == "__main__":
    train_sentiment_model()