"""Optional LLM step (Google Gemini) for what the keyword rules can't handle.

Two narrow jobs, both reviewable by a person:
  Job A  label_unclassified(): classify only reviews the rules left as "Other",
         choosing from the SAME fixed category list. Each label carries a short reason.
  Job B  suggest_keywords(): propose new keywords for config.py, each measured
         against the data. A person decides which to add; nothing is auto-applied.

Privacy: only review_id and review text are sent. No names, no other fields.
Cost/repeatability: every label is cached by review_id in data/labels_llm.csv,
so each review is sent once and later refreshes only send new reviews.
Without GEMINI_API_KEY the app simply runs rules-only.
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone

import pandas as pd

from src import config

OTHER_ID = "other"
VALID_IDS = [c["id"] for c in config.CATEGORIES] + [OTHER_ID]
FIXABLE = {c["id"]: c["fixable_by"] for c in config.CATEGORIES} | {OTHER_ID: ""}
LABEL_COLUMNS = ["review_id", "llm_category", "llm_secondary", "llm_is_safety",
                 "llm_reason", "llm_model", "labelled_at"]


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------
def get_api_key() -> str | None:
    """Read the key from the environment or .env. Never logged or printed."""
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        try:
            from dotenv import dotenv_values
            key = dotenv_values(config.ROOT / ".env").get("GEMINI_API_KEY")
        except ImportError:
            key = None
    return key or None


def is_available() -> bool:
    return get_api_key() is not None


def _default_generate(prompt: str, response_schema: dict) -> str:
    """One Gemini call that must return JSON matching response_schema."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=get_api_key())
    resp = client.models.generate_content(
        model=config.LLM_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0,  # as repeatable as the model allows
            response_mime_type="application/json",
            response_json_schema=response_schema,
        ),
    )
    return resp.text


def _is_permanent(exc: Exception) -> bool:
    """4xx errors other than 429 (rate limit) won't fix themselves: bad model, bad key..."""
    code = getattr(exc, "code", None)
    return isinstance(code, int) and 400 <= code < 500 and code != 429


def _call_with_retries(generate, prompt, schema, retries=4):
    """Retry on rate limits / transient errors with increasing waits (10s, 20s, 40s...)."""
    for attempt in range(retries):
        try:
            return json.loads(generate(prompt, schema))
        except Exception as exc:
            if attempt == retries - 1 or _is_permanent(exc):
                raise
            wait = 10 * 2 ** attempt
            print(f"    LLM call failed ({type(exc).__name__}: {str(exc)[:120]}); retrying in {wait}s")
            time.sleep(wait)


# ---------------------------------------------------------------------------
# Job A: label reviews the rules couldn't place
# ---------------------------------------------------------------------------
def _category_guide() -> str:
    lines = [f'- "{c["id"]}": {c["name"]}. {c["description"]}' for c in config.CATEGORIES]
    lines.append(f'- "{OTHER_ID}": Too vague to tell, or not about any category above '
                 '(e.g. "worst app", "useless").')
    return "\n".join(lines)


LABEL_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "review_id": {"type": "string"},
            "category": {"type": "string", "enum": VALID_IDS},
            "secondary": {"type": "string", "enum": VALID_IDS + ["none"]},
            "is_safety": {"type": "boolean"},
            "reason": {"type": "string"},
        },
        "required": ["review_id", "category", "secondary", "is_safety", "reason"],
    },
}


def build_label_prompt(batch: pd.DataFrame) -> str:
    reviews = [{"review_id": r.review_id, "text": r.review_text} for r in batch.itertuples()]
    return f"""You are classifying Google Play reviews of MoveInSync, an app employees use to book and track office cabs/shuttles arranged by their employer.

Assign each review ONE main category from this fixed list (use the id in quotes):
{_category_guide()}

Rules:
- Base the label only on what the review says. Do not guess a root cause.
- Reviews may be in English, Hindi or Hinglish (Hindi in Latin script). Read them as written.
- "secondary": another category the review clearly also mentions, otherwise "none".
- "is_safety": true only if the review describes a personal safety risk.
- "reason": max 12 words, quoting or paraphrasing the part of the review that decided the label.
- Return exactly one object per review_id given, in any order.

Reviews (JSON):
{json.dumps(reviews, ensure_ascii=False)}"""


