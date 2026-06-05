import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL = "claude-opus-4-8"
HAIKU_MODEL = "claude-haiku-4-5-20251001"
PORT = 5050
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "cortex.db")

# Zepto MCP integration
# Auth server discovered via RFC 9728: https://mcp.zepto.co.in/.well-known/oauth-protected-resource
ZEPTO_MCP_URL = "https://mcp.zepto.co.in/mcp"
ZEPTO_OAUTH_REDIRECT_URI = os.getenv("ZEPTO_REDIRECT_URI", "http://localhost:5050/api/zepto/callback")
ZEPTO_OAUTH_AUTH_URL = os.getenv("ZEPTO_OAUTH_AUTH_URL", "https://auth.zepto.co.in/authorize")
ZEPTO_OAUTH_TOKEN_URL = os.getenv("ZEPTO_OAUTH_TOKEN_URL", "https://auth.zepto.co.in/token")
ZEPTO_CLIENT_ID = os.getenv("ZEPTO_CLIENT_ID", "2516f1beee02dab0606738d7be97165e")
FERNET_KEY = os.getenv("FERNET_KEY", "")  # Required for Zepto OAuth token encryption

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
