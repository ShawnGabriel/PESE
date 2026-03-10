"""Centralized configuration — loaded once from environment and .env file."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = BASE_DIR / "pese.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

# AI provider
AI_PROVIDER = os.getenv("AI_PROVIDER", "openai")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ENRICHMENT_MODEL = os.getenv("ENRICHMENT_MODEL", "gpt-4o-mini")
SCORING_MODEL = os.getenv("SCORING_MODEL", "gpt-4o-mini")

# Scoring weights (must sum to 1.0)
SCORING_WEIGHTS = {
    "sector_fit": 0.35,
    "relationship_depth": 0.30,
    "halo_value": 0.20,
    "emerging_manager_fit": 0.15,
}

TIER_THRESHOLDS = [
    (8.0, "PRIORITY CLOSE"),
    (6.5, "STRONG FIT"),
    (5.0, "MODERATE FIT"),
    (0.0, "WEAK FIT"),
]

# Typical allocation to a single fund by org type
ALLOCATION_RANGES = {
    "Pension":              (0.005, 0.02),
    "Insurance":            (0.005, 0.02),
    "Endowment":            (0.01,  0.03),
    "Foundation":           (0.01,  0.03),
    "Fund of Funds":        (0.02,  0.05),
    "Multi-Family Office":  (0.02,  0.05),
    "Single Family Office": (0.03,  0.10),
    "HNWI":                 (0.03,  0.10),
    "Asset Manager":        (0.005, 0.03),
    "RIA/FIA":              (0.005, 0.03),
    "Private Capital Firm": (0.005, 0.03),
}

# Token costs per 1M tokens for cost estimation
TOKEN_COSTS = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o":      {"input": 2.50, "output": 10.00},
}

MAX_CONCURRENT_REQUESTS = 5
ENRICHMENT_BATCH_SIZE = 10
