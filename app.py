"""MoveInSync review analyzer: Streamlit dashboard.

    streamlit run app.py

Reads the saved CSVs (no network needed). "Refresh data" fetches new reviews and,
if a Gemini key is configured, labels only the new unclassified ones.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import analysis, config, fix_tracker, llm_assist
from src.classifier import category_name
from src.collector import load_reviews, refresh

st.set_page_config(page_title="MoveInSync review analyzer", page_icon="⭐", layout="wide")

PERIODS = {"30 days": 30, "90 days": 90, "6 months": 182, "12 months": 365, "All time": None}
LOW_DATA = 30
REPLY_TARGET = 80
FIXABLE_LABEL = {"App": "App fix", "Ops": "Ops fix", "Review": "Human review"}
FIXABLE_COLOR = {"App": "blue", "Ops": "orange", "Review": "red"}


# ---------------------------------------------------------------------------
# Data loading (cached; invalidated when the CSV files change)
# ---------------------------------------------------------------------------
def _mtime(path) -> float:
    return path.stat().st_mtime if path.exists() else 0.0


@st.cache_data(show_spinner="Classifying reviews…")
def load_data(_reviews_mtime: float, _labels_mtime: float, _config_mtime: float) -> pd.DataFrame:
    return analysis.prepare(load_reviews())


@st.cache_data
def load_snapshots(_mtime: float) -> pd.DataFrame | None:
    return pd.read_csv(config.SNAPSHOTS_CSV) if config.SNAPSHOTS_CSV.exists() else None


def last_updated() -> str:
    if not config.FETCH_LOG_CSV.exists():
        return "never"
    t = pd.to_datetime(pd.read_csv(config.FETCH_LOG_CSV)["run_time"]).max()
    return f"{t:%d %b %Y, %H:%M} UTC"


def run_refresh():
    with st.status("Refreshing data…", expanded=True) as status:
        st.write("Fetching new reviews from Google Play…")
        summary = refresh(log=lambda m: None)
        st.write(f"{summary['new_reviews']} new reviews.")
        if summary["errors"]:
            st.warning("Some sources failed; previously saved data was kept:\n\n- " + "\n- ".join(summary["errors"]))
        if llm_assist.is_available():
            st.write("Labelling new unclassified complaints with Gemini (capped per run)…")
            from src.classifier import classify_df
            res = llm_assist.label_unclassified(classify_df(load_reviews()))
            st.write(f"Labelled {res['labelled']} reviews" + (f"; {res['held_back']} left for later." if res["held_back"] else "."))
        else:
            st.write("No Gemini key: new reviews are classified by keyword rules only.")
        status.update(label="Data refreshed", state="complete")
    st.cache_data.clear()


# ---------------------------------------------------------------------------
# Header and filters
# ---------------------------------------------------------------------------
head_l, head_r = st.columns([4, 1], vertical_alignment="center")
with head_l:
    st.title("MoveInSync review analyzer")
    st.caption(f"Why are Play Store ratings where they are, and what should we fix first? "
               f"Public Google Play reviews · updated {last_updated()}")
with head_r:
    if st.button("Refresh data", icon=":material/refresh:", width="stretch"):
        run_refresh()

if not config.REVIEWS_CSV.exists():
    st.info("No data yet. Click **Refresh data** to fetch reviews (takes a few minutes the first time).")
    st.stop()

data = load_data(_mtime(config.REVIEWS_CSV), _mtime(config.LLM_LABELS_CSV), _mtime(config.ROOT / "src" / "config.py"))
snaps = load_snapshots(_mtime(config.SNAPSHOTS_CSV))

app_options = {meta["name"]: app_id for app_id, meta in config.APPS.items()}
f1, f2 = st.columns([3, 3])
with f1:
    app_choice = st.segmented_control("App", list(app_options) + ["Compare apps"],
                                      default=next(iter(app_options)), label_visibility="collapsed")
with f2:
    period_choice = st.segmented_control("Period", list(PERIODS), default="12 months",
                                         label_visibility="collapsed")
app_choice = app_choice or next(iter(app_options))
period_choice = period_choice or "12 months"
days = PERIODS[period_choice]


# ---------------------------------------------------------------------------
# Compare view
# ---------------------------------------------------------------------------
if app_choice == "Compare apps":
    start = analysis.period_start(data, days)
    comp = analysis.compare_apps(data, snaps, start)
    st.subheader(f"Apps side by side · {period_choice.lower()}")
    st.dataframe(
        comp, hide_index=True, width="stretch",
        column_config={
            "app": "App", "reviews": "Written reviews",
            "avg_rating": st.column_config.NumberColumn("Avg ★ (written)", format="%.2f"),
            "pct_1_star": st.column_config.NumberColumn("1★ share", format="%.1f%%"),
            "reply_rate_unhappy": st.column_config.NumberColumn("Replied to 1–2★", format="%.1f%%"),
            "store_score": st.column_config.NumberColumn("Store rating", format="%.2f"),
            "store_ratings": st.column_config.NumberColumn("Store ratings", format="%d"),
        })
    st.caption("Store rating includes people who rated without writing a review. Written reviews are the ones "
               "other users read, and they are much more critical.")
    st.stop()


# ---------------------------------------------------------------------------
# Single-app view
# ---------------------------------------------------------------------------
app_id = app_options[app_choice]
app_all = analysis.filter_period(data, app_id)
df = analysis.filter_period(app_all, start=analysis.period_start(app_all, days))
snap = analysis.latest_snapshot(snaps, app_id)
k = analysis.kpis(df, snap)
rh = analysis.reply_health(df)
summary = analysis.issue_summary(df)

if k["reviews"] < LOW_DATA:
    st.warning(f"Only {k['reviews']} written reviews in this period. Treat these numbers as anecdotes, "
               "not trends. Try a longer period.", icon=":material/warning:")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Written-review rating", f"{k['avg_rating']:.2f} ★" if k["avg_rating"] else "–",
          delta=(f"{k['avg_rating'] - k['store_score']:+.2f} vs store {k['store_score']:.2f}"
                 if k["avg_rating"] and k["store_score"] else None),
          help="Average stars of reviews with text in this period. The store rating also counts silent "
               "star-only ratings, which are mostly 5★.")
c2.metric("1★ share", f"{k['pct_1_star']:.0f}%" if k["pct_1_star"] is not None else "–",
          delta=f"{k['pct_1_star'] - k['store_pct_1_star']:+.0f} pts vs store" if k["store_pct_1_star"] and k["pct_1_star"] is not None else None,
          delta_color="inverse")
c3.metric("1–2★ reviews replied to", f"{rh['reply_rate_unhappy']:.0f}%" if rh["reply_rate_unhappy"] is not None else "–",
          delta=f"target {REPLY_TARGET}%", delta_color="off",
          help=f"{rh['unhappy_replied']} of {rh['unhappy_reviews']} unhappy reviews got a developer reply.")
c4.metric("Reviews analysed", f"{k['reviews']:,}",
          delta=(f"{k['date_from']:%d %b %Y} – {k['date_to']:%d %b %Y}" if k["reviews"] else None), delta_color="off")


# Trend + star distribution ---------------------------------------------------
trend_col, dist_col = st.columns([3, 1])
with trend_col:
    st.markdown("**Average rating by month** · written reviews")
    trend = analysis.monthly_trend(df)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=trend["month"], y=trend["avg_rating"], mode="lines+markers",
                             name="Avg ★", line=dict(width=2),
                             customdata=trend[["reviews", "pct_1_star"]],
                             hovertemplate="%{x|%b %Y}<br>%{y:.2f} ★<br>%{customdata[0]} reviews"
                                           "<br>%{customdata[1]}% 1★<extra></extra>"))
    versions = analysis.version_table(df)
    versions = versions[versions["enough_data"] & (versions["first_review"] >= df["review_date"].min())]
    for v in versions.itertuples():
        fig.add_vline(x=v.first_review, line=dict(dash="dot", width=1, color="rgba(128,128,128,0.35)"))
    if len(versions):
        # one hoverable marker per release along the bottom instead of a label per line
        fig.add_trace(go.Scatter(
            x=versions["first_review"], y=[1.15] * len(versions), mode="markers",
            marker=dict(symbol="triangle-up", size=9, color="gray"),
            customdata=versions[["version", "avg_rating", "pct_1_star", "reviews"]],
            hovertemplate="v%{customdata[0]} · first review %{x|%d %b %Y}<br>"
                          "%{customdata[1]:.2f} ★ · %{customdata[2]}% 1★ · %{customdata[3]} reviews<extra></extra>"))
    fig.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0), yaxis=dict(range=[1, 5], title=None),
                      xaxis=dict(title=None), showlegend=False)
    st.plotly_chart(fig, width="stretch")
    st.caption("▲ and dotted lines mark app releases (first review on each version with 30+ reviews). Hover for its rating.")
with dist_col:
    st.markdown("**Star distribution**")
    dist = df["rating"].value_counts().reindex([5, 4, 3, 2, 1], fill_value=0)
    bar = go.Figure(go.Bar(x=dist.values, y=[f"{s}★" for s in dist.index], orientation="h",
                           text=[f"{v / max(len(df), 1):.0%}" for v in dist.values], textposition="auto",
                           marker_color=["#4C9BE8", "#4C9BE8", "#9AA0A6", "#E5735C", "#E5735C"],
                           hovertemplate="%{y}: %{x} reviews<extra></extra>"))
    bar.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0), xaxis=dict(visible=False),
                      yaxis=dict(autorange="reversed"))  # 5★ on top
    st.plotly_chart(bar, width="stretch")


# Fix these first ---------------------------------------------------------------
def fix_form(category: str, key: str):
    """Small form to put an issue into the fix tracker."""
    status = st.radio("Status", fix_tracker.STATUSES, horizontal=True, key=f"{key}_status")
    since = st.date_input("Since", value=date.today(), key=f"{key}_date",
                          help="When work started or the fix was released. Before/after numbers use this date.")
    note = st.text_input("Note (optional)", placeholder="e.g. session timeout raised in v12.20", key=f"{key}_note")
    if st.button("Save", key=f"{key}_save", type="primary"):
        fix_tracker.set_status(app_id, category, status, since, note)
        st.rerun()


tracker = fix_tracker.load(app_id)
tracked = set(tracker["category"])
st.subheader("Fix these first")
st.caption("Ranked by estimated rating impact: how much the written-review average would rise if these unhappy "
           "reviewers had given 4★ (a ranking aid, not a forecast). Mark an issue as being fixed and the next one "
           "moves up; reviews take weeks to catch up with a fix.")
top = analysis.top_fixes(summary, exclude=tracked)
cards = st.columns(4)
for i, r in top.iterrows():
    with cards[i].container(border=True):
        st.badge(FIXABLE_LABEL[r["fixable_by"]], color=FIXABLE_COLOR[r["fixable_by"]])
        st.markdown(f"**#{i + 1} {r['issue']}**")
        plural = "s" if r["reviews"] != 1 else ""
        st.markdown(f"{r['reviews']} complaint{plural} · {r['pct_of_complaints']:.0f}% of all complaints  \n"
                    f"Could lift rating by about **+{r['uplift']:.2f}★**")
        if pd.notna(r["share_before"]) and pd.notna(r["share_last_period"]):
            change = r["share_last_period"] - r["share_before"]
            if abs(change) >= 2:
                arrow = "rising" if change > 0 else "falling"
                st.caption(f"Share {arrow}: {r['share_before']:.0f}% → {r['share_last_period']:.0f}% (last 90 days)")
        bd = analysis.sub_issue_breakdown(df, r["category"])
        specific = bd[bd["actionable"]] if not bd.empty else bd
        if not specific.empty:
            b = specific.iloc[0]
            st.markdown(f"**Start with:** {b['problem']} ({b['share']:.0f}% of these)")
            st.caption(b["first_step"])
        with st.popover("Mark as being fixed", icon=":material/build:", width="stretch"):
            fix_form(r["category"], key=f"card_{r['category']}")
if top.empty:
    cards[0].info("Every ranked issue is in the fix tracker below.")
if rh["reply_rate_unhappy"] is not None and rh["reply_rate_unhappy"] < REPLY_TARGET:
    with cards[3].container(border=True):
        st.badge("Quick win", color="green")
        st.markdown("**Reply to unhappy reviews**")
        st.markdown(f"{rh['unhappy_reviews'] - rh['unhappy_replied']} of {rh['unhappy_reviews']} 1–2★ reviews "
                    f"unanswered · no code needed")
        if rh["edited_after_reply"]:
            st.caption(f"Historically, {rh['edited_after_reply']} reviewers edited after a reply; "
                       f"{rh['edited_now_4_5']} now show 4–5★.")

# Fix tracker -------------------------------------------------------------------
if not tracker.empty:
    st.markdown("#### Being fixed: are complaints dropping?")
    st.caption("Complaints about the issue per 100 written reviews: 90 days before the date vs since. "
               "Needs 50+ reviews after the date before giving a verdict.")
    verdict_color = {"Improving": "green", "Getting worse": "red", "No clear change yet": "orange"}
    for t in tracker.itertuples():
        prog = analysis.fix_progress(app_all, t.category, t.since)
        with st.container(border=True):
            c_a, c_b, c_c, c_d = st.columns([3, 2, 2, 2], vertical_alignment="center")
            with c_a:
                st.markdown(f"**{category_name(t.category)}**  \n{t.status} since {pd.Timestamp(t.since):%d %b %Y}")
                if t.note:
                    st.caption(t.note)
            c_b.metric("Before (per 100 reviews)", prog["per_100_before"] if prog["per_100_before"] is not None else "–")
            c_c.metric("Since (per 100 reviews)", prog["per_100_after"] if prog["per_100_after"] is not None else "–",
                       delta=(f"{prog['per_100_after'] - prog['per_100_before']:+.1f}"
                              if prog["per_100_after"] is not None and prog["per_100_before"] is not None else None),
                       delta_color="inverse",
                       help=f"{prog['complaints_after']} complaints in {prog['reviews_after']} reviews since the date.")
            with c_d:
                st.badge(prog["verdict"], color=verdict_color.get(prog["verdict"], "gray"))
                if st.button("Remove", key=f"rm_{t.category}", icon=":material/close:"):
                    fix_tracker.remove(app_id, t.category)
                    st.rerun()


# Safety ------------------------------------------------------------------------
safety = analysis.safety_reviews(df)
if len(safety):
    with st.expander(f":red[**{len(safety)} safety-related complaints need human review**]", icon=":material/shield:"):
        st.caption("Flagged by keywords or the LLM. Always surfaced, regardless of volume. Some may be false alarms.")
        for s in safety.itertuples():
            st.markdown(f"- {s.rating}★ · {s.review_date:%d %b %Y} · {s.review_text}")


# All issues ----------------------------------------------------------------------
st.subheader("All issues")
if summary.empty:
    st.info("No complaints in this period.")
else:
    fl, fr = st.columns([3, 2], vertical_alignment="bottom")
    owners = fl.pills("Fixable by", list(FIXABLE_LABEL.values()), selection_mode="multi",
                      default=list(FIXABLE_LABEL.values()))
    hide_tracked = fr.toggle("Hide issues already being fixed", value=False)
    view = summary[summary["fixable_by"].map(FIXABLE_LABEL).isin(owners or list(FIXABLE_LABEL.values()))]
    if hide_tracked:
        view = view[~view["category"].isin(tracked)]
    view = view.reset_index(drop=True)
    table = view.assign(
        trend=view.apply(lambda r: "not enough data" if pd.isna(r["share_before"]) or pd.isna(r["share_last_period"])
                         else ("▲ rising" if r["share_last_period"] - r["share_before"] >= 2
                               else "▼ falling" if r["share_before"] - r["share_last_period"] >= 2 else "–"), axis=1),
        fixable=view["fixable_by"].map(FIXABLE_LABEL),
        status=view["category"].map(dict(zip(tracker["category"], tracker["status"]))).fillna(""),
    )[["issue", "fixable", "reviews", "pct_of_complaints", "avg_rating", "uplift", "trend", "status"]]
    st.caption("Click a row (or pick below) to see what exactly people report, where to start, and the reviews.")
    event = st.dataframe(
        table, hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row",
        column_config={
            "issue": "Issue", "fixable": "Fixable by", "reviews": "Complaints",
            "pct_of_complaints": st.column_config.ProgressColumn("Share of complaints", format="%.0f%%",
                                                                 min_value=0, max_value=100),
            "avg_rating": st.column_config.NumberColumn("Avg ★", format="%.1f"),
            "uplift": st.column_config.NumberColumn("Rating impact", format="+%.2f ★"),
            "trend": "Last 90 days", "status": "Fix status",
        })

    if not view.empty:
        clicked = event.selection.rows[0] if event.selection.rows else None
        non_safety = view.index[view["category"] != "safety"]
        default_idx = clicked if clicked is not None else (int(non_safety[0]) if len(non_safety) else 0)
        pick = st.selectbox("Look closer at", view["issue"].tolist(), index=default_idx, key=f"pick_{clicked}")
        row = view[view["issue"] == pick].iloc[0]
        cat = row["category"]

        st.markdown(f"### {row['issue']}: what exactly, and where to start")
        bd = analysis.sub_issue_breakdown(df, cat)
        if not bd.empty:
            st.dataframe(
                bd[["problem", "complaints", "share", "avg_rating", "first_step"]], hide_index=True, width="stretch",
                column_config={
                    "problem": st.column_config.TextColumn("Specific problem", width="medium"),
                    "complaints": "Complaints",
                    "share": st.column_config.ProgressColumn("Share of this issue", format="%.0f%%",
                                                             min_value=0, max_value=100),
                    "avg_rating": st.column_config.NumberColumn("Avg ★", format="%.1f"),
                    "first_step": st.column_config.TextColumn("Suggested first step", width="large"),
                })
            st.caption("Suggested first steps are starting points based on what reviewers describe, not verified "
                       "root causes. Edit them in src/playbook.py.")

        st.markdown("**Read the reviews**")
        rows = df[df["is_complaint"] & (df["primary_category"] == cat)].copy()
        sub_names = {s: analysis.sub_issue_name(cat, s) for s in rows["sub_issue"].dropna().unique()}
        r1, r2, r3 = st.columns([2, 2, 3])
        sub_pick = r1.selectbox("Specific problem", ["All"] + sorted(sub_names.values()), key=f"sub_{cat}")
        version_opts = sorted(
            rows["review_version"].dropna().astype(str).str.extract(r"^(\d+\.\d+)")[0].dropna().unique(),
            key=lambda v: tuple(int(x) for x in v.split(".")), reverse=True)
        ver_pick = r2.selectbox("App version", ["All"] + version_opts, key=f"ver_{cat}")
        search = r3.text_input("Search in text", placeholder="otp, update, driver…", key=f"q_{cat}")
        r4, r5, r6 = st.columns([2, 2, 3])
        stars = r4.pills("Stars", [1, 2, 3], selection_mode="multi", default=[1, 2, 3],
                         format_func=lambda s: f"{s}★", key=f"stars_{cat}")
        sort = r5.selectbox("Sort by", ["Lowest rating", "Most liked", "Newest"], key=f"sort_{cat}")
        show_n = r6.select_slider("Show", options=[5, 10, 25, 50, 100], value=10, key=f"n_{cat}")

        if sub_pick != "All":
            rows = rows[rows["sub_issue"].map(sub_names) == sub_pick]
        if ver_pick != "All":
            v = rows["review_version"].astype(str)
            rows = rows[v.str.startswith(ver_pick + ".") | (v == ver_pick)]
        if search:
            rows = rows[rows["review_text"].fillna("").str.contains(search, case=False, regex=False)]
        rows = rows[rows["rating"].isin(stars or [1, 2, 3])]
        order = {"Lowest rating": (["rating", "thumbs_up", "review_date"], [True, False, False]),
                 "Most liked": (["thumbs_up", "rating", "review_date"], [False, True, False]),
                 "Newest": (["review_date"], [False])}[sort]
        rows = rows.sort_values(order[0], ascending=order[1])
        st.caption(f"Showing {min(show_n, len(rows))} of {len(rows)} matching complaints.")
        for e in rows.head(show_n).itertuples():
            with st.container(border=True):
                st.markdown(f"{'★' * int(e.rating)}{'☆' * (5 - int(e.rating))} · {e.review_date:%d %b %Y}"
                            f"{f' · v{e.review_version}' if isinstance(e.review_version, str) else ''}"
                            f"{f' · 👍 {e.thumbs_up}' if e.thumbs_up else ''}"
                            f" · *{analysis.sub_issue_name(cat, e.sub_issue)}*")
                st.write(e.review_text)
                how = (f"Keyword match: {e.matched_keywords}" if e.label_source == "rule"
                       else f"Classified by LLM: {e.llm_reason}")
                st.caption(how)


# Export ------------------------------------------------------------------------
st.subheader("Export")
e1, e2 = st.columns(2)
export_cols = ["app_id", "review_id", "review_date", "rating", "review_version", "thumbs_up", "review_text",
               "issue_name", "sub_issue", "fixable_by", "categories", "label_source", "matched_keywords", "llm_reason",
               "is_safety", "has_reply"]
e1.download_button("Download reviews (CSV)", df[export_cols].to_csv(index=False).encode("utf-8-sig"),
                   file_name=f"moveinsync_reviews_{app_id}_{period_choice.replace(' ', '')}.csv",
                   mime="text/csv", icon=":material/download:", width="stretch")
e2.download_button("Download issue summary (CSV)", summary.to_csv(index=False).encode("utf-8-sig"),
                   file_name=f"moveinsync_issues_{app_id}_{period_choice.replace(' ', '')}.csv",
                   mime="text/csv", icon=":material/download:", width="stretch")


# How this works -----------------------------------------------------------------
cov = analysis.uncategorised(df)
with st.expander("How this works and what it can't tell you", icon=":material/info:"):
    st.markdown(f"""
