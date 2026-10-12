"""One place that turns raw reviews into the labelled table the dashboard reads.

    refresh → (optional) LLM for new unclassified → classify + sub-problems → data/reviews_labelled.csv

The dashboard only *reads* reviews_labelled.csv, so it opens in seconds instead of
re-classifying 24k reviews on every start. A small fingerprint file records which inputs
(data + rules) produced it; if any input changes, the table is rebuilt automatically.
"""

from __future__ import annotations

import hashlib
import json
import os

import pandas as pd

from src import analysis, config, llm_assist
from src.classifier import classify_df
from src.collector import load_reviews, refresh

LABELLED_CSV = config.DATA_DIR / "reviews_labelled.csv"
FINGERPRINT = config.DATA_DIR / "reviews_labelled.fingerprint.json"
SRC = config.ROOT / "src"
INPUTS = [config.REVIEWS_CSV, config.LLM_LABELS_CSV,
          SRC / "config.py", SRC / "classifier.py", SRC / "playbook.py", SRC / "analysis.py"]
BOOL_COLS = ["has_reply", "is_complaint", "is_substantive", "is_safety"]


def public_demo() -> bool:
    """PUBLIC_DEMO=1 on the public link: read-only (no refresh, no fix tracking, no Gemini)."""
    return os.environ.get("PUBLIC_DEMO", "") == "1"


def llm_allowed() -> bool:
    """LLM calls need a key and must not be disabled (DISABLE_LLM=1, or the public demo)."""
    return (llm_assist.is_available() and os.environ.get("DISABLE_LLM", "") != "1"
            and not public_demo())


def _fingerprint() -> str:
    h = hashlib.sha256()
    for path in INPUTS:
        h.update(path.name.encode())
        if path.exists():
            # normalise line endings so a Windows checkout and a Linux server agree
            h.update(path.read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()


def is_fresh() -> bool:
    if not (LABELLED_CSV.exists() and FINGERPRINT.exists()):
        return False
    try:
        return json.loads(FINGERPRINT.read_text())["inputs"] == _fingerprint()
    except (ValueError, KeyError):
        return False


def build_labelled() -> pd.DataFrame:
    """Classify everything from saved data (no network) and save the labelled table."""
    df = analysis.prepare(load_reviews())
    df.to_csv(LABELLED_CSV, index=False, encoding="utf-8")
    FINGERPRINT.write_text(json.dumps({"inputs": _fingerprint(), "rows": len(df)}))
    return df


def load_labelled() -> pd.DataFrame:
    """Read the labelled table, rebuilding it first if any input changed."""
    if not is_fresh():
        return build_labelled()
    df = pd.read_csv(LABELLED_CSV, dtype={"review_id": "string", "review_version": "string"},
                     parse_dates=["review_date", "reply_date", "month"], low_memory=False)
    for col in BOOL_COLS:
        df[col] = df[col].astype(str).str.lower().eq("true")
    for col in ["categories", "matched_keywords", "label_source", "sub_issue", "fixable_by", "llm_reason"]:
        df[col] = df[col].where(df[col].notna(), None)
    return df


def run(full: bool = False, use_llm: bool | None = None, log=print) -> dict:
    """Full refresh: fetch → LLM (if allowed) → labelled table. Used by the CLI, the button and the weekly job."""
    summary = refresh(full=full, log=log)
    use_llm = llm_allowed() if use_llm is None else use_llm
    summary["llm"] = None
    if use_llm:
        summary["llm"] = llm_assist.label_unclassified(classify_df(load_reviews()))
    build_labelled()
    return summary
