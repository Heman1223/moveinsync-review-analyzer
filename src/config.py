"""Project settings: apps, storage paths, issue categories and their keywords.

Everything a reviewer might want to tweak lives in this one file.
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

# ---------------------------------------------------------------------------
# Issue categories
# ---------------------------------------------------------------------------
# Built from a manual read of 100 recent 1-3 star reviews
# (data/reading_sample_labelled.csv), then tuned on the full dataset.
#
# Each keyword is a regular expression matched case-insensitively on whole words
# (\b...\b is added automatically). Hinglish variants are included on purpose.
#
# Order matters: when a review matches several categories, the first one in this
# list becomes its primary category. Specific issues come first; generic ones
# ("not working", "not user friendly") come last so they don't swallow the rest.
#
# fixable_by: who can act on it.
#   App    = MoveInSync product/engineering
#   Ops    = transport operations, vendors, drivers, helpdesk
#   Review = always needs a human to look at it (safety)
CATEGORIES = [
    {
        "id": "safety",
        "name": "Safety concern",
        "fixable_by": "Review",
        "description": "Personal safety risk: harassment, misbehaviour toward women, drunk or rash driving, unsafe pickup spots, emergencies, no way to get help.",
        "keywords": [
            r"unsafe", r"not safe", r"no safety", r"safety (issue|concern|risk)",
            r"harass\w*", r"molest\w*", r"assault\w*", r"inappropriate\w*",
            r"misbehav\w* with (a |the )?(girl|woman|lady|female)\w*",
            r"(girl|woman|women|lady|female) (employee|colleague|passenger)s?",
            r"drunk", r"rash driv\w*", r"dangerous\w*", r"sos",
            # "emergency"/"threat" alone are too broad ("stuck in an emergency", "a threat to my time")
            r"emergency (button|number|contact|call|alert)s?", r"in case of (an |any )?emergency",
            r"threaten\w*", r"scared", r"afraid",
        ],
    },
    {
        "id": "prompts",
        "name": "Repeated prompts and permissions",
        "fixable_by": "App",
        "description": "Friction from mandatory pop-ups and permissions: accepting the transport policy every time, forced trip rating, seat-belt confirmations, excessive permissions.",
        "keywords": [
            r"(transport )?polic(y|ies)", r"agreements?", r"terms and conditions",
            r"accept (it |the \w+ )?every ?time", r"seat ?belt",
            r"(rate|rating) (every|each|the previous|previous) (trip|ride)",
            r"forced? to rate", r"rating pop ?ups?", r"pop[- ]?ups?",
            r"permissions?",
        ],
    },
    {
        "id": "login",
        "name": "Login, OTP and session",
        "fixable_by": "App",
        "description": "Getting into the app: OTP not received, forced logouts, session expired, identity verification, password problems.",
        "keywords": [
            r"otp\w*", r"log ?in\w*", r"sign ?in\w*", r"logged out", r"logs? (me )?out",
            r"log ?out automatically", r"auto(matically)? log ?out", r"signs? (me )?out",
            r"session (expired|timeout|time out)", r"unauthori[sz]ed", r"password",
            r"verif(y|ication|ied)", r"validat\w*", r"credentials?", r"re-?login",
            # added from LLM keyword suggestions (approved 2026-10-11)
            r"user not found",
        ],
    },
    {
        "id": "notifications",
        "name": "Notifications",
        "fixable_by": "App",
        "description": "Push notifications and alerts that are wrong, missing, late, duplicated or spammy.",
        "keywords": [
            r"notifications?", r"notif", r"alerts?", r"reminders?", r"push messages?",
        ],
    },
    {
        "id": "booking",
        "name": "Booking and schedule",
        "fixable_by": "App",
        "description": "Creating, viewing, editing or cancelling trips and schedules: booking fails, booked trip missing, waitlist, booking window limits.",
        "keywords": [
            r"book\w*", r"schedul\w*", r"roster\w*", r"cancel\w*", r"wait ?list\w*",
            r"slots?", r"seats? (are |is )?(full|booked|not available)", r"reserv\w*",
            r"chance passenger", r"ad ?hoc", r"modify", r"edit (the |my )?(trip|booking)",
            r"edit\w*",
            # added from LLM keyword suggestions (approved 2026-10-11)
            r"roaster\w*",
        ],
    },
    {
        "id": "routing",
        "name": "Routing and pickup points",
        "fixable_by": "Ops",
        "description": "Route planning and pickup/drop points: long routes, far or removed pickup points, wrong drop sequence, poor pooling.",
        "keywords": [
            r"rout(e|es|ing)", r"nodal\w*", r"pick ?-?up points?", r"drop points?",
            r"pick ?-?up locations?", r"boarding points?", r"drop sequence",
            r"detours?", r"pooling", r"(far|long) (away|distance|walk)", r"walk\w*",
            r"(bus|shuttle|pickup|nodal) stops?", r"more stops",
        ],
    },
    {
        "id": "driver",
        "name": "Driver behaviour",
        "fixable_by": "Ops",
        "description": "Driver conduct: rude, abusive, unprofessional behaviour (non-safety).",
        "keywords": [
            r"rude\w*", r"misbehav\w*", r"abusive", r"abus\w*", r"behaviou?r\w*",
            r"behave", r"attitude", r"unprofessional", r"manners", r"arrogant",
            r"driver (is |was |are )?(very )?(bad|worst|rude|horrible|pathetic)",
        ],
    },
    {
        "id": "tracking",
        "name": "Tracking, ETA and map",
        "fixable_by": "App",
        "description": "Live tracking, ETA and maps: wrong cab location, inaccurate ETA, map/zoom issues, cab or vehicle details not shown.",
        "keywords": [
            r"track\w*", r"gps", r"eta", r"live location", r"cab location",
            r"vehicle location", r"(wrong|incorrect|inaccurate) location", r"maps?",
            r"zoom\w*", r"navigation", r"arrival time", r"address\w*", r"geo ?location",
            r"location\w*", r"locate", r"real ?-?time",
            r"(cab|vehicle|car|driver) (details|number|status|info)",
            # added from LLM keyword suggestions (approved 2026-10-11)
            r"where is the cab",
        ],
    },
    {
        "id": "cab_delay",
        "name": "Cab late or no-show",
        "fixable_by": "Ops",
        "description": "Cab punctuality: late cabs, cab never came, no-show disputes, long waits, late allocation.",
        "keywords": [
            r"late", r"delay\w*", r"not on time", r"never (came|come|arrived?)",
            r"(didn'?t|did not|does not|doesn'?t) (come|arrive|turn up)", r"no[- ]?show\w*",
            r"marked (me )?absent", r"missed (my |the )?(cab|shuttle|bus|pickup)",
            r"waiting (for|time)", r"allocat\w*", r"cab (nahi|nhi) (aayi|aaya|aati|aata)",
            r"(nahi|nhi) (aayi|aaya)", r"der se",
            r"(made|make|kept|keep) (me|us) wait\w*", r"wait(ed)? (for|till)", r"reassign\w*",
            # added from LLM keyword suggestions (approved 2026-10-11)
            r"never on time", r"not coming on time",
        ],
    },
    {
        "id": "support",
        "name": "Support and contact",
        "fixable_by": "Ops",
        "description": "Reaching people: helpdesk/customer support unresponsive, can't call driver or helpdesk, complaints and feedback ignored.",
        "keywords": [
            r"help ?desk", r"customer (care|support|service)", r"support team",
            r"no response", r"not respond\w*", r"no one (respond|answer|pick)\w*",
            r"(don'?t|do not|never) pick ?up (the )?calls?", r"complain\w*", r"escalat\w*",
            r"(can'?t|cannot|unable to|no option to) call", r"call(ing)? (option|permission)",
            r"contact (number|details|anyone)", r"feedback (is )?ignored", r"don'?t listen",
            r"calls? (are )?(not|never) (connect\w*|answered)",
            r"(cannot|can'?t|unable to) (connect|reach|contact)\w*", r"nobody (answers|responds|picks)",
            r"feedback\w*",
            # added from LLM keyword suggestions (approved 2026-10-11)
            r"call the driver", r"contact the driver",
        ],
    },
    {
        "id": "vehicle_vendor",
        "name": "Vehicle and vendor quality",
        "fixable_by": "Ops",
        "description": "Vehicle condition and transport vendor quality: dirty or old vehicles, AC, poor vendor management.",
        "keywords": [
            r"vendors?", r"transport (management|team|department|service)s?",
            r"(vehicle|cab|car|bus) (condition|quality|is dirty|was dirty)", r"dirty",
            r"ac (not|is not|isn'?t) working", r"no ac", r"old (vehicles?|cabs?|cars?)",
        ],
    },
    {
        "id": "stability",
        "name": "App stability and performance",
        "fixable_by": "App",
        "description": "Technical reliability: app crashes, won't open, slow, stuck, errors, fails on mobile data or Wi-Fi, battery drain, bugs after an update.",
        "keywords": [
            r"crash\w*", r"(not|never|doesn'?t|does not|won'?t|will not) open\w*",
            r"not opening", r"stuck", r"hang\w*", r"freez\w*", r"frozen", r"slow\w*",
            r"load\w*", r"not working", r"(doesn'?t|does not|isn'?t|is not) work\w*",
            r"(stopped|stops) working", r"errors?", r"glitch\w*", r"bug\w*",
            r"server (is )?down", r"app (is )?down", r"battery", r"mobile data", r"wi-?fi",
            r"network", r"something went wrong", r"lag\w*", r"(chal|khul) (nahi|nhi)",
            r"after (the )?(latest |new |recent )?update", r"new update",
            r"never works?", r"stop working", r"unreliable",
            # added from LLM keyword suggestions (approved 2026-10-11)
            r"rooted device", r"uninstall and reinstall", r"not compatible", r"server issues", r"goes blank",
        ],
    },
    {
        "id": "usability",
        "name": "Usability and design",
        "fixable_by": "App",
        "description": "Design and ease of use: not user friendly, confusing UI, removed features, old version was better, accessibility, dark mode.",
        "keywords": [
            r"user ?-?friendly", r"ui", r"ux", r"interface", r"design\w*",
            r"confus\w*", r"complicated", r"(difficult|hard) to (use|understand|find)",
            r"dark (mode|theme)", r"tutorial",
            r"too many (taps|clicks|steps)", r"not intuitive",
            r"(old|previous|previuos|earlier) (app|version)\w*", r"(removed|remove) (the |that |this )?(feature|option)\w*",
            r"co-?passengers?", r"with whom", r"accessib\w*", r"inaccessible", r"blind",
            r"search (option|bar|function)",
        ],
    },
]

# Display names for reviews that get no issue category.
OTHER = "Other / unclassified"
LOW_INFO = "Low info"          # very short text with no issue keyword ("good", "nice app")
NO_TEXT = "Rating only"        # no text at all

LOW_INFO_MAX_WORDS = 3         # reviews this short with no keyword match are "Low info"
COMPLAINT_MAX_RATING = 3       # issue analysis focuses on 1-3 star reviews

# ---------------------------------------------------------------------------
# LLM assist (optional; needs GEMINI_API_KEY in .env)
# ---------------------------------------------------------------------------
LLM_MODEL = "gemini-3.8-flash"     # pinned (not "-latest") so results stay reproducible
LLM_BATCH_SIZE = 50            # reviews per request (fewer calls = fewer rate-limit hits)
LLM_PAUSE_SECONDS = 7.0        # stays under free-tier requests-per-minute limits
LLM_LABELS_CSV = DATA_DIR / "labels_llm.csv"
KEYWORD_SUGGESTIONS_CSV = DATA_DIR / "keyword_suggestions.csv"
LLM_THINKING_LEVEL = "low"     # classification is simple; less "thinking" = far fewer billed tokens
LLM_USAGE_CSV = DATA_DIR / "llm_usage.csv"   # token counts per call, to track spend
LLM_MAX_CALLS_PER_RUN = 10     # budget guard: one run can never send more than this many requests
