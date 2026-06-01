import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL = "claude-opus-4-8"
PORT = 5050
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "cortex.db")

CONFIDENCE_THRESHOLD = 0.70

KNOWN_PROJECTS = [
    "CORTEX",
    "Marketpulse",
    "TrueRating",
    "ClearCart",
    "MicroManga",
]

CONTENT_TYPES = {
    "job_post":     {"icon": "💼", "color": "#4A90E2", "label": "Job Post"},
    "product_idea": {"icon": "💡", "color": "#7B61FF", "label": "Idea"},
    "reminder":     {"icon": "⏰", "color": "#E8834A", "label": "Reminder"},
    "learning":     {"icon": "🧠", "color": "#2E9E6B", "label": "Learning"},
    "blog_post":    {"icon": "📰", "color": "#E8600A", "label": "Blog & Post"},
    "general_note": {"icon": "📝", "color": "#5A9E6F", "label": "Note"},
    "unclassified": {"icon": "❓", "color": "#9B9B9B", "label": "Unclear"},
}

SCRAPER_TIMEOUT = 10
REMINDER_POLL_INTERVAL = 60
