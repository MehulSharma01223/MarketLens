"""
MarketLens: Centralized Configuration
Reads paths, API endpoints, and timeouts from environment variables.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = Path(os.getenv("MARKETLENS_MODEL_DIR", PROJECT_ROOT / "models"))
DATA_DIR = Path(os.getenv("MARKETLENS_DATA_DIR", PROJECT_ROOT / "data"))

MODEL_VERSION = os.getenv("MARKETLENS_MODEL_VERSION", "1.0.0")
MODEL_NAME = "RandomForestDeliveryDelayClassifier"

API_HOST = os.getenv("MARKETLENS_API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("MARKETLENS_API_PORT", "5000"))
API_BASE_URL = os.getenv("MARKETLENS_API_URL", f"http://{API_HOST}:{API_PORT}")
API_TIMEOUT = float(os.getenv("MARKETLENS_API_TIMEOUT", "5.0"))