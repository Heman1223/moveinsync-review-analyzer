"""Rule-based issue classifier.

Transparent by design: every label can be traced to the keyword that triggered it.
Keywords live in src/config.py. Reviews the rules can't place are left as
"Other / unclassified" for the optional LLM step (src/llm_assist.py).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import pandas as pd

from src import config


def normalize(text) -> str:
    """Lowercase, unify apostrophes and collapse whitespace. Original text is kept elsewhere."""
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return ""
    text = str(text).lower().replace("’", "'").replace("‘", "'")
    return re.sub(r"\s+", " ", text).strip()


def _compile(categories):
    compiled = []
    for cat in categories:
        pattern = r"\b(?:" + "|".join(cat["keywords"]) + r")\b"
        compiled.append((cat, re.compile(pattern, re.IGNORECASE)))
    return compiled


_COMPILED = _compile(config.CATEGORIES)
_NAME = {c["id"]: c["name"] for c in config.CATEGORIES}
_FIXABLE = {c["id"]: c["fixable_by"] for c in config.CATEGORIES}


@dataclass
class Classification:
    categories: list[str] = field(default_factory=list)    # all matched category ids, in priority order
    primary: str | None = None                             # first match, or a special label
    matched_keywords: dict[str, list[str]] = field(default_factory=dict)
    is_safety: bool = False


def classify_text(text, compiled=None) -> Classification:
    compiled = compiled or _COMPILED
    norm = normalize(text)
    if not norm:
        return Classification(primary=config.NO_TEXT)

    result = Classification()
    for cat, regex in compiled:
        hits = sorted({m.group(0) for m in regex.finditer(norm)})
        if hits:
            result.categories.append(cat["id"])
            result.matched_keywords[cat["id"]] = hits

    if result.categories:
        result.primary = result.categories[0]
        result.is_safety = "safety" in result.categories
    elif len(norm.split()) <= config.LOW_INFO_MAX_WORDS:
        result.primary = config.LOW_INFO
    else:
        result.primary = config.OTHER
    return result


def category_name(cat_id: str) -> str:
    return _NAME.get(cat_id, cat_id)


def fixable_by(cat_id: str) -> str:
    return _FIXABLE.get(cat_id, "")


def classify_df(df: pd.DataFrame) -> pd.DataFrame:
    """Add rule-based label columns to a reviews DataFrame (returns a copy)."""
    out = df.copy()
    results = [classify_text(t) for t in out["review_text"]]
    out["categories"] = ["|".join(r.categories) for r in results]
    out["primary_category"] = [r.primary for r in results]
    out["matched_keywords"] = [
        "; ".join(f"{cid}: {', '.join(kws)}" for cid, kws in r.matched_keywords.items())
        for r in results
    ]
    out["is_safety"] = [r.is_safety for r in results]
    out["label_source"] = ["rule" if r.categories else "" for r in results]
    return out
