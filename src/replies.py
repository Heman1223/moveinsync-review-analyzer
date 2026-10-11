"""Reply assistant: suggested replies to unhappy (1–2★) reviews, for a person to check and post.

Two ways to draft a reply:
  template_reply()  no AI, no cost: greeting + a line written for the review's specific
                    problem (src/playbook.py) + a closing that invites them to get in touch
  llm_reply()       Google Gemini writes a reply to that exact review, following the same
                    rules; one call per review, saved in data/reply_drafts.csv so the same
                    review never costs twice

Rules for every reply (enforced in the prompt and checked afterwards):
  - fits Google Play's 350-character limit for developer replies
  - polite, specific to what the reviewer said, no blaming the user
  - no promises of refunds, compensation or fix dates; no personal data
  - contact details are a placeholder ([support email]) for the team to fill in
Nothing is ever posted automatically.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd

from src import config, llm_assist
from src.playbook import SUB_ISSUES

MAX_CHARS = 350                      # Google Play developer reply limit
DRAFTS_CSV = config.DATA_DIR / "reply_drafts.csv"
CONTACT = "[support email]"          # filled in by the support team before posting

OPENING = "Hi, thank you for your feedback, and we're sorry for the trouble."
CLOSING = f"Please write to us at {CONTACT} with your registered number so we can look into it. – Team MoveInSync"
FALLBACK_LINE = "We'd like to understand what went wrong so we can fix it."
BANNED = ["refund", "compensat", "guarantee", "free ride", "cashback", "by tomorrow", "within 24"]


def _sub_line(category: str | None, sub_issue: str | None) -> str:
    for sub in SUB_ISSUES.get(category or "", []):
        if sub["id"] == sub_issue and sub.get("reply"):
            return sub["reply"]
    return FALLBACK_LINE


def template_reply(category: str | None, sub_issue: str | None) -> str:
    text = f"{OPENING} {_sub_line(category, sub_issue)} {CLOSING}"
    if len(text) > MAX_CHARS:  # drop the opening rather than cut a sentence in half
        text = f"Sorry for the trouble. {_sub_line(category, sub_issue)} {CLOSING}"
    return text


def check_reply(text: str) -> list[str]:
    """Problems that mean a draft should not be used as-is."""
    problems = []
    if len(text) > MAX_CHARS:
        problems.append(f"too long ({len(text)} characters; Google Play allows {MAX_CHARS})")
    low = text.lower()
    problems += [f"mentions '{w}'" for w in BANNED if w in low]
    return problems


# ---------------------------------------------------------------------------
# Gemini drafts (optional)
# ---------------------------------------------------------------------------
REPLY_SCHEMA = {"type": "object", "properties": {"reply": {"type": "string"}}, "required": ["reply"]}


def build_prompt(review_text: str, rating: int, problem: str) -> str:
    return f"""You draft public replies from the MoveInSync team to Google Play reviews of its employee commute app
(employees book and track office cabs arranged by their employer).

Write ONE reply to the review below.
Rules:
- At most 300 characters. Plain, warm, professional English. No emojis.
- Acknowledge the specific problem in the reviewer's own terms (they may write in Hinglish; reply in English).
- Do not blame the user. Do not promise refunds, compensation, free rides, or fix dates.
- Do not state facts you don't know: no reasons for product decisions, no claims that something is already fixed.
- Do not ask for personal details publicly. To continue the conversation, say: write to us at {CONTACT}.
- End with: – Team MoveInSync

Review ({rating}★), about: {problem}
\"\"\"{review_text}\"\"\""""


def load_drafts() -> pd.DataFrame:
    if not DRAFTS_CSV.exists():
        return pd.DataFrame(columns=["review_id", "draft", "model", "created_at"])
    return pd.read_csv(DRAFTS_CSV, dtype={"review_id": "string"})


def cached_draft(review_id: str) -> str | None:
    d = load_drafts()
    hit = d[d["review_id"] == review_id]
    return None if hit.empty else str(hit.iloc[-1]["draft"])


def llm_reply(review_id: str, review_text: str, rating: int, category: str | None, sub_issue: str | None,
              problem: str, generate=None) -> tuple[str, str]:
    """Return (reply, source). Uses the saved draft if there is one; falls back to the template
    if Gemini fails or breaks a rule. source is 'saved', 'gemini' or 'template'."""
    saved = cached_draft(review_id)
    if saved:
        return saved, "saved"
    generate = generate or llm_assist._default_generate
    try:
        raw = generate(build_prompt(review_text, rating, problem), REPLY_SCHEMA)
        draft = str(json.loads(raw)["reply"]).strip()
    except Exception:
        return template_reply(category, sub_issue), "template"
    if not draft or check_reply(draft):
        return template_reply(category, sub_issue), "template"
    row = pd.DataFrame([{"review_id": review_id, "draft": draft, "model": config.LLM_MODEL,
                         "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")}])
    pd.concat([load_drafts(), row], ignore_index=True).to_csv(DRAFTS_CSV, index=False, encoding="utf-8")
    return draft, "gemini"


def unanswered(df: pd.DataFrame) -> pd.DataFrame:
    """1–2★ reviews with text and no developer reply, newest first."""
    rows = df[(df["rating"] <= 2) & ~df["has_reply"] & df["review_text"].fillna("").str.strip().ne("")]
    return rows.sort_values("review_date", ascending=False)
