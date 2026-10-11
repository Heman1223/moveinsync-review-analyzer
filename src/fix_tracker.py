"""Track which issues the team is already fixing, so "Fix these first" shows what's next.

Stored in data/fix_tracker.csv (one row per app + issue). Reviews lag behind fixes, so an
issue stays in the tracker, with before/after numbers, until someone removes it.
On Streamlit Community Cloud the file resets when the app restarts; commit it to the
repo to keep it.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from src import config

PATH = config.DATA_DIR / "fix_tracker.csv"
STATUSES = ["In progress", "Fix shipped"]
COLUMNS = ["app_id", "category", "status", "since", "note"]


def load(app_id: str | None = None, path=None) -> pd.DataFrame:
    path = path or PATH
    df = pd.read_csv(path, dtype=str).fillna("") if path.exists() else pd.DataFrame(columns=COLUMNS)
    return df[df["app_id"] == app_id] if app_id else df


def _save(df: pd.DataFrame, path=None) -> None:
    path = path or PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    df[COLUMNS].to_csv(path, index=False, encoding="utf-8")


def set_status(app_id: str, category: str, status: str, since: date, note: str = "", path=None) -> pd.DataFrame:
    if status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}")
    df = load(path=path)
    df = df[~((df["app_id"] == app_id) & (df["category"] == category))]
    row = {"app_id": app_id, "category": category, "status": status, "since": str(since), "note": note.strip()}
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    _save(df, path)
    return df


def remove(app_id: str, category: str, path=None) -> pd.DataFrame:
    df = load(path=path)
    df = df[~((df["app_id"] == app_id) & (df["category"] == category))]
    _save(df, path)
    return df
