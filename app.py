"""MoveInSync review analyzer: Streamlit dashboard.

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

st.set_page_config(page_title="MoveInSync review analyzer", page_icon="⭐", layout="wide")
PUBLIC = pipeline.public_demo()   # read-only public link: no refresh, no fix tracking, no Gemini

PERIODS = {"30 days": 30, "90 days": 90, "6 months": 182, "12 months": 365, "All time": None}
LOW_DATA = 30
REPLY_TARGET = 80
FIXABLE_LABEL = {"App": "App fix", "Ops": "Ops fix", "Review": "Human review"}
FIXABLE_COLOR = {"App": "blue", "Ops": "orange", "Review": "red"}
STATUS_COLOR = {"OK": "green", "WATCH": "orange", "ALERT": "red"}
STATUS_ICON = {"OK": ":material/check_circle:", "WATCH": ":material/visibility:", "ALERT": ":material/warning:"}

# Plain-English definitions, used as tooltips and in the "How it works" tab.
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
# Header and filters
# ---------------------------------------------------------------------------
head_l, head_r = st.columns([4, 1], vertical_alignment="center")
with head_l:
    st.title("MoveInSync review analyzer")
    st.caption(f"Why are Play Store ratings where they are, and what should we fix first? "
               f"Public Google Play reviews · updated {last_updated()}")
with head_r:
    if PUBLIC:
        st.caption("Data updates automatically every Monday.")
    elif st.button("Refresh data", icon=":material/refresh:", width="stretch",
                   help="Fetch new reviews from Google Play (takes under a minute)."):
        run_refresh()

if not config.REVIEWS_CSV.exists():
    st.info("No data yet. Click **Refresh data** to fetch reviews (takes a few minutes the first time).")
    st.stop()

data = load_data(pipeline._fingerprint())
snaps = load_snapshots(_mtime(config.SNAPSHOTS_CSV))

app_options = {meta["name"]: app_id for app_id, meta in config.APPS.items()}
f1, f2 = st.columns([3, 3])
with f1:
    app_choice = st.segmented_control("App", list(app_options) + ["Compare apps"],
                                      default=next(iter(app_options)), label_visibility="collapsed")
with f2:
    period_choice = st.segmented_control("Period", list(PERIODS), default="90 days",
                                         label_visibility="collapsed")
app_choice = app_choice or next(iter(app_options))
period_choice = period_choice or "90 days"
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
            "avg_rating": st.column_config.NumberColumn("Written-review rating", format="%.2f",
                                                        help=GLOSSARY["Written-review rating"]),
            "pct_1_star": st.column_config.NumberColumn("1★ share", format="%.1f%%"),
            "reply_rate_unhappy": st.column_config.NumberColumn("Replied to 1–2★", format="%.1f%%"),
            "store_score": st.column_config.NumberColumn("Store rating", format="%.2f", help=GLOSSARY["Store rating"]),
            "store_ratings": st.column_config.NumberColumn("Store ratings", format="%d"),
        })
    st.caption("Store rating includes people who rated without writing a review. Written reviews are the ones "
               "other users read, and they are much more critical.")
    st.stop()


# ---------------------------------------------------------------------------
# Single-app data
# ---------------------------------------------------------------------------
app_id = app_options[app_choice]
app_all = analysis.filter_period(data, app_id)
df = analysis.filter_period(app_all, start=analysis.period_start(app_all, days))
snap = analysis.latest_snapshot(snaps, app_id)
k = analysis.kpis(df, snap)
rh = analysis.reply_health(df)
summary = analysis.issue_summary(df)
tracker = fix_tracker.load(app_id)
tracked = set(tracker["category"])

tab_sum, tab_issues, tab_reply, tab_fix, tab_bench, tab_how = st.tabs(
    ["Summary", "Issues", "Reply to reviews", f"Fix tracker{f' ({len(tracker)})' if len(tracker) else ''}",
     "Benchmark", "How it works"])
GEMINI_DRAFTS_PER_SESSION = 20   # protects the API budget; saved drafts don't count


def fix_form(category: str, key: str, note_default: str = ""):
    """Small form to put an issue into the fix tracker."""
    if PUBLIC:
        st.caption("Fix tracking is switched off on the public demo, so visitors can't change it. "
                   "It works when the dashboard is run by the team.")
        return
    status = st.radio("Status", fix_tracker.STATUSES, horizontal=True, key=f"{key}_status")
    since = st.date_input("Since", value=date.today(), key=f"{key}_date",
                          help="When work started or the fix was released. Before/after numbers use this date.")
    note = st.text_input("Note (optional)", value=note_default, placeholder="e.g. session timeout raised in v12.20",
                         key=f"{key}_note")
    if st.button("Save", key=f"{key}_save", type="primary"):
        fix_tracker.set_status(app_id, category, status, since, note)
        st.rerun()


# ---------------------------------------------------------------------------
# Summary tab
# ---------------------------------------------------------------------------
with tab_sum:
    status = analysis.weekly_status(app_all)
    with st.container(border=True):
        s1, s2 = st.columns([1, 5], vertical_alignment="center")
        with s1:
            st.badge(f"Status: {status['status']}", color=STATUS_COLOR[status["status"]],
                     icon=STATUS_ICON[status["status"]])
        with s2:
            for reason in status["reasons"]:
                st.markdown(f"- {reason}")
        st.caption("Checks this app's latest reviews, whatever period is selected. The rules are listed in "
                   "**How it works**.", help=GLOSSARY["Status"])

    with st.container(border=True):
        st.markdown("**In short**")
        for sentence in analysis.plain_summary(df, snap, exclude=tracked):
            st.markdown(f"- {sentence}")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Written-review rating", f"{k['avg_rating']:.2f} ★" if k["avg_rating"] else "–",
              delta=(f"{k['avg_rating'] - k['store_score']:+.2f} vs store {k['store_score']:.2f}"
                     if k["avg_rating"] and k["store_score"] else None),
              help=GLOSSARY["Written-review rating"] + " " + GLOSSARY["Store rating"])
    c2.metric("1★ share", f"{k['pct_1_star']:.0f}%" if k["pct_1_star"] is not None else "–",
              delta=(f"{k['pct_1_star'] - k['store_pct_1_star']:+.0f} pts vs store"
                     if k["store_pct_1_star"] and k["pct_1_star"] is not None else None),
              delta_color="inverse", help="Share of written reviews that give 1 star, compared with all store ratings.")
    c3.metric("1–2★ reviews replied to",
              f"{rh['reply_rate_unhappy']:.0f}%" if rh["reply_rate_unhappy"] is not None else "–",
              delta=f"target {REPLY_TARGET}%", delta_color="off",
              help=f"{rh['unhappy_replied']} of {rh['unhappy_reviews']} unhappy reviews got a reply from MoveInSync.")
    c4.metric("Reviews analysed", f"{k['reviews']:,}",
              delta=(f"{k['date_from']:%d %b %Y} – {k['date_to']:%d %b %Y}" if k["reviews"] else None),
              delta_color="off")

    trend_col, dist_col = st.columns([3, 1])
    with trend_col:
        st.markdown("**Average rating by month** · written reviews")
        trend = analysis.monthly_ranges(df)
        fig = go.Figure()
        band = trend.dropna(subset=["avg_lo", "avg_hi"])
        if len(band):
            fig.add_trace(go.Scatter(x=pd.concat([band["month"], band["month"][::-1]]),
                                     y=pd.concat([band["avg_hi"], band["avg_lo"][::-1]]),
                                     fill="toself", fillcolor="rgba(76,155,232,0.15)", line=dict(width=0),
                                     hoverinfo="skip", showlegend=False))
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
            fig.add_trace(go.Scatter(
                x=versions["first_review"], y=[1.15] * len(versions), mode="markers",
                marker=dict(symbol="triangle-up", size=9, color="gray"),
                customdata=versions[["version", "avg_rating", "pct_1_star", "reviews"]],
                hovertemplate="v%{customdata[0]} · first review %{x|%d %b %Y}<br>"
                              "%{customdata[1]:.2f} ★ · %{customdata[2]}% 1★ · %{customdata[3]} reviews<extra></extra>"))
        fig.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0), yaxis=dict(range=[1, 5], title=None),
                          xaxis=dict(title=None), showlegend=False)
        st.plotly_chart(fig, width="stretch")
        st.caption("Shaded band: plausible range for each month (wider when there are fewer reviews). "
                   "▲ and dotted lines mark app releases (versions with 30+ reviews).", help=GLOSSARY["Plausible range"])
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

    vr = analysis.version_ranges(df)
    if not vr.empty:
        with st.expander("Did a release make things worse? 1★ share by app version", icon=":material/new_releases:"):
            vr = vr[vr["reviews"] >= 10]
            colors = ["#4C9BE8" if ok else "rgba(150,150,150,0.5)" for ok in vr["enough_data"]]
            vfig = go.Figure(go.Bar(
                x=["v" + v for v in vr["version"]], y=vr["pct_1_star"], marker_color=colors,
                error_y=dict(type="data", symmetric=False, array=vr["pct_1_hi"] - vr["pct_1_star"],
                             arrayminus=vr["pct_1_star"] - vr["pct_1_lo"], color="gray", thickness=1),
                customdata=vr[["reviews", "pct_1_lo", "pct_1_hi"]],
                hovertemplate="%{x}: %{y:.0f}% 1★ (plausible %{customdata[1]:.0f}–%{customdata[2]:.0f}%)"
                              "<br>%{customdata[0]} reviews<extra></extra>"))
            vfig.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0),
                               yaxis=dict(title="% of reviews that are 1★", rangemode="tozero"))
            st.plotly_chart(vfig, width="stretch")
            st.caption("Whiskers show the plausible range. If two versions' whiskers overlap, the difference may be "
                       "chance. Grey bars have fewer than 30 reviews.", help=GLOSSARY["Plausible range"])

    st.subheader("Fix these first")
    st.caption("Ranked by rating impact (hover the ⓘ for what that means). Mark an issue as being fixed and the next "
               "one moves up; reviews take weeks to catch up with a fix, so follow progress in the Fix tracker tab.",
               help=GLOSSARY["Rating impact"])
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
                    st.caption(f"Share {arrow}: {r['share_before']:.0f}% → {r['share_last_period']:.0f}% "
                               f"(last 90 days)")
            bd = analysis.sub_issue_breakdown(df, r["category"])
            specific = bd[bd["actionable"]] if not bd.empty else bd
            note_default = ""
            if not specific.empty:
                b = specific.iloc[0]
                note_default = b["problem"]
                st.markdown(f"**Start with:** {b['problem']} ({b['share']:.0f}% of these)")
                st.caption(b["first_step"])
                st.caption(f"**Who:** {b['owner']}  \n**Effort:** {int(b['effort'])}/5 · {EFFORT[int(b['effort'])]}")
            with st.popover("Mark as being fixed", icon=":material/build:", width="stretch"):
                fix_form(r["category"], key=f"card_{r['category']}", note_default=note_default)
            st.caption("Full plan for each problem: **Issues** tab.")
    if top.empty:
        cards[0].info("Every ranked issue is in the Fix tracker.")
    if rh["reply_rate_unhappy"] is not None and rh["reply_rate_unhappy"] < REPLY_TARGET:
        with cards[3].container(border=True):
            st.badge("Quick win", color="green")
            st.markdown("**Reply to unhappy reviews**")
            st.markdown(f"{rh['unhappy_reviews'] - rh['unhappy_replied']} of {rh['unhappy_reviews']} 1–2★ reviews "
                        f"unanswered · no code needed")
            if rh["edited_after_reply"]:
                st.caption(f"Historically, {rh['edited_after_reply']} reviewers edited after a reply; "
                           f"{rh['edited_now_4_5']} now show 4–5★.")

    safety = analysis.safety_reviews(df)
    if len(safety):
        with st.expander(f":red[**{len(safety)} safety-related complaints need human review**]",
                         icon=":material/shield:"):
            st.caption("Flagged by keywords or the LLM. Always shown, however few there are. Some may be false alarms.")
            for s in safety.itertuples():
                st.markdown(f"- {s.rating}★ · {s.review_date:%d %b %Y} · {s.review_text}")


# ---------------------------------------------------------------------------
# Issues tab
# ---------------------------------------------------------------------------
with tab_issues:
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
                            with st.popover("Mark as being fixed", icon=":material/build:"):
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
# Reply to reviews tab
# ---------------------------------------------------------------------------
with tab_reply:
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
# Fix tracker tab
# ---------------------------------------------------------------------------
with tab_fix:
    st.markdown("#### Is the fix working?")
    st.caption("Reviews take weeks to react to a fix. For each issue the team is working on, this compares complaints "
               "per 100 written reviews in the 90 days before the date with the period since. It needs 50+ reviews "
               "after the date before it gives a verdict.", help=GLOSSARY["Per 100 reviews"])
    if tracker.empty:
        st.info("Nothing is being tracked yet. On the **Summary** tab, use **Mark as being fixed** on an issue card. "
                "It moves here, and the next issue takes its place in *Fix these first*.")
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
# Benchmark tab
# ---------------------------------------------------------------------------
with tab_bench:
    bench = benchmark.latest()
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


# ---------------------------------------------------------------------------
# How it works tab
# ---------------------------------------------------------------------------
with tab_how:
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
