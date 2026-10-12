"""Build the case-study report: deliverables/MoveInSync_Ratings_Report.docx (+ PDF via Word).

    python -m scripts.screenshots     # dashboard images first (dashboard must be running)
    python -m scripts.build_report
"""

from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parent.parent
IMG = ROOT / "docs" / "report" / "img"
OUT = ROOT / "deliverables" / "MoveInSync_Ratings_Report.docx"

NAVY = RGBColor(0x14, 0x21, 0x3D)
BLUE = RGBColor(0x25, 0x63, 0xEB)
GREY = RGBColor(0x55, 0x60, 0x70)
LIVE = "https://moveinsync-review-analyzer.streamlit.app"
REPO = "https://github.com/Heman1223/moveinsync-review-analyzer"

doc = Document()
sec = doc.sections[0]
sec.page_height, sec.page_width = Cm(29.7), Cm(21.0)
sec.left_margin = sec.right_margin = Cm(2.2)
sec.top_margin, sec.bottom_margin = Cm(2.0), Cm(2.0)
CONTENT_W = 21.0 - 4.4

st = doc.styles["Normal"]
st.font.name, st.font.size = "Calibri", Pt(11)
st.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
st.paragraph_format.space_after = Pt(6)
st.paragraph_format.line_spacing = 1.15
for name, size, color in [("Heading 1", 18, NAVY), ("Heading 2", 13.5, BLUE)]:
    h = doc.styles[name]
    h.font.name, h.font.size, h.font.bold, h.font.color.rgb = "Calibri", Pt(size), True, color
    h.element.rPr.rFonts.set(qn("w:asciiTheme"), "")
    h.paragraph_format.space_before = Pt(14 if name == "Heading 1" else 10)
    h.paragraph_format.space_after = Pt(6)
    h.paragraph_format.keep_with_next = True


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def para(text="", bold=False, size=None, color=None, italic=False, align=None, after=None):
    p = doc.add_paragraph()
    if text:
        add_runs(p, text, bold=bold, size=size, color=color, italic=italic)
    if align:
        p.alignment = align
    if after is not None:
        p.paragraph_format.space_after = Pt(after)
    return p


def add_runs(p, text, bold=False, size=None, color=None, italic=False):
    """**double stars** mark bold spans inside a line."""
    parts = text.split("**")
    for i, part in enumerate(parts):
        if not part:
            continue
        r = p.add_run(part)
        r.bold = bold or (i % 2 == 1)
        r.italic = italic
        if size:
            r.font.size = Pt(size)
        if color:
            r.font.color.rgb = color
    return p


def bullet(text, level=0):
    p = doc.add_paragraph(style="List Bullet" if level == 0 else "List Bullet 2")
    add_runs(p, text)
    p.paragraph_format.space_after = Pt(3)
    return p


def numbered(text):
    p = doc.add_paragraph(style="List Number")
    add_runs(p, text)
    p.paragraph_format.space_after = Pt(3)
    return p