**Data.** Public Google Play reviews collected with the unofficial `google-play-scraper` library
(not an official Google API). Reviewer names are never stored. Store rating and star counts come from
the listing page and include people who rated without writing anything.

**Classification.** Each complaint (1–3★) is matched against editable keyword rules in `src/config.py`
(English and Hinglish, whole-word matching). Reviews the rules can't place are labelled by Google Gemini
using the same fixed categories, each with a one-line reason; a person approves any new keyword.
In this view: {cov['by_rules']} complaints labelled by rules, {cov['by_llm']} by the LLM,
{cov['pct_unclassified'] if cov['pct_unclassified'] is not None else 0}% still unclassified,
{cov['low_info']} too short to classify ("bad", "worst app").
On 100 held-out reviews, rules alone got the main issue right 63% of the time; rules + LLM 75% (90% counting a second issue).

**Rating impact.** For each issue: the sum of (4 − rating) over its 1–2★ reviews, divided by all written reviews
in the period. It answers "if these reviewers had been satisfied (4★), how much would the written-review
average rise?" It is for ranking, not a forecast.

**Limitations.**
- Reviews describe experiences, not verified root causes. Use them to decide where to look first.
- People who write reviews are more critical than the silent majority.
- Google shows only the latest version of an edited review.
- Shift slang ("login cab", "logout cab") can confuse keyword matching.
""")
