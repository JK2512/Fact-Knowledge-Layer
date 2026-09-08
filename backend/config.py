"""
Configuration management for the Fact Knowledge Layer.
Handles API keys, mode selection, and extraction parameters.
"""

import os
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "facts.db"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)

# ── LLM Configuration ─────────────────────────────────────────────────────────
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

def is_llm_available() -> bool:
    """Check whether a Google API key is configured."""
    return bool(GOOGLE_API_KEY)

def get_extraction_mode() -> str:
    """Return 'llm' if an API key is present, otherwise 'rule_based'."""
    return "llm" if is_llm_available() else "rule_based"

# ── Extraction Parameters ──────────────────────────────────────────────────────
# Minimum confidence threshold for keeping a fact
MIN_CONFIDENCE = 0.3

# Maximum number of characters per page chunk sent to the LLM
LLM_CHUNK_SIZE = 6000

# How many surrounding characters to capture as source context
CONTEXT_WINDOW = 300

# Similarity thresholds for cross-document matching
SUBJECT_SIMILARITY_THRESHOLD = 0.55
PREDICATE_SIMILARITY_THRESHOLD = 0.50
VALUE_TOLERANCE_PERCENT = 5.0  # values within 5% are considered matching