def parse_labels(raw: list, batch_ids: list[str], model: str) -> list[dict]:
    """Validate model output. Unknown ids are dropped, unknown categories become 'other'."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    wanted = set(batch_ids)
    out = {}
    for item in raw or []:
        rid = str(item.get("review_id", ""))
        if rid not in wanted or rid in out:
            continue
        cat = item.get("category") if item.get("category") in VALID_IDS else OTHER_ID
        sec = item.get("secondary") if item.get("secondary") in VALID_IDS else None
        out[rid] = {
            "review_id": rid,
            "llm_category": cat,
            "llm_secondary": sec if sec != cat else None,
            "llm_is_safety": bool(item.get("is_safety")) or cat == "safety",
            "llm_reason": str(item.get("reason", ""))[:200],
            "llm_model": model,
            "labelled_at": now,
        }
    return list(out.values())


def load_llm_labels(path=None) -> pd.DataFrame:
    path = path or config.LLM_LABELS_CSV
    if not path.exists():
        return pd.DataFrame(columns=LABEL_COLUMNS)
    return pd.read_csv(path, dtype={"review_id": "string"})


def label_unclassified(classified: pd.DataFrame, limit: int | None = None,
                       generate=None, pause: float | None = None, path=None) -> dict:
    """Send rule-unclassified, substantive 1-3 star reviews to the LLM (only ones not cached).

    classified: output of classifier.classify_df().
    Saves after every batch, so an interruption loses at most one batch.
    """
    generate = generate or _default_generate
    pause = config.LLM_PAUSE_SECONDS if pause is None else pause
    path = path or config.LLM_LABELS_CSV

    cached = load_llm_labels(path)
    todo = classified[
        (classified["primary_category"] == config.OTHER)
        & (classified["rating"] <= config.COMPLAINT_MAX_RATING)
        & ~classified["review_id"].isin(set(cached["review_id"]))
    ]
    if limit:
        todo = todo.head(limit)

    labelled, failed_batches = 0, 0
    size = config.LLM_BATCH_SIZE
    for start in range(0, len(todo), size):
        batch = todo.iloc[start:start + size]
        try:
            raw = _call_with_retries(generate, build_label_prompt(batch), LABEL_SCHEMA)
        except Exception as exc:
            failed_batches += 1
            print(f"  batch {start // size + 1} failed: {type(exc).__name__}: {str(exc)[:200]}")
            if _is_permanent(exc):
                print("  Stopping: this error won't fix itself (check model name / key).")
                break
            print("  Skipped; it will be retried on the next run.")
            continue
        rows = parse_labels(raw, list(batch["review_id"]), config.LLM_MODEL)
        cached = pd.concat([cached, pd.DataFrame(rows, columns=LABEL_COLUMNS)], ignore_index=True)
        cached.to_csv(path, index=False, encoding="utf-8")
        labelled += len(rows)
        print(f"  batch {start // size + 1}/{-(-len(todo) // size)}: labelled {len(rows)}/{len(batch)}")
        if start + size < len(todo):
            time.sleep(pause)

    return {"to_label": len(todo), "labelled": labelled, "failed_batches": failed_batches,
            "total_cached": len(cached)}


def apply_llm_labels(classified: pd.DataFrame, labels: pd.DataFrame | None = None) -> pd.DataFrame:
    """Fill rule-unclassified reviews with cached LLM labels. Rule labels are never overwritten."""
    labels = load_llm_labels() if labels is None else labels
    out = classified.copy()
    if labels.empty:
        out["llm_reason"] = None
        return out
    lab = labels.drop_duplicates("review_id", keep="last").set_index("review_id")
    mask = (out["primary_category"] == config.OTHER) & out["review_id"].isin(lab.index)
    ids = out.loc[mask, "review_id"]
    llm_cat = ids.map(lab["llm_category"])
    has_cat = llm_cat != OTHER_ID

    upd = ids.index[has_cat.values]
    out.loc[upd, "primary_category"] = llm_cat[has_cat].values
    sec = ids[has_cat].map(lab["llm_secondary"])
    out.loc[upd, "categories"] = [
        "|".join([p] + ([s] if isinstance(s, str) and s else []))
        for p, s in zip(llm_cat[has_cat].values, sec.values)
    ]
    out.loc[upd, "is_safety"] = ids[has_cat].map(lab["llm_is_safety"]).astype(bool).values
    out.loc[upd, "label_source"] = "llm"
    out["llm_reason"] = out["review_id"].map(lab["llm_reason"]).where(mask)
    return out


# ---------------------------------------------------------------------------
# Job B: keyword suggestions for a person to review
# ---------------------------------------------------------------------------
SUGGEST_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "category": {"type": "string", "enum": [c["id"] for c in config.CATEGORIES]},
            "keyword": {"type": "string"},
            "why": {"type": "string"},
        },
        "required": ["category", "keyword", "why"],
    },
}


def build_suggest_prompt(examples: pd.DataFrame) -> str:
    items = [{"category": r.llm_category, "text": r.review_text} for r in examples.itertuples()]
    return f"""These app reviews were missed by a keyword classifier and then labelled by category.
