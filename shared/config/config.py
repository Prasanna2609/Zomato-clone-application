import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

"""
Backend-wide configuration for dataset locations and identifiers.

This module intentionally stays lightweight and free of side effects so it can
be safely imported from both scripts and library code.
"""


PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Hugging Face dataset identifier for the raw Zomato dataset
ZOMATO_DATASET_ID = "ManikaSaini/zomato-restaurant-recommendation"

# Directory for storing any local data artifacts produced by Phase 1
DATA_DIR = PROJECT_ROOT / "data"

# Path to the cleaned Zomato dataset (Parquet for typed columns and list values)
ZOMATO_CLEAN_PARQUET_PATH = DATA_DIR / "zomato_cleaned.parquet"

# LLM Configuration
USE_LLM_EXPLANATIONS = os.getenv("USE_LLM_EXPLANATIONS", "false").lower() == "true"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "mixtral-8x7b-32768")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# CORS configuration
ALLOWED_ORIGINS_RAW = os.getenv("ALLOWED_ORIGINS", "*")
if ALLOWED_ORIGINS_RAW == "*":
    ALLOWED_ORIGINS = ["*"]
else:
    ALLOWED_ORIGINS = [o.strip() for o in ALLOWED_ORIGINS_RAW.split(",") if o.strip()]

# Fallback to local deterministic explanations if LLM fails or is disabled.