def shade(cell, hex_fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    tcPr.append(shd)


def table(rows, widths, header=True, size=9.5, highlight_row=None):
    t = doc.add_table(rows=len(rows), cols=len(rows[0]))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            c = t.cell(i, j)
            c.width = Cm(widths[j])
            c.text = ""
            p = c.paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            add_runs(p, str(val), bold=(header and i == 0), size=size,
                     color=RGBColor(0xFF, 0xFF, 0xFF) if header and i == 0 else None)
            if i < len(rows) - 1:
                p.paragraph_format.keep_with_next = True
            if header and i == 0:
                shade(c, "14213D")
            elif highlight_row is not None and i == highlight_row:
                shade(c, "EAF1FF")
    for row in t.rows:
        trPr = row._tr.get_or_add_trPr()
        cant = OxmlElement("w:cantSplit")
        trPr.append(cant)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


def image(name, caption, width=CONTENT_W):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run()
    run.add_picture(str(IMG / f"{name}.png"), width=Cm(width))
    c = para(caption, italic=True, size=9, color=GREY, align=WD_ALIGN_PARAGRAPH.CENTER, after=10)
    return c


def callout(text, fill="EAF1FF"):
    t = doc.add_table(rows=1, cols=1)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    c = t.cell(0, 0)
    c.width = Cm(CONTENT_W)
    shade(c, fill)
    c.text = ""
    p = c.paragraphs[0]
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(4)
    add_runs(p, text, size=10.5)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def page_break():
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


def footer():
    p = sec.footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("MoveInSync Play Store ratings · Heman Sharma · page ")
    r.font.size, r.font.color.rgb = Pt(8.5), GREY
    for code in ("begin", None, "end"):
        if code is None:
            instr = OxmlElement("w:instrText")
            instr.set(qn("xml:space"), "preserve")
            instr.text = "PAGE"
            run = p.add_run()
            run._r.append(instr)
        else:
            fld = OxmlElement("w:fldChar")
            fld.set(qn("w:fldCharType"), code)
            run = p.add_run()
            run._r.append(fld)
        run.font.size = Pt(8.5)


footer()

# ---------------------------------------------------------------------------
# Cover
# ---------------------------------------------------------------------------
for _ in range(5):
    para()
para("MOVEINSYNC · FORWARD DEPLOYED ENGINEER CASE STUDY", bold=True, size=10, color=BLUE)
para("Raising MoveInSync's Play Store rating", bold=True, size=30, color=NAVY, after=4)
para("Why the rating is where it is, what to fix, and what to do first", size=16, color=GREY, after=30)
para("A review of 24,000+ public Google Play reviews, a benchmark against 10 comparable apps, "
     "and a dashboard that answers \"How are our Play Store ratings?\" every week.", size=12, after=40)
para("**Heman Sharma**", size=12, after=2)
para("12 October 2026", size=11, color=GREY, after=24)
para(f"Live dashboard: {LIVE}", size=10.5, color=BLUE, after=2)
para(f"Code, data and memo: {REPO}", size=10.5, color=BLUE)
page_break()

# ---------------------------------------------------------------------------
# Executive summary
# ---------------------------------------------------------------------------
doc.add_heading("Executive summary", 1)
para("**The question.** MoveInSync's Play Store ratings are \"lower than they should be\". Why, what should be fixed, "
     "and what should happen first?")
para("**The answer in three lines.**", after=2)
numbered("**MoveInSync already leads its category.** At 4.64★ it is the best-rated of 7 employee-transport apps "
         "(the others average 3.05★). Uber, at 4.73★, is only 0.09★ higher.")
numbered("**The clearest gap is silence, not the product.** MoveInSync answered about 97% of 1–2★ reviews in 2023 and "
         "1% in 2026. Its direct competitor, Routematic, answers 100%. Fixing this needs no code.")
numbered("**The product work that matters most now:** app stability (23% of complaints in the last 90 days, up from "
         "14%), led by a false \"not installed from Play Store\" block, then booking and OTP delivery.")
para("**What to do first.**", after=2)
table([
    ["When", "Action", "Owner", "Target"],
    ["Week 1–2", "Reply to every 1–2★ review within 48 h; show the transport policy only when it changes; make "
                 "trip rating skippable; ask for ratings after a good trip, not every ride", "Support, app team",
     "Replies 4% → 80%"],
    ["30 days", "Fix the false Play Store/rooted-phone block; find where OTPs get lost; stop forced logouts",
     "App team, SMS provider", "Stability complaints back to ~14%"],
    ["60–90 days", "Measure and fix the booking flow; staged releases; show GPS freshness on the cab",
     "Product, app team", "1★ share 25% → ≤20%"],
], widths=[2.3, 8.7, 2.8, 2.8])
callout("**How it stays on track:** a dashboard refreshes the data every Monday, flags what changed (OK / WATCH / "
        "ALERT), and compares complaints before and after each fix ships. Today's status is **WATCH**: stability "
        "complaints are rising, unhappy reviewers aren't getting replies, and the newest release may be worse.")
page_break()

# ---------------------------------------------------------------------------
# 1 Problem and approach
# ---------------------------------------------------------------------------
doc.add_heading("1. The problem and my approach", 1)
para("MoveInSync's employee app is how 1.5 million people book and track their office commute every working day. "
     "Employees rate it openly on Google Play, and the company wants the rating higher. The brief asked for "
     "recommendations specific enough for a product or engineering team to start the next day, and noted that "
     "\"How are our Play Store ratings?\" will be asked again and again.")
para("I treated it as two jobs: **answer the question now**, and **build something that keeps answering it**.")
doc.add_heading("Approach", 2)
numbered("**Collect everything public:** every written review of the employee app since 2014, its store rating "
         "snapshot, and the same data for 10 comparable apps.")
numbered("**Read before modelling:** look at trends by quarter and app version, then read 100 recent complaints "
         "to find the real themes before writing any rules.")
numbered("**Sort complaints transparently:** readable English and Hinglish keyword rules first, Gemini only for "
         "what the rules miss, and accuracy measured on reviews held back for checking.")
numbered("**Rank by impact, then make it actionable:** split each issue into specific problems, each with an "
         "owner, effort, a metric, and what to check in MoveInSync's own data before building.")
numbered("**Make it repeatable:** a dashboard, a weekly automatic update, and a fix tracker.")
doc.add_heading("Scope", 2)
table([
    ["App", "Who uses it", "Included?", "Why"],
    ["MoveInSync (com.moveinsync.ets)", "Employees", "Yes: main focus", "24,317 written reviews; the app the brief describes"],
    ["Moveinsync Partner – Lite", "Drivers", "Yes: secondary", "Driver app problems can show up as late cabs; only 111 reviews"],
    ["Driver Partner, Field app, Workplace", "Prospective drivers, admins, kiosks", "No",
     "Not part of the commute; too few reviews to analyse"],
], widths=[4.6, 3.4, 2.6, 6.0])
para("**Data was collected on 11 October 2026**; the newest review is from 9 October 2026.", size=10, color=GREY)

# ---------------------------------------------------------------------------
# 2 Data and method
# ---------------------------------------------------------------------------
doc.add_heading("2. Data and method", 1)
doc.add_heading("Data", 2)
table([
    ["Source", "What", "How much"],
    ["Google Play reviews (employee app)", "Text, stars, date, app version, likes, developer reply", "24,317 reviews, 2014–2026"],
    ["Google Play listing", "Store rating and star counts (includes star-only ratings)", "4.64★ from 114,869 ratings"],
    ["10 comparable apps", "Listing + newest 500 written reviews each", "Routematic, eFmFm, SMT, Shuttl, Uber, Rapido, Ola and others"],
], widths=[4.6, 6.6, 5.4])
para("Reviews were collected with google-play-scraper, an open-source Python library that reads the public Play Store "
     "pages (not an official Google API). Reviewer names and photos were never stored.", size=10)
doc.add_heading("Sorting complaints into issues", 2)
para("Complaints (1–3★ reviews) were sorted into 13 issue categories, such as Login and OTP, App stability, Booking, "
     "Tracking, Cab late, Routing, Safety. The categories came from reading real reviews, not from a template.")
bullet("**Keyword rules first.** Readable, editable rules in English and Hinglish (\"cab nahi aayi\", \"otp nahi\"), "
       "matched as whole words. Every label can be traced to the keyword that triggered it.")
bullet("**Gemini for the long tail.** Reviews the rules missed, often Hinglish or vague, went to Google Gemini, "
       "which had to choose from the same 13 categories and give a one-line reason. Each review is sent once and "
       "the result saved. Gemini also suggested new keywords; only the 12 that held up on the data were added.")
bullet("**Measured, not assumed.** On 100 reviews held back from building anything:")
table([
    ["Method", "Main issue correct", "Correct counting a 2nd issue", "Left unsorted"],
    ["Keyword rules only", "63%", "77%", "19%"],
    ["Rules + Gemini", "**75%**", "**90%**", "**4%**"],
], widths=[5.0, 3.8, 4.4, 3.4], highlight_row=2)
doc.add_heading("Ranking by impact, not by count", 2)
para("For each issue, **rating impact** = the sum of (4 − stars) over its 1–2★ reviews, divided by all written reviews. "
     "In words: how much the written-review average would rise if those unhappy reviewers had been satisfied enough "
     "to give 4★. It is a ranking aid, not a forecast. Safety complaints are always shown separately, however few.")
page_break()

# ---------------------------------------------------------------------------
# 3 Findings
# ---------------------------------------------------------------------------
doc.add_heading("3. Why the rating is where it is", 1)
doc.add_heading("3.1 Two groups rate the app, and the critical one writes the reviews", 2)
table([
    ["", "Store rating (all ratings)", "Written reviews, last 12 months"],
    ["Average", "**4.64★**", "**3.83★**"],
    ["1★ share", "6.4%", "24.0%"],
    ["Count", "114,869 ratings", "2,857 reviews"],
], widths=[3.6, 6.5, 6.5])
para("Most people only tap a star, and those ratings are mostly 5★. The people who write a review are far more critical, "
     "and written reviews are what prospective users, and the HR teams who buy MoveInSync, actually read.")
doc.add_heading("3.2 The gap is normal, and MoveInSync is the category leader", 2)
para("Every app was measured the same way: its store listing plus its newest 500 written reviews.")
image("10_benchmark_chart", "Figure 1. Benchmark tab: store rating (blue) vs newest written reviews (orange) for 11 apps.",
      width=13.5)
table([
    ["App", "Store ★", "Written ★ (newest 500)", "Replies to 1–2★"],
    ["**MoveInSync**", "**4.64**", "**3.78**", "**1%**"],
    ["Routematic (direct competitor)", "4.34", "3.56", "100%"],
    ["Uber", "4.73", "3.73", "0%"],
    ["Rapido", "4.72", "3.77", "23%"],
    ["Ola", "4.62", "2.75", "4%"],
    ["Other 5 employee-transport apps (average)", "2.6", "–", "–"],
], widths=[6.6, 2.6, 4.2, 3.2], highlight_row=1)
para("For 10 of the 11 apps, written reviews sit about 1★ below the store rating. MoveInSync's written reviews are "
     "level with Uber and Rapido and ahead of Routematic. **The product is not failing; the visible reviews are where "
     "to act.**")
doc.add_heading("3.3 The biggest gap: replies stopped in 2024", 2)
table([
    ["Year", "2022", "2023", "2024", "2025", "2026"],
    ["Share of 1–2★ reviews with a developer reply", "76%", "97%", "38%", "7%", "**1%**"],
], widths=[6.6, 2.0, 2.0, 2.0, 2.0, 2.0])
para("In the last 12 months, **743 of 772** unhappy reviews got no answer, while Routematic answers all of its own. "
     "Replies seem to work: of the reviewers who edited after getting a reply, **13 of 22 now show 4–5★**. Google only "
     "shows the latest version of a review, so this suggests replies help rather than proving it.")
doc.add_heading("3.4 What people complain about", 2)
para("About two-thirds of complaints are about the app itself rather than cabs or drivers, so they are within "
     "MoveInSync's control. The ranking has shifted in the last 90 days:")
table([
    ["Issue", "Last 90 days", "Last 12 months", "Biggest specific problem (last 90 days)"],
    ["App stability", "**23%, rising**", "17%", "False \"not installed from Play Store\" / rooted-phone block (26%)"],
    ["Booking and schedule", "16%", "14%", "Booking fails or the steps are confusing (66%)"],
    ["Login, OTP and session", "10%, falling", "17%", "OTP not received or slow (47%); forced logouts (26%)"],
    ["Tracking, ETA and map", "9%", "10%", "Cab location wrong or not updating (56%)"],
    ["Repeated prompts", "7%", "5%", "Forced trip rating; transport policy shown every time"],
], widths=[3.8, 2.6, 2.6, 7.6])
image("06_issues_table", "Figure 2. Issues tab: every issue ranked by rating impact, with its owner type and trend.")
doc.add_heading("3.5 Releases matter", 2)
para("Versions 12.10–12.12 (Feb–May 2026) averaged **4.05★** with 20% 1★, which shows the targets below are reachable "
     "with today's product. The latest, v12.19, has 32% 1★ against 23% for v12.18. Its range overlaps, with only 102 "
     "reviews so far, so it could still be chance, but it is worth watching.")
image("05_releases", "Figure 3. 1★ share by app version, with plausible ranges. Grey bars have under 30 reviews.")
doc.add_heading("3.6 The driver app (Partner Lite): small, but connected", 2)
table([
    ["", "Store", "Written reviews, last 12 months"],
    ["Rating", "4.25★ (702 ratings)", "3.26★ (23 reviews, 39% 1★)"],
    ["Unhappy reviews answered", "–", "0 of 9"],
], widths=[5.0, 5.0, 6.6])
para("Too few reviews to rank issues reliably, so it gets no separate plan. Two things are still worth acting on:")
bullet("**Most specific complaints are about stability:** not opening on some phones, getting stuck, wrong kilometre "
       "counts. Drivers' GPS feeds the employee app's tracking screen, so driver-app reliability is a likely contributor "
       "to \"cab location wrong\" complaints in the employee app (action 9 checks this).")
bullet("**Employees install the wrong app.** One reviewer explains to others: \"this is the driver app not the passenger "
       "app\". A clearer store name and first line of the description would prevent 1★ reviews from confused employees.")

# ---------------------------------------------------------------------------
# 4 Recommendations
# ---------------------------------------------------------------------------
page_break()
doc.add_heading("4. What to do, in order", 1)
para("Cheapest first: answer the unhappy, remove self-inflicted friction, then fix the specific app problems. Every "
     "action names what to check in MoveInSync's own data before building, because reviews describe experiences, "
     "not proven causes.")
doc.add_heading("Week 1–2: little or no code", 2)
table([
    ["Action", "Owner", "Effort", "Target"],
    ["Reply to every 1–2★ review within 48 hours, using the dashboard's reply assistant", "Support team", "Low",
     "Reply rate 4% → 80%"],
    ["Show the transport policy only when it changes; make the trip rating skippable", "App team", "1/5",
     "Prompt complaints halved"],
    ["Ask for a Play Store rating after an on-time trip, not after every ride. Never ask \"do you like the app?\" "
     "first: Google forbids filtering who gets the prompt", "Product", "1/5", "Fewer rating pop-up complaints"],
], widths=[9.2, 2.8, 1.6, 3.0])
doc.add_heading("Next 30 days: the biggest app problems", 2)
table([
    ["Action", "Owner", "Effort", "Check first in MoveInSync's data", "Target"],
    ["Fix the false \"not installed from Play Store\" / rooted-phone block; reword its message",
     "App team (security)", "2/5", "Integrity-check logs: which phones and versions it blocks", "False blocks ≈ 0"],
    ["Find where OTPs get lost; add a backup channel and SMS auto-read", "App team + SMS provider", "3/5",
     "OTP send/deliver/verify logs by operator", "Delivery ≥ 98%"],
    ["Keep people signed in through brief network drops and updates", "App + backend team", "3/5",
     "Session-expiry logs by app version", "Forced-logout complaints halved"],
], widths=[5.4, 2.8, 1.4, 4.4, 2.6], size=9)
doc.add_heading("60–90 days", 2)
table([
    ["Action", "Owner", "Effort", "Target"],
    ["Measure each booking step (open → choose → confirm → booked) and fix where people give up; compare with the "
     "older one-step flow", "Product + app team", "3/5", "Booking completion up"],
    ["Release in stages (5% → 20% → 100%) and pause if crashes or 1★ reviews rise", "App team + release", "2/5",
     "No release worse than the last"],
    ["Show \"updated x min ago\" on the cab location; check the driver app's GPS upload frequency",
     "Tracking + driver app team", "3/5", "Fewer location complaints"],
], widths=[9.2, 3.0, 1.4, 3.0])
callout("**90-day targets:** reply rate ≥ 80% · written-review 1★ share 25% → ≤ 20% · written-review average "
        "3.80★ → ≥ 4.0★ (v12.10–12.12 already reached 4.05★) · store rating held at 4.64★ or better.")

# ---------------------------------------------------------------------------
# 5 Dashboard
# ---------------------------------------------------------------------------
page_break()
doc.add_heading("5. The dashboard", 1)
para(f"Live at {LIVE}. It reads saved data, so it opens in seconds and costs nothing to view. Six tabs: Summary, "
     "Issues, Reply to reviews, Fix tracker, Benchmark, How it works.")
image("01_header_status", "Figure 4. The weekly status, with the reasons in plain words, sits at the top of the Summary tab.")
image("02_summary_kpis", "Figure 5. \"In short\": the answer in a few sentences, generated from the data, then the headline numbers.")
image("04_fix_first", "Figure 6. Fix these first: the top issues by rating impact, each with where to start, owner and "
      "effort, plus the reply quick win. \"Mark as being fixed\" moves an issue to the tracker and the next one moves up.")
image("07_action_cards", "Figure 7. Issues tab: one issue broken into specific problems, each with an action card "
      "(what to do, who, effort, what to check first, how you'll know it worked).")
image("09_replies", "Figure 8. Reply to reviews: a suggested reply for each unanswered review, written for its specific "
      "problem, within Google Play's 350-character limit. A person checks and posts it; nothing is posted automatically.")
image("03_trend", "Figure 9. Average rating by month over 12 months, with a plausible-range band and release markers.", width=15)

# ---------------------------------------------------------------------------
# 6 Keeping it on track
# ---------------------------------------------------------------------------
page_break()
doc.add_heading("6. Keeping it on track", 1)
para("The brief said this question will keep coming back, so the answer is a system rather than a one-off report.")
bullet("**Every Monday, automatically** (GitHub Actions): run the tests, fetch new reviews, re-measure the 10 "
       "comparison apps, write a one-page digest, and update the live dashboard.")
bullet("**A weekly status** from four published rules. ALERT if the 1★ share jumps 8+ points in 30 days. WATCH if it "
       "rises 4+ points, an issue's share rises 5+ points, under 20% of unhappy reviews get a reply, or the newest "
       "release is 5+ points worse. When the data can't tell a real change from chance, it says so.")
bullet("**A fix tracker.** When a fix ships, it compares complaints about that issue per 100 reviews before and after, "
       "and says \"improving\", \"no clear change\", \"getting worse\" or \"too early\". Reviews lag behind fixes, so "
       "the next issue moves up in the meantime.")
bullet("**Cost control.** The public dashboard never calls the AI. Locally, each review is sent to Gemini at most once, "
       "with a cap of 10 requests per run.")

# ---------------------------------------------------------------------------
# 7 Assumptions and limits
# ---------------------------------------------------------------------------
doc.add_heading("7. Assumptions and limits", 1)
bullet("Reviews describe experiences, not proven causes. Every action lists what to check internally before building.")
bullet("Only written reviews can be read; star-only ratings are visible as totals.")
bullet("The data comes from public pages via an unofficial library; Google can change those pages.")
bullet("Issue sorting is about 75% accurate (90% counting a second issue). The ranking is robust to that; individual "
       "labels are not perfect. Shift words such as \"login cab\" and \"logout cab\" can confuse the keyword rules.")
bullet("Google shows only the latest version of an edited review, so the effect of replies is suggested, not proven.")
bullet("Effort scores and targets are judgement calls. Benchmark samples cover different time spans (500 reviews can "
       "be days for Uber and months for MoveInSync).")
bullet("12 complaints in the last year mention safety (for example, a driver misbehaving with a woman employee). They "
       "are listed in the dashboard for a person to read, not ranked by volume.")

# ---------------------------------------------------------------------------
# Appendix
# ---------------------------------------------------------------------------
page_break()
doc.add_heading("Appendix: tools, links, and what changed my mind", 1)
doc.add_heading("What changed my mind", 2)
bullet("**\"Ratings dropped recently.\"** My first look at the newest 1,000 reviews suggested a decline. The full "
       "history showed written reviews have sat at 3.5–3.9★ for years; the real change was replies stopping in 2024.")
bullet("**\"Not enough users are asked to rate.\"** The benchmark showed MoveInSync already collects the most ratings "
       "per install of all 11 apps (11.5 per 100, against 2–5), so I dropped that idea.")
doc.add_heading("Tools", 2)
table([
    ["Tool", "Used for"],
    ["Python: pandas, Streamlit, Plotly, pytest", "Analysis, dashboard, charts, 68 automated tests"],
    ["google-play-scraper", "Collecting public reviews and store data"],
    ["Google Gemini", "Sorting reviews the rules missed; keyword suggestions; optional reply drafts"],
    ["GitHub Actions", "The weekly automatic update"],
    ["Streamlit Community Cloud", "Hosting the live dashboard"],
    ["Claude Code (AI assistant)", "Help with writing and testing code, labelling review samples, and drafting; "
                                   "I set the direction and made the scope and design decisions"],
], widths=[6.0, 10.6])
doc.add_heading("Links", 2)
bullet(f"Live dashboard: {LIVE}")
bullet(f"Code, data, memo and method note: {REPO}")

OUT.parent.mkdir(parents=True, exist_ok=True)
doc.save(OUT)
print("saved", OUT)
