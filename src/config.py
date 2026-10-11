"""Project settings: which apps to analyse and where data is stored.

Category keywords, owners and thresholds will be added here in later milestones,
so that everything a reviewer might want to tweak lives in one file.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Apps
# ---------------------------------------------------------------------------
# Only commute-related apps with enough reviews to analyse are included.
# Out of scope (stated in the method note): Driver Partner (onboarding form,
# 7 text reviews), Field app (admin tool, 8 reviews), Workplace (kiosk, no ratings).
APPS = {
    "com.moveinsync.ets": {
        "name": "Employee app",
        "audience": "Employees booking and taking office rides",
        "primary": True,
    },
    "com.moveinsync.driver.lite": {
        "name": "Partner Lite",
        "audience": "Cab drivers completing assigned trips",
        "primary": False,
    },
}

# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------
COUNTRY = "in"
# Reviews are requested per language. Hinglish/Hindi reviews can be tagged "hi",
# so we fetch both and deduplicate by review_id.
LANGUAGES = ["en", "hi"]
BATCH_SIZE = 200            # max reviews per request the Play Store returns
PAUSE_SECONDS = 1.0         # politeness delay between requests
MAX_RETRIES = 3             # per request, with increasing waits

# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
REVIEWS_CSV = DATA_DIR / "reviews.csv"
SNAPSHOTS_CSV = DATA_DIR / "snapshots.csv"
FETCH_LOG_CSV = DATA_DIR / "fetch_log.csv"

REVIEW_COLUMNS = [
    "app_id",
    "review_id",
    "review_text",
    "rating",
    "review_date",
    "review_version",
    "thumbs_up",
    "reply_text",
    "reply_date",
    "has_reply",
    "fetched_lang",
]