Categories:
{_category_guide()}

Propose up to 30 NEW keywords or short phrases (1-3 words, lowercase) that:
- appear word-for-word in several of the reviews below,
- strongly indicate their category (avoid generic words like "app", "worst", "service", "bad"),
- include Hindi/Hinglish phrases where you see them.
For each, give the category and a short reason.

Labelled reviews (JSON):
{json.dumps(items, ensure_ascii=False)}"""


def score_keyword(keyword: str, category: str, reviews: pd.DataFrame) -> dict:
    """How often a candidate keyword appears in complaints, and how often those reviews
    carry that category (from rules or LLM). Helps a person judge precision."""
    from src.classifier import normalize
    regex = re.compile(r"\b" + re.escape(keyword.lower()) + r"\b")
    hits = reviews[reviews["review_text"].map(lambda t: bool(regex.search(normalize(t))))]
    in_cat = hits["categories"].fillna("").str.split("|").map(lambda c: category in c)
    return {
        "matches": len(hits),
        "precision_vs_labels": round(in_cat.mean(), 2) if len(hits) else None,
        "newly_covered": int((hits["label_source"] != "rule").sum()),
    }


def suggest_keywords(final_labels: pd.DataFrame, generate=None, max_examples: int = 300) -> pd.DataFrame:
    """Ask the LLM for keyword candidates from LLM-labelled reviews, then measure each one."""
    generate = generate or _default_generate
    complaints = final_labels[final_labels["rating"] <= config.COMPLAINT_MAX_RATING]
    llm_rows = complaints[complaints["label_source"] == "llm"].copy()
    llm_rows["llm_category"] = llm_rows["primary_category"]
    examples = llm_rows.sample(min(max_examples, len(llm_rows)), random_state=1)
    raw = _call_with_retries(generate, build_suggest_prompt(examples), SUGGEST_SCHEMA)

    rows = []
    for s in raw or []:
        kw = str(s.get("keyword", "")).strip().lower()
        if not kw or s.get("category") not in FIXABLE:
            continue
        rows.append({"category": s["category"], "keyword": kw, "why": s.get("why", ""),
                     **score_keyword(kw, s["category"], complaints),
                     "decision": "pending"})
    out = pd.DataFrame(rows).drop_duplicates(["category", "keyword"])
    if not out.empty:
        out = out.sort_values(["precision_vs_labels", "matches"], ascending=False)
    out.to_csv(config.KEYWORD_SUGGESTIONS_CSV, index=False, encoding="utf-8-sig")
    return out
