"""Capture dashboard screenshots for the report (docs/report/img/).

    streamlit run app.py          # in another terminal
    python -m scripts.screenshots

Uses the Edge browser already installed on Windows (Playwright channel "msedge"), light theme,
2x resolution. Each image is cropped between two pieces of text on the page.
"""

from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

URL = "http://localhost:8501"
OUT = Path(__file__).resolve().parent.parent / "docs" / "report" / "img"
SCALE = 2


def crop(page, name, top_text, bottom_text, top_pad=24, bottom_pad=24, bottom_edge="bottom", nth_top=0):
    """Full-page screenshot, cropped from the top of `top_text` to the bottom (or top) of `bottom_text`."""
    raw = OUT / f"_{name}_raw.png"
    page.screenshot(path=str(raw), full_page=True)
    t = page.get_by_text(top_text, exact=False).filter(visible=True).nth(nth_top).bounding_box()
    b = page.get_by_text(bottom_text, exact=False).filter(visible=True).first.bounding_box()
    y0 = max(0, t["y"] - top_pad)
    y1 = (b["y"] + b["height"] if bottom_edge == "bottom" else b["y"]) + bottom_pad
    img = Image.open(raw)
    w = img.width
    img.crop((int(24 * SCALE), int(y0 * SCALE), int(w - 24 * SCALE), int(y1 * SCALE))).save(OUT / f"{name}.png")
    raw.unlink()
    print("saved", name, int(y1 - y0), "px tall")


def open_tab(page, label):
    page.get_by_role("tab", name=label).click()
    page.wait_for_timeout(2500)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 4200}, device_scale_factor=SCALE,
                                  color_scheme="light")
        page = ctx.new_page()
        page.goto(URL)
        page.get_by_text("In short").first.wait_for(timeout=90000)
        page.wait_for_timeout(4000)

        # Summary tab
        crop(page, "01_header_status", "MoveInSync review analyzer", "In short", bottom_edge="top", bottom_pad=-10)
        crop(page, "02_summary_kpis", "In short", "Reviews analysed", bottom_pad=70)
        page.get_by_text("12 months", exact=True).filter(visible=True).first.click()      # a longer trend reads better
        page.wait_for_timeout(3500)
        crop(page, "03_trend", "Average rating by month", "Shaded band")
        page.get_by_text("90 days", exact=True).filter(visible=True).first.click()
        page.wait_for_timeout(3500)
        crop(page, "04_fix_first", "Fix these first", "safety-related complaints", bottom_edge="top", bottom_pad=-8)
        page.get_by_text("Did a release make things worse?").first.click()
        page.wait_for_timeout(2500)
        crop(page, "05_releases", "Did a release make things worse?", "Whiskers show the plausible range")

        # Issues tab
        open_tab(page, "Issues")
        crop(page, "06_issues_table", "Fixable by", "Look closer at", bottom_pad=60)
        crop(page, "07_action_cards", "what exactly, and what to do", "Read the reviews", bottom_edge="top", bottom_pad=-6)
        crop(page, "08_reviews", "Read the reviews", "Showing", bottom_pad=420)

        # Reply tab
        open_tab(page, "Reply to reviews")
        page.get_by_role("button", name="Suggest a reply").first.click()
        page.wait_for_timeout(2500)
        crop(page, "09_replies", "unhappy (1–2★) reviews in this period have no reply", "characters", bottom_pad=30)

        # Benchmark tab
        open_tab(page, "Benchmark")
        crop(page, "10_benchmark_chart", "Public Play Store data", "the length of the line is the gap")
        crop(page, "11_benchmark_table", "Details", "Limits:", top_pad=10)

        # How it works
        open_tab(page, "How it works")
        crop(page, "12_how_it_works", "Where the data comes from", "How issues are ranked", bottom_edge="top", bottom_pad=-6)
        browser.close()


if __name__ == "__main__":
    main()
