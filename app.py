"""Ratings radar: MoveInSync Play Store review dashboard.

    streamlit run app.py

Reads data/reviews_labelled.csv (built by the refresh pipeline), so it opens in seconds and
needs no network. "Refresh data" fetches new reviews and, when allowed, labels only the new
unclassified ones with Gemini.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import analysis, benchmark, config, fix_tracker, pipeline, replies
from src.classifier import category_name
from src.playbook import EFFORT, VERIFY_FROM_REVIEWS

st.set_page_config(page_title="Ratings radar · MoveInSync", page_icon="⭐", layout="wide")

PERIODS = {"30 days": 30, "90 days": 90, "6 months": 182, "12 months": 365, "All time": None}
LOW_DATA = 30
REPLY_TARGET = 80
FIXABLE_LABEL = {"App": "App fix", "Ops": "Ops fix", "Review": "Human review"}
FIXABLE_COLOR = {"App": "blue", "Ops": "orange", "Review": "red"}
STATUS_COLOR = {"OK": "green", "WATCH": "orange", "ALERT": "red"}
STATUS_ICON = {"OK": ":material/check_circle:", "WATCH": ":material/visibility:", "ALERT": ":material/warning:"}

# Plain-English definitions, used as tooltips and on the "How it works" page.
GLOSSARY = {
    "Store rating": "The star rating shown on the Play Store. It counts everyone who rated, including the many "
                    "people who only tapped a star (mostly 5★) without writing anything.",
    "Written-review rating": "The average stars of reviews that include text. These are the reviews other users "
                             "read, and they are much more critical than the store rating.",
    "Complaint": "A written review with 1, 2 or 3 stars.",
    "Rating impact": "How much the written-review average would rise if the unhappy (1–2★) reviewers of this issue "
                     "had been satisfied enough to give 4★. Used to rank issues; not a forecast.",
    "Per 100 reviews": "How many complaints about an issue appear for every 100 written reviews. Used to compare "
                       "before and after a fix, even if the number of reviews changes.",
    "App fix / Ops fix": "App fix: the app team can solve it (bugs, design). Ops fix: transport operations, vendors "
                         "or drivers need to act. Human review: safety concerns someone must read.",
    "Specific problem": "A narrower complaint inside an issue (for example, inside Login: OTP not received).",
    "Effort (1–5)": "A rough guess of how hard a fix is. " + " · ".join(f"{k} = {v}" for k, v in EFFORT.items()) + ".",
    "Check first": "What to look at in MoveInSync's own systems before building anything, to confirm that the "
                   "cause reviewers describe is real.",
    "Plausible range": "With few reviews, a number can move a lot by chance. The shaded band or whisker shows "
                       "where the true value most likely is (95%). If two ranges overlap, the difference may be chance.",
    "Status": "OK = nothing unusual. WATCH = something is worth a look (a rising complaint, few replies, a worse "
              "release). ALERT = 1★ reviews jumped sharply in the last 30 days.",
    "Low-info review": "Very short reviews like \"bad\" or \"worst app\". They count towards ratings but say nothing "
                       "about what went wrong.",
    "Labelled by rules / by LLM": "Most reviews are sorted by keyword rules you can read in the code. Reviews the "
                                  "rules miss (often Hinglish) are sorted by Google Gemini with a one-line reason.",
}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner="Loading reviews…")
def load_data(fingerprint: str) -> pd.DataFrame:  # fingerprint: cache key that changes when inputs change
    return pipeline.load_labelled()


@st.cache_data
def load_snapshots(_mtime: float) -> pd.DataFrame | None:
    return pd.read_csv(config.SNAPSHOTS_CSV) if config.SNAPSHOTS_CSV.exists() else None


def _mtime(path) -> float:
    return path.stat().st_mtime if path.exists() else 0.0


def last_updated() -> str:
    if not config.FETCH_LOG_CSV.exists():
        return "never"
    t = pd.to_datetime(pd.read_csv(config.FETCH_LOG_CSV)["run_time"]).max()
    return f"{t:%d %b %Y, %H:%M} UTC"


def run_refresh():
    with st.status("Refreshing data…", expanded=True) as status:
        st.write("Fetching new reviews from Google Play…")
        use_llm = pipeline.llm_allowed()
        result = pipeline.run(log=lambda m: None, use_llm=use_llm)
        st.write(f"{result['new_reviews']} new reviews.")
        if result["errors"]:
            st.warning("Some sources failed; previously saved data was kept:\n\n- " + "\n- ".join(result["errors"]))
        if result["llm"]:
            st.write(f"Gemini labelled {result['llm']['labelled']} new unclassified complaints"
                     + (f"; {result['llm']['held_back']} left for later." if result["llm"]["held_back"] else "."))
        elif not use_llm:
            st.write("New reviews were classified by keyword rules only (LLM not enabled here).")
        status.update(label="Data refreshed", state="complete")
    st.cache_data.clear()


# ---------------------------------------------------------------------------
# Look and feel: tinted page, white cards (navy/slate in dark mode)
# ---------------------------------------------------------------------------
def inject_css():
    dark = getattr(st.context.theme, "type", "light") == "dark"
    card, border = ("#131C2E", "#24324A") if dark else ("#FFFFFF", "#E2E8F0")
    shadow = "none" if dark else "0 1px 2px rgba(15,23,42,.06), 0 1px 3px rgba(15,23,42,.04)"
    muted = "#94A3B8" if dark else "#64748B"
    st.html(f"""<style>
    .block-container {{ padding-top: 2.2rem; padding-left: 2.5rem; padding-right: 2.5rem; }}
    [class*="st-key-card"] {{ background: {card}; border: 1px solid {border} !important; border-radius: 14px;
        box-shadow: {shadow}; padding: 14px 16px 10px 16px; }}
    [class*="st-key-card-app"] {{ border-top: 4px solid #3B82F6 !important; }}
    [class*="st-key-card-ops"] {{ border-top: 4px solid #F59E0B !important; }}
    [class*="st-key-card-win"] {{ border-top: 4px solid #22C55E !important; }}
    [class*="st-key-panel"] {{ background: {card}; border: 1px solid {border} !important; border-radius: 14px;
        box-shadow: {shadow}; padding: 6px 14px; }}
    [data-testid="stMetric"] {{ background: {card}; border: 1px solid {border}; border-radius: 14px;
        box-shadow: {shadow}; padding: 12px 14px 4px 14px; }}
    [data-testid="stSidebar"] {{ border-right: 1px solid {border}; }}
    .brand {{ font-weight: 700; font-size: 1.15rem; letter-spacing: -0.01em; }}
    .brand-sub {{ color: {muted}; font-size: 0.8rem; margin-top: -2px; }}
    .muted {{ color: {muted}; font-size: 0.8rem; }}
    .verdict {{ border-radius: 14px; padding: 16px 18px; margin: 4px 0 18px 0; }}
    .verdict .head {{ font-size: 1.2rem; font-weight: 650; line-height: 1.35; }}
    .verdict .sub {{ font-size: 0.92rem; margin-top: 6px; opacity: .85; }}
    .eyebrow {{ text-transform: uppercase; letter-spacing: .06em; font-size: .72rem; font-weight: 600;
        color: {muted}; margin: 6px 0 6px 0; }}
    </style>""")


VERDICT_STYLE = {
    "OK": ("rgba(34,197,94,.12)", "#22C55E", "All steady"),
    "WATCH": ("rgba(245,158,11,.14)", "#F59E0B", "Watch"),
    "ALERT": ("rgba(239,68,68,.14)", "#EF4444", "Alert"),
}


# ---------------------------------------------------------------------------
# Sidebar: brand, pages, filters, refresh
# ---------------------------------------------------------------------------
inject_css()

if not config.REVIEWS_CSV.exists():
    st.info("No data yet. Run `python refresh.py` to fetch reviews (a few minutes the first time).")
    st.stop()

data = load_data(pipeline._fingerprint())
snaps = load_snapshots(_mtime(config.SNAPSHOTS_CSV))
bench = benchmark.latest()

with st.sidebar:
    st.html('<div class="brand">⭐ Ratings radar</div>'
            '<div class="brand-sub">MoveInSync · Google Play reviews</div>')
    nav_box = st.container()
    st.divider()
    app_options = {meta["name"]: app_id for app_id, meta in config.APPS.items()}
    app_choice = st.segmented_control("App", list(app_options), default=next(iter(app_options)), key="f_app")
    period_choice = st.segmented_control("Period", list(PERIODS), default="12 months", key="f_period")
    st.divider()
    st.html(f'<div class="muted">Updated {last_updated()}<br>Auto-refresh every Monday</div>')
    if st.button("Refresh now", icon=":material/refresh:", width="stretch",
                 help="Fetch new reviews from Google Play (under a minute)."):
        run_refresh()

app_choice = app_choice or next(iter(app_options))
period_choice = period_choice or "12 months"
days = PERIODS[period_choice]
app_id = app_options[app_choice]
app_all = analysis.filter_period(data, app_id)
df = analysis.filter_period(app_all, start=analysis.period_start(app_all, days))
snap = analysis.latest_snapshot(snaps, app_id)
k = analysis.kpis(df, snap)
rh = analysis.reply_health(df)
summary = analysis.issue_summary(df)
tracker = fix_tracker.load(app_id)
tracked = set(tracker["category"])
status = analysis.weekly_status(app_all)
GEMINI_DRAFTS_PER_SESSION = 20   # protects the API budget; saved drafts don't count


def fix_form(category: str, key: str, note_default: str = ""):
    """Small form to put an issue into the fix tracker."""
    status_pick = st.radio("Status", fix_tracker.STATUSES, horizontal=True, key=f"{key}_status")
    since = st.date_input("Since", value=date.today(), key=f"{key}_date",
                          help="When work started or the fix was released. Before/after numbers use this date.")
    note = st.text_input("Note (optional)", value=note_default, placeholder="e.g. session timeout raised in v12.20",
                         key=f"{key}_note")
    if st.button("Save", key=f"{key}_save", type="primary"):
        fix_tracker.set_status(app_id, category, status_pick, since, note)
        st.rerun()


def page_header(title: str, subtitle: str = ""):
    st.markdown(f"## {title}")
    if subtitle:
        st.caption(subtitle)
    if k["reviews"] < LOW_DATA:
        st.warning(f"Only {k['reviews']} written reviews for {app_choice} in this period, so treat these numbers as "
                   f"anecdotes. Try a longer period.", icon=":material/warning:")


# ---------------------------------------------------------------------------
# Overview page: the answer and the actions first; details one click away
# ---------------------------------------------------------------------------
def page_overview():
    top = analysis.top_fixes(summary, n=3, exclude=tracked)
    cards = []
    for _, r in top.iterrows():
        bd = analysis.sub_issue_breakdown(df, r["category"])
        spec = bd[bd["actionable"]] if not bd.empty else bd
        cards.append((r, spec.iloc[0] if not spec.empty else None))

    # Verdict: one line + one short line
    bg, edge, word = VERDICT_STYLE[status["status"]]
    phrases = status["short"][:2]
    head = f"{word}: {' and '.join(phrases)}" if status["status"] != "OK" else "All steady: nothing unusual lately"
    bits = []
    if not bench.empty and app_id in set(bench["app_id"]):
        peers = bench[bench["group"] == "Employee transport"]
        me = bench[bench["app_id"] == app_id].iloc[0]
        if len(peers):
            rank = int((peers["store_score"] > me["store_score"]).sum()) + 1
            bits.append(f"#{rank} of {len(peers) + 1} employee-transport apps ({me['store_score']:.2f}★)")
    if cards:
        bits.append(f"fix first: {cards[0][0]['issue'].split(',')[0]}")
    st.html(f'<div class="verdict" style="background:{bg};border-left:5px solid {edge}">'
            f'<div class="head">{head[0].upper() + head[1:]}</div>'
            f'<div class="sub">{" · ".join(bits)}</div></div>')

    # Do this next
    st.html('<div class="eyebrow">Do this next</div>')
    cols = st.columns(4, gap="medium")
    for i, (r, spec) in enumerate(cards):
        kind = "app" if r["fixable_by"] == "App" else "ops"
        with cols[i]:
            with st.container(key=f"card-{kind}-{i}"):
                tags = st.container(horizontal=True, gap="small")
                tags.badge(FIXABLE_LABEL[r["fixable_by"]], color=FIXABLE_COLOR[r["fixable_by"]])
                if pd.notna(r["share_before"]) and r["share_last_period"] - r["share_before"] >= analysis.STATUS_RULES["watch_issue_rise"]:
                    tags.badge("Rising", color="red", icon=":material/trending_up:")
                st.markdown(f"**{i + 1}. {r['issue']}**")
                st.caption(f"{r['pct_of_complaints']:.0f}% of complaints · could add +{r['uplift']:.2f}★")
                if spec is not None:
                    st.markdown(f"Start with **{spec['problem']}**")
                    st.progress(min(1.0, spec["share"] / 100), text=f"{spec['share']:.0f}% of these complaints")
                    st.caption(f"{spec['owner']} · effort {int(spec['effort'])}/5")
                with st.popover("Track this fix", icon=":material/build:", width="stretch"):
                    fix_form(r["category"], key=f"ov_{r['category']}",
                             note_default=spec["problem"] if spec is not None else "")
    if not cards:
        cols[0].info("Every ranked issue is in the fix tracker.")
    if rh["reply_rate_unhappy"] is not None and rh["reply_rate_unhappy"] < REPLY_TARGET:
        with cols[3]:
            with st.container(key="card-win"):
                st.badge("Quick win", color="green", icon=":material/bolt:")
                st.markdown("**Reply to unhappy reviews**")
                st.caption(f"{rh['unhappy_reviews'] - rh['unhappy_replied']} of {rh['unhappy_reviews']} unanswered "
                           f"· no code needed")
                st.progress(min(1.0, rh["reply_rate_unhappy"] / 100),
                            text=f"{rh['reply_rate_unhappy']:.0f}% answered (aim for {REPLY_TARGET}%)")
                if rh["edited_after_reply"]:
                    st.caption(f"{rh['edited_now_4_5']} of {rh['edited_after_reply']} who got a reply now show 4–5★")
                st.page_link(PAGES["replies"], label="Start replying", icon=":material/arrow_forward:")

    safety = analysis.safety_reviews(df)
    if len(safety):
        st.page_link(PAGES["issues"], icon=":material/shield:",
                     label=f"{len(safety)} safety-related complaints need someone to read them")

    # The numbers
    st.html('<div class="eyebrow" style="margin-top:14px">The numbers</div>')
    trend = analysis.monthly_trend(df).tail(12)
    rival = bench[bench["name"] == "Routematic"].iloc[0] if not bench.empty and "Routematic" in set(bench["name"]) else None
    refs = bench[bench["group"] == "Ride-hailing (reference)"] if not bench.empty else bench
    m1, m2, m3, m4 = st.columns(4, gap="medium")
    m1.metric("Store rating", f"{k['store_score']:.2f}★" if k["store_score"] else "–",
              delta=f"{k['store_ratings']:,} ratings" if k["store_ratings"] else None,
              delta_color="off", delta_arrow="off", help=GLOSSARY["Store rating"])
    ref_txt = " · ".join(f"{r['name']} {r['written_avg']:.2f}" for _, r in refs.head(2).iterrows()) if len(refs) else None
    m2.metric("Written-review rating", f"{k['avg_rating']:.2f}★" if k["avg_rating"] else "–",
              delta=ref_txt, delta_color="off", delta_arrow="off",
              chart_data=trend["avg_rating"].tolist() if len(trend) > 2 else None, chart_type="line",
              help=GLOSSARY["Written-review rating"])
    m3.metric("1★ share", f"{k['pct_1_star']:.0f}%" if k["pct_1_star"] is not None else "–",
              delta=f"Routematic {rival['pct_1_star']:.0f}%" if rival is not None else None,
              delta_color="off", delta_arrow="off",
              chart_data=trend["pct_1_star"].tolist() if len(trend) > 2 else None, chart_type="line")
    m4.metric("Replies to 1–2★",
              f"{rh['reply_rate_unhappy']:.0f}%" if rh["reply_rate_unhappy"] is not None else "–",
              delta=f"Routematic {rival['reply_rate_unhappy']:.0f}%" if rival is not None else f"aim for {REPLY_TARGET}%",
              delta_color="off", delta_arrow="off",
              chart_data=trend["pct_replied"].tolist() if len(trend) > 2 else None, chart_type="line")

    with st.expander("See the trends: rating by month, star mix, releases", icon=":material/monitoring:"):
        render_trends()
    with st.expander("Why this status?", icon=":material/help:"):
        for reason in status["reasons"]:
            st.markdown(f"- {reason}")
        st.caption("Simple published rules; see How it works.")


def render_trends():
    trend_col, dist_col = st.columns([3, 1])
    with trend_col:
        st.markdown("**Average rating by month** · written reviews")
        trend = analysis.monthly_ranges(df)
        fig = go.Figure()
        band = trend.dropna(subset=["avg_lo", "avg_hi"])
        if len(band):
            fig.add_trace(go.Scatter(x=pd.concat([band["month"], band["month"][::-1]]),
                                     y=pd.concat([band["avg_hi"], band["avg_lo"][::-1]]),
                                     fill="toself", fillcolor="rgba(59,130,246,0.15)", line=dict(width=0),
                                     hoverinfo="skip", showlegend=False))
        fig.add_trace(go.Scatter(x=trend["month"], y=trend["avg_rating"], mode="lines+markers",
                                 name="Avg ★", line=dict(width=2, color="#3B82F6"),
                                 customdata=trend[["reviews", "pct_1_star"]],
                                 hovertemplate="%{x|%b %Y}<br>%{y:.2f} ★<br>%{customdata[0]} reviews"
                                               "<br>%{customdata[1]}% 1★<extra></extra>"))
        versions = analysis.version_table(df)
        versions = versions[versions["enough_data"] & (versions["first_review"] >= df["review_date"].min())]
        for v in versions.itertuples():
            fig.add_vline(x=v.first_review, line=dict(dash="dot", width=1, color="rgba(128,128,128,0.35)"))
        if len(versions):
            fig.add_trace(go.Scatter(
                x=versions["first_review"], y=[1.15] * len(versions), mode="markers",
                marker=dict(symbol="triangle-up", size=9, color="gray"),
                customdata=versions[["version", "avg_rating", "pct_1_star", "reviews"]],
                hovertemplate="v%{customdata[0]} · first review %{x|%d %b %Y}<br>"
                              "%{customdata[1]:.2f} ★ · %{customdata[2]}% 1★ · %{customdata[3]} reviews<extra></extra>"))
        fig.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0), yaxis=dict(range=[1, 5], title=None),
                          xaxis=dict(title=None), showlegend=False)
        st.plotly_chart(fig, width="stretch")
        st.caption("Shaded band: plausible range for each month. ▲ marks app releases (30+ reviews).",
                   help=GLOSSARY["Plausible range"])
    with dist_col:
        st.markdown("**Star mix**")
        dist = df["rating"].value_counts().reindex([5, 4, 3, 2, 1], fill_value=0)
        bar = go.Figure(go.Bar(x=dist.values, y=[f"{s}★" for s in dist.index], orientation="h",
                               text=[f"{v / max(len(df), 1):.0%}" for v in dist.values], textposition="auto",
                               marker_color=["#3B82F6", "#3B82F6", "#94A3B8", "#EF4444", "#EF4444"],
                               hovertemplate="%{y}: %{x} reviews<extra></extra>"))
        bar.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0), xaxis=dict(visible=False),
                          yaxis=dict(autorange="reversed"))
        st.plotly_chart(bar, width="stretch")

    vr = analysis.version_ranges(df)
    vr = vr[vr["reviews"] >= 10] if not vr.empty else vr
    if not vr.empty:
        st.markdown("**Did a release make things worse?** 1★ share by app version")
        colors = ["#3B82F6" if ok else "rgba(150,150,150,0.5)" for ok in vr["enough_data"]]
        vfig = go.Figure(go.Bar(
            x=["v" + v for v in vr["version"]], y=vr["pct_1_star"], marker_color=colors,
            error_y=dict(type="data", symmetric=False, array=vr["pct_1_hi"] - vr["pct_1_star"],
                         arrayminus=vr["pct_1_star"] - vr["pct_1_lo"], color="gray", thickness=1),
            customdata=vr[["reviews", "pct_1_lo", "pct_1_hi"]],
            hovertemplate="%{x}: %{y:.0f}% 1★ (plausible %{customdata[1]:.0f}–%{customdata[2]:.0f}%)"
                          "<br>%{customdata[0]} reviews<extra></extra>"))
        vfig.update_layout(height=260, margin=dict(l=0, r=0, t=10, b=0),
                           yaxis=dict(title="% 1★", rangemode="tozero"))
        st.plotly_chart(vfig, width="stretch")
        st.caption("Whiskers show the plausible range; overlapping whiskers may just be chance. Grey: under 30 reviews.")


# ---------------------------------------------------------------------------
# Issues page
# ---------------------------------------------------------------------------
def page_issues():
    page_header("Issues", "What people complain about, what exactly, and what to do. Click a row to look closer.")
    safety = analysis.safety_reviews(df)
    if len(safety):
        with st.expander(f":red[**{len(safety)} safety-related complaints need someone to read them**]",
                         icon=":material/shield:"):
            st.caption("Flagged by keywords or the LLM. Always shown, however few. Some may be false alarms.")
            for s_ in safety.itertuples():
                st.markdown(f"- {s_.rating}★ · {s_.review_date:%d %b %Y} · {s_.review_text}")

    if summary.empty:
        st.info("No complaints in this period.")
    else:
        fl, fr = st.columns([3, 2], vertical_alignment="bottom")
        owners = fl.pills("Fixable by", list(FIXABLE_LABEL.values()), selection_mode="multi",
                          default=list(FIXABLE_LABEL.values()), help=GLOSSARY["App fix / Ops fix"])
        hide_tracked = fr.toggle("Hide issues already being fixed", value=False)
        view = summary[summary["fixable_by"].map(FIXABLE_LABEL).isin(owners or list(FIXABLE_LABEL.values()))]
        if hide_tracked:
            view = view[~view["category"].isin(tracked)]
        view = view.reset_index(drop=True)
        table = view.assign(
            trend=view.apply(lambda r: "not enough data" if pd.isna(r["share_before"]) or pd.isna(r["share_last_period"])
                             else ("▲ rising" if r["share_last_period"] - r["share_before"] >= 2
                                   else "▼ falling" if r["share_before"] - r["share_last_period"] >= 2 else "–"),
                             axis=1),
            fixable=view["fixable_by"].map(FIXABLE_LABEL),
            status=view["category"].map(dict(zip(tracker["category"], tracker["status"]))).fillna(""),
        )[["issue", "fixable", "reviews", "pct_of_complaints", "avg_rating", "uplift", "trend", "status"]]
        st.caption("Click a row (or pick below) to see what exactly people report, where to start, and the reviews.")
        event = st.dataframe(
            table, hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row",
            column_config={
                "issue": "Issue", "fixable": "Fixable by",
                "reviews": st.column_config.NumberColumn("Complaints", help=GLOSSARY["Complaint"]),
                "pct_of_complaints": st.column_config.ProgressColumn("Share of complaints", format="%.0f%%",
                                                                     min_value=0, max_value=100),
                "avg_rating": st.column_config.NumberColumn("Avg ★", format="%.1f"),
                "uplift": st.column_config.NumberColumn("Rating impact", format="+%.2f ★",
                                                        help=GLOSSARY["Rating impact"]),
                "trend": "Last 90 days", "status": "Fix status",
            })

        if not view.empty:
            clicked = event.selection.rows[0] if event.selection.rows else None
            non_safety = view.index[view["category"] != "safety"]
            default_idx = clicked if clicked is not None else (int(non_safety[0]) if len(non_safety) else 0)
            pick = st.selectbox("Look closer at", view["issue"].tolist(), index=default_idx, key=f"pick_{clicked}")
            row = view[view["issue"] == pick].iloc[0]
            cat = row["category"]

            st.markdown(f"### {row['issue']}: what exactly, and what to do")
            bd = analysis.sub_issue_breakdown(df, cat)
            if not bd.empty:
                left, right = st.columns([2, 3])
                with left:
                    st.markdown("**What people complain about**")
                    st.dataframe(
                        bd[["problem", "complaints", "share"]], hide_index=True, width="stretch",
                        column_config={
                            "problem": st.column_config.TextColumn("Specific problem", help=GLOSSARY["Specific problem"]),
                            "complaints": "Complaints",
                            "share": st.column_config.ProgressColumn("Share", format="%.0f%%",
                                                                     min_value=0, max_value=100),
                        })
                    vague = bd[~bd["actionable"]]
                    if not vague.empty:
                        st.caption(f"{int(vague['complaints'].sum())} complaints are too vague to point at a specific "
                                   f"problem (\"not working\", \"worst app\"), so they have no action card.")
                with right:
                    st.markdown("**Action cards**, largest problem first")
                    st.caption("Starting points based on what reviewers describe. Confirm the cause with "
                               "**Check first** before building.")
                    for j, c in enumerate(bd[bd["actionable"]].itertuples()):
                        with st.expander(f"**{c.problem}** · {c.complaints} complaints ({c.share:.0f}%)",
                                         expanded=(j == 0)):
                            st.markdown(f"**What to do:** {c.first_step}")
                            w1, w2 = st.columns(2)
                            w1.markdown(f"**Who:** {c.owner}")
                            w2.markdown(f"**Effort:** {'●' * int(c.effort)}{'○' * (5 - int(c.effort))} "
                                        f"{int(c.effort)}/5 · {EFFORT[int(c.effort)]}",
                                        help=GLOSSARY["Effort (1–5)"])
                            st.markdown(f"**Check first** (MoveInSync's own data): {c.check_first}",
                                        help=GLOSSARY["Check first"])
                            st.markdown(f"**How you'll know it worked:**  \n"
                                        f"- In MoveInSync's data, watch: {c.measure}.  \n"
                                        f"- In reviews: {VERIFY_FROM_REVIEWS}")
                            with st.popover("Track this fix", icon=":material/build:"):
                                fix_form(cat, key=f"issue_{cat}_{c.sub_issue}", note_default=c.problem)

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

    st.divider()
    st.markdown("**Download**")
    e1, e2 = st.columns(2)
    export_cols = ["app_id", "review_id", "review_date", "rating", "review_version", "thumbs_up", "review_text",
                   "issue_name", "sub_issue", "fixable_by", "categories", "label_source", "matched_keywords",
                   "llm_reason", "is_safety", "has_reply"]
    e1.download_button("Reviews with labels (CSV)", df[export_cols].to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"moveinsync_reviews_{app_id}_{period_choice.replace(' ', '')}.csv",
                       mime="text/csv", icon=":material/download:", width="stretch")
    e2.download_button("Issue summary (CSV)", summary.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"moveinsync_issues_{app_id}_{period_choice.replace(' ', '')}.csv",
                       mime="text/csv", icon=":material/download:", width="stretch")


# ---------------------------------------------------------------------------
# Reply to reviews page
# ---------------------------------------------------------------------------
def page_replies():
    page_header("Replies", "Answer unhappy reviews in a few clicks.")

    todo = replies.unanswered(df)
    unhappy_total = int((df["rating"] <= 2).sum())
    bench_now = benchmark.latest()
    rival = bench_now[bench_now["name"] == "Routematic"] if not bench_now.empty else bench_now
    why = (f" For comparison, Routematic replies to {rival.iloc[0]['reply_rate_unhappy']:.0f}% of its recent 1–2★ "
           f"reviews." if len(rival) and pd.notna(rival.iloc[0]["reply_rate_unhappy"]) else "")
    st.markdown(f"**{len(todo)} of {unhappy_total} unhappy (1–2★) reviews in this period have no reply.**{why}")
    st.caption("Pick a review, get a suggested reply, check it, copy it, and post it in Google Play Console → "
               "Ratings and reviews. Nothing is posted from here. Replace [support email] before posting.")

    gemini_ok = pipeline.llm_allowed()
    used = st.session_state.setdefault("gemini_drafts_used", 0)
    if not gemini_ok:
        st.info("Suggested replies use ready-made templates for each problem (no AI). Gemini drafts are switched "
                "off here.", icon=":material/info:")

    if todo.empty:
        st.success("Every unhappy review in this period has a reply.")
    else:
        q1, q2, q3 = st.columns([3, 2, 2])
        issue_names = sorted(todo["issue_name"].dropna().unique())
        issue_pick = q1.selectbox("Issue", ["All"] + issue_names, key="reply_issue")
        min_words = q2.selectbox("Length", ["Any length", "At least 8 words"], index=1, key="reply_len",
                                 help="Longer reviews say more, so they're more useful to answer first.")
        show_n = q3.select_slider("Show", options=[5, 10, 20, 50], value=10, key="reply_n")
        view = todo
        if issue_pick != "All":
            view = view[view["issue_name"] == issue_pick]
        if min_words != "Any length":
            view = view[view["review_text"].fillna("").str.split().str.len() >= 8]
        st.caption(f"Showing {min(show_n, len(view))} of {len(view)}, newest first.")

        for e in view.head(show_n).itertuples():
            problem = (analysis.sub_issue_name(e.primary_category, e.sub_issue)
                       if isinstance(e.sub_issue, str) else e.issue_name)
            with st.container(border=True):
                st.markdown(f"{'★' * int(e.rating)}{'☆' * (5 - int(e.rating))} · {e.review_date:%d %b %Y} · "
                            f"*{e.issue_name}{f' → {problem}' if problem != e.issue_name else ''}*")
                st.write(e.review_text)
                key = f"draft_{e.review_id}"
                b1, b2, _ = st.columns([2, 2, 3])
                if b1.button("Suggest a reply", key=f"tpl_{e.review_id}", icon=":material/edit_note:"):
                    st.session_state[key] = (replies.template_reply(e.primary_category, e.sub_issue), "template")
                if gemini_ok:
                    saved = replies.cached_draft(e.review_id)
                    label = "Show Gemini draft" if saved else "Write with Gemini"
                    if b2.button(label, key=f"ai_{e.review_id}", icon=":material/auto_awesome:",
                                 disabled=(not saved and used >= GEMINI_DRAFTS_PER_SESSION),
                                 help=f"One call per review; saved so it never costs twice. "
                                      f"{GEMINI_DRAFTS_PER_SESSION - used} new drafts left this session."):
                        with st.spinner("Writing…"):
                            text, source = replies.llm_reply(e.review_id, e.review_text, int(e.rating),
                                                             e.primary_category, e.sub_issue, problem)
                        if source == "gemini":
                            st.session_state["gemini_drafts_used"] = used + 1
                        st.session_state[key] = (text, source)
                if key in st.session_state:
                    text, source = st.session_state[key]
                    st.code(text, language=None, wrap_lines=True)
                    note = {"template": "Template for this problem", "gemini": "Written by Gemini",
                            "saved": "Gemini draft (saved earlier)"}[source]
                    st.caption(f"{note} · {len(text)}/{replies.MAX_CHARS} characters · copy with the icon at the "
                               f"top right of the box, check it, then post it in Play Console.")


# ---------------------------------------------------------------------------
# Fix tracker page
# ---------------------------------------------------------------------------
def page_tracker():
    page_header("Fix tracker", "Is the fix working? Complaints per 100 reviews, before and after.")

    st.caption("Reviews take weeks to react to a fix. For each issue the team is working on, this compares complaints "
               "per 100 written reviews in the 90 days before the date with the period since. It needs 50+ reviews "
               "after the date before it gives a verdict.", help=GLOSSARY["Per 100 reviews"])
    if tracker.empty:
        st.info("Nothing is being tracked yet. On the **Overview** page, use **Track this fix** on an action card. "
                "It moves here, and the next issue takes its place in *Do this next*.")
    verdict_color = {"Improving": "green", "Getting worse": "red", "No clear change yet": "orange"}
    for t in tracker.itertuples():
        prog = analysis.fix_progress(app_all, t.category, t.since)
        with st.container(border=True):
            c_a, c_b, c_c, c_d = st.columns([3, 2, 2, 2], vertical_alignment="center")
            with c_a:
                st.markdown(f"**{category_name(t.category)}**  \n{t.status} since {pd.Timestamp(t.since):%d %b %Y}")
                if t.note:
                    st.caption(t.note)
            c_b.metric("Before (per 100 reviews)",
                       prog["per_100_before"] if prog["per_100_before"] is not None else "–")
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


# ---------------------------------------------------------------------------
# Benchmark page
# ---------------------------------------------------------------------------
def page_benchmark():
    st.markdown("## Benchmark")

    if bench.empty:
        st.info("No benchmark yet. Run `python -m scripts.benchmark` (about 2 minutes, no Gemini).")
    else:
        as_of = pd.to_datetime(bench["fetched_at"]).max()
        st.caption(f"Public Play Store data for {len(bench)} apps · measured {as_of:%d %b %Y}. "
                   f"Every app, MoveInSync included, is measured the same way: its store listing plus its newest "
                   f"{config.BENCHMARK_SAMPLE} written reviews.")
        with st.container(border=True):
            st.markdown("**In short**")
            for line in benchmark.headline(bench):
                st.markdown(f"- {line}")

        st.markdown("**Store rating vs written-review rating**")
        order = bench.sort_values("store_score")
        fig = go.Figure()
        for _, r in order.iterrows():
            fig.add_trace(go.Scatter(x=[r["written_avg"], r["store_score"]], y=[r["name"]] * 2, mode="lines",
                                     line=dict(color="rgba(128,128,128,0.45)", width=3), hoverinfo="skip",
                                     showlegend=False))
        fig.add_trace(go.Scatter(x=order["store_score"], y=order["name"], mode="markers", name="Store rating",
                                 marker=dict(size=12, color="#4C9BE8"),
                                 hovertemplate="%{y}: store %{x:.2f}★<extra></extra>"))
        fig.add_trace(go.Scatter(x=order["written_avg"], y=order["name"], mode="markers",
                                 name=f"Newest {config.BENCHMARK_SAMPLE} written reviews",
                                 marker=dict(size=12, color="#E5735C"),
                                 hovertemplate="%{y}: written reviews %{x:.2f}★<extra></extra>"))
        fig.update_layout(height=40 * len(order) + 80, margin=dict(l=0, r=0, t=10, b=0),
                          xaxis=dict(range=[1, 5], title="Stars"), yaxis=dict(title=None),
                          legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0))
        st.plotly_chart(fig, width="stretch")
        st.caption("Each line joins an app's store rating (blue) and the average of its newest written reviews (orange). "
                   "For almost every app the written reviews are lower; the length of the line is the gap.")

        st.markdown("**Details**")
        st.dataframe(
            bench.sort_values(["group", "store_score"], ascending=[True, False])[
                ["name", "group", "store_score", "store_ratings", "written_avg", "pct_1_star", "reply_rate_unhappy",
                 "pct_ratings_with_text", "ratings_per_100_installs", "top_complaints"]],
            hide_index=True, width="stretch",
            column_config={
                "name": "App", "group": "Type",
                "store_score": st.column_config.NumberColumn("Store rating", format="%.2f",
                                                             help=GLOSSARY["Store rating"]),
                "store_ratings": st.column_config.NumberColumn("Ratings", format="%d"),
                "written_avg": st.column_config.NumberColumn("Written-review rating", format="%.2f",
                                                             help=f"Average stars of the newest "
                                                                  f"{config.BENCHMARK_SAMPLE} reviews with text."),
                "pct_1_star": st.column_config.NumberColumn("1★ share", format="%.0f%%"),
                "reply_rate_unhappy": st.column_config.NumberColumn(
                    "Replies to 1–2★", format="%.0f%%", help="Share of recent 1–2★ reviews the company replied to."),
                "pct_ratings_with_text": st.column_config.NumberColumn(
                    "Ratings with text", format="%.0f%%",
                    help="Of everyone who rated, how many also wrote a review. Written reviewers tend to be more "
                         "critical than people who only tap a star."),
                "ratings_per_100_installs": st.column_config.NumberColumn(
                    "Ratings per 100 installs", format="%.1f",
                    help="How many ratings an app collects per 100 installs (installs are a lower bound shown by "
                         "Google). Higher means more users are rating."),
                "top_complaints": st.column_config.TextColumn("Most common complaints", width="large"),
            })
        st.caption("Limits: other apps get far more reviews, so their newest 500 can cover just a few days while "
                   "MoveInSync's cover months. Complaint themes use keyword rules built for MoveInSync, so they're "
                   "rough for other apps (ride-hailing complaints about bookings and fares all land in "
                   "\"Booking\"). Public numbers only; no claims about why other apps score as they do.")

    st.markdown("**MoveInSync's own apps side by side**")
    comp = analysis.compare_apps(data, snaps, analysis.period_start(data, days))
    st.dataframe(
        comp, hide_index=True, width="stretch",
        column_config={
            "app": "App", "reviews": "Written reviews",
            "avg_rating": st.column_config.NumberColumn("Written-review rating", format="%.2f"),
            "pct_1_star": st.column_config.NumberColumn("1★ share", format="%.1f%%"),
            "reply_rate_unhappy": st.column_config.NumberColumn("Replied to 1–2★", format="%.1f%%"),
            "store_score": st.column_config.NumberColumn("Store rating", format="%.2f"),
            "store_ratings": st.column_config.NumberColumn("Store ratings", format="%d"),
        })
    st.caption(f"Period: {period_choice.lower()}.")


# ---------------------------------------------------------------------------
# How it works page
# ---------------------------------------------------------------------------
def page_how():
    st.markdown("## How it works")

    cov = analysis.uncategorised(df)
    st.markdown(f"""
#### Where the data comes from
Public Google Play reviews, collected with the unofficial `google-play-scraper` library (not an official Google
API). Reviewer names are never stored. The store rating and star counts come from the listing page and include
people who rated without writing anything.

#### How reviews are sorted into issues
Each complaint (1–3★) is matched against keyword rules (English and Hinglish) that anyone can read and edit.
Reviews the rules can't place are sorted by Google Gemini into the same fixed list, each with a one-line reason;
new keywords suggested by Gemini are only added after a person approves them.

In this view: **{cov['by_rules']}** complaints sorted by rules, **{cov['by_llm']}** by Gemini,
**{cov['pct_unclassified'] if cov['pct_unclassified'] is not None else 0}%** still unsorted, and
**{cov['low_info']}** too short to sort ("bad", "worst app").
Checked on 100 reviews that weren't used to build the rules: rules alone picked the right main issue 63% of the
time; rules + Gemini 75% (90% if a second issue counts).

#### How issues are ranked
**Rating impact** = for each issue, add up (4 − stars) over its 1–2★ reviews, then divide by all written reviews in
the period. In words: how much the written-review average would rise if those unhappy reviewers had given 4★.
It is for ranking, not a forecast.

#### How suggested replies work
For an unanswered 1–2★ review, **Suggest a reply** builds a reply from a ready-made line for that review's specific
problem (no AI, no cost). **Write with Gemini** (only where enabled) drafts a reply to that exact review, under strict
rules: under Google Play's 350-character limit, no blaming the user, no promises of refunds or fix dates, no invented
facts. Drafts that break a rule are replaced by the template. Each review costs at most one call, ever. A person
checks every reply and posts it in Play Console; nothing is posted from here.

#### How the status (OK / WATCH / ALERT) is decided
Checked on each app's newest reviews, whatever period is selected:
- **ALERT** if the 1★ share in the last 30 days is at least {analysis.STATUS_RULES['alert_1star_jump']} points higher
  than in the 90 days before (needs {analysis.STATUS_RULES['min_recent_reviews']}+ recent reviews).
- **WATCH** if any of these:
  - that 1★ share is up {analysis.STATUS_RULES['watch_1star_jump']}+ points;
  - an issue's share of complaints rose {analysis.STATUS_RULES['watch_issue_rise']}+ points in the last 90 days;
  - fewer than {analysis.STATUS_RULES['watch_reply_rate']}% of recent 1–2★ reviews got a reply;
  - the newest app version has {analysis.STATUS_RULES['watch_release_jump']}+ points more 1★ reviews than the one
    before.
- **OK** otherwise.

#### Plausible ranges
With few reviews, numbers jump around by chance. Charts show a shaded band or whiskers for where the true value most
likely is (95%). When two ranges overlap, treat the difference as "maybe", not "proven".

#### What this can't tell you
- Reviews describe experiences, not proven root causes. Use them to decide where to look first, then confirm in
  MoveInSync's own data (crash logs, OTP delivery reports, booking funnel, GPS logs).
- People who write reviews are more critical than the silent majority.
- Google only shows the latest version of an edited review.
- Shift words ("login cab", "logout cab") can confuse keyword matching.
""")
    st.markdown("#### Glossary")
    st.dataframe(pd.DataFrame(GLOSSARY.items(), columns=["Term", "Meaning"]), hide_index=True, width="stretch",
                 column_config={"Term": st.column_config.TextColumn(width="small"),
                                "Meaning": st.column_config.TextColumn(width="large")})


# ---------------------------------------------------------------------------
# Navigation (sidebar links, with counts where they help)
# ---------------------------------------------------------------------------
PAGES = {
    "overview": st.Page(page_overview, title="Overview", icon=":material/space_dashboard:", default=True),
    "issues": st.Page(page_issues, title="Issues", icon=":material/manage_search:", url_path="issues"),
    "replies": st.Page(page_replies, title="Replies", icon=":material/forum:", url_path="replies"),
    "tracker": st.Page(page_tracker, title="Fix tracker", icon=":material/build:", url_path="fix-tracker"),
    "benchmark": st.Page(page_benchmark, title="Benchmark", icon=":material/leaderboard:", url_path="benchmark"),
    "how": st.Page(page_how, title="How it works", icon=":material/menu_book:", url_path="how-it-works"),
}
current = st.navigation(list(PAGES.values()), position="hidden")
to_answer = len(replies.unanswered(df))
labels = {"replies": f"Replies · {to_answer} to answer" if to_answer else "Replies",
          "tracker": f"Fix tracker · {len(tracker)}" if len(tracker) else "Fix tracker"}
with nav_box:
    for key, page in PAGES.items():
        st.page_link(page, label=labels.get(key, page.title), icon=page.icon)
current.run()
