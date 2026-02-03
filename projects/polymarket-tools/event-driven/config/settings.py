"""
Configuration settings for the event-driven system.
Extracted from hardcoded values in scan.py.
"""
from pathlib import Path
import json

# Base paths
WORKSPACE = Path(__file__).parent.parent
CONFIG_DIR = WORKSPACE / "config"
DATA_DIR = WORKSPACE / "data"

# Config files
SOURCES_FILE = CONFIG_DIR / "sources.json"
STATE_FILE = WORKSPACE / "scan_state.json"
ALERTS_FILE = WORKSPACE / "alerts.jsonl"

# Create data directory if it doesn't exist
DATA_DIR.mkdir(exist_ok=True)

# Load sources configuration
def load_sources():
    """Load sources configuration from JSON file."""
    return json.loads(SOURCES_FILE.read_text())

SOURCES = load_sources()

# Import categories from new configuration
from config.categories import CATEGORIES, get_category_names

# Legacy keywords mapping for backward compatibility
KEYWORDS = {}
for category_name, category_config in CATEGORIES.items():
    # Convert to legacy format - use lowercase category name
    legacy_name = category_name.lower().replace("_", "")
    KEYWORDS[legacy_name] = category_config["keywords"]

# Add some legacy mappings
KEYWORDS.update({
    "trump_deportations": ["deportation", "deported", "ice raid", "mass deportation", "immigration enforcement"],
    "tariffs": ["tariff", "trade war", "import tax", "trump tariff"],
    "fed": CATEGORIES["FED_MONETARY"]["keywords"],
    "russia_ukraine": ["ceasefire", "peace talk", "zelensky", "putin negotiate", "ukraine offensive", "russia attack"],
    "china_taiwan": ["taiwan strait", "china taiwan", "pla exercise", "taiwan invasion", "blockade taiwan"],
    "btc": ["bitcoin price", "btc price", "whale alert", "bitcoin etf", "btc 100k", "btc million"],
    "gta": ["gta 6", "gta vi", "rockstar games", "grand theft auto 6"]
})

# Urgency scoring factors
URGENCY_MULTIPLIERS = {
    "fed": 2.5,  # Fed news are highest priority for markets
    "btc": 2.0,  # Crypto moves fast
    "trump_deportations": 1.8,
    "tariffs": 1.7,
    "russia_ukraine": 1.5,
    "china_taiwan": 1.4,
    "gta": 0.8   # Lower priority
}

URGENCY_KEYWORDS = {
    "breaking": 3.0,
    "urgent": 3.0,
    "alert": 2.5,
    "just in": 2.5,
    "emergency": 3.0,
    "immediate": 2.5,
    "now": 1.5,
    "announced": 2.0,
    "confirms": 1.8,
    "official": 1.5
}

# Scan settings
MIN_URGENCY_THRESHOLD = 4.0  # Only log alerts with urgency >= 4
MAX_FEEDS_PER_CATEGORY = 10  # Limit RSS feeds per scan
MAX_TWEETS_PER_ACCOUNT = 5   # Limit tweets per account
SCAN_TIMEOUT_SECONDS = 30    # Timeout for individual API calls

# Deduplication settings
SIMILARITY_THRESHOLD = 0.75  # For content similarity detection
STATE_RETENTION_HOURS = 6    # How long to keep recent alerts for deduplication
MAX_SEEN_IDS = 500          # Maximum seen IDs to keep in state
MAX_RECENT_ALERTS = 50      # Maximum recent alerts to keep for similarity checking

# Twitter settings
TWITTER_CATEGORIES_TO_SCAN = ["breaking", "fed_specific", "bloomberg_terminal"]
TWITTER_TWEETS_PER_ACCOUNT = 3  # Reduced to avoid rate limits