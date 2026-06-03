import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL = "claude-opus-4-8"
PORT = 5050
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "cortex.db")

# Confidence routing thresholds (Release 1 — Dynamic Taxonomy)
HIGH_CONFIDENCE = 0.80   # >= this → assign to existing type directly
LOW_CONFIDENCE  = 0.20   # <  this → create new type (if Corty suggests one)
                         # between HIGH and LOW → route to Unknown staging

KNOWN_PROJECTS = [
    "CORTEX",
    "Marketpulse",
    "TrueRating",
    "ClearCart",
    "MicroManga",
]

SCRAPER_TIMEOUT = 10
REMINDER_POLL_INTERVAL = 60
