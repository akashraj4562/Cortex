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

# Intent-based content types: classified by what the user will DO with the item
CONTENT_TYPES = {
    "job_application": {"icon": "💼", "color": "#4A90E2", "label": "Job Applications"},
    "food_for_thought": {"icon": "🍽️",  "color": "#E8600A", "label": "Food for Thought"},
    "build_better":    {"icon": "🔨", "color": "#7B61FF", "label": "Build Better"},
    "learning":        {"icon": "🧠", "color": "#2E9E6B", "label": "Learnings"},
    "interview_exp":   {"icon": "🎯", "color": "#C0392B", "label": "Interview Exp"},
    "reminder":        {"icon": "⏰", "color": "#E8834A", "label": "Reminder"},
    "product_idea":    {"icon": "💡", "color": "#8E44AD", "label": "Idea"},
    "general_note":    {"icon": "📝", "color": "#5A9E6F", "label": "Note"},
    "unclassified":    {"icon": "❓", "color": "#9B9B9B", "label": "Unclear"},
}

SCRAPER_TIMEOUT = 10
REMINDER_POLL_INTERVAL = 60
