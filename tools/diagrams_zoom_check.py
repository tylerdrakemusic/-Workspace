"""Playwright validation: diagrams dashboard click-to-zoom lightbox."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = "file:///f:/⊕Workspace/reports/diagrams_dashboard.html"
SCREENSHOT = Path(r"f:\⊕Workspace\tmp\diagrams_zoom_test.png")
SCREENSHOT.parent.mkdir(parents=True, exist_ok=True)

errors = []

with sync_playwright() as p:
    br = p.chromium.launch()
    pg = br.new_page(viewport={"width": 1400, "height": 900})
    console_errors = []
    pg.on("console", lambda msg: console_errors.append(f"[{msg.type}] {msg.text}") if msg.type in ("error", "warning") else None)
    pg.on("pageerror", lambda exc: console_errors.append(f"[pageerror] {exc}"))

    pg.goto(URL, timeout=15000, wait_until="load")
    pg.wait_for_timeout(800)

    n_cards = pg.evaluate("document.querySelectorAll('.svg-wrap').length")
    n_btns = pg.evaluate("document.querySelectorAll('.zoom-btn').length")
    print(f"cards: {n_cards}, zoom buttons: {n_btns}")

    # Click first zoom button
    pg.evaluate("document.querySelector('.zoom-btn').click()")
    pg.wait_for_timeout(1500)

    lb_open = pg.evaluate("document.getElementById('lightbox').classList.contains('open')")
    has_img = pg.evaluate("!!document.querySelector('#lb-content img')")
    img_complete = pg.evaluate("(() => { const i = document.querySelector('#lb-content img'); return i ? {complete: i.complete, naturalWidth: i.naturalWidth, naturalHeight: i.naturalHeight, src: i.src} : null; })()")
    title = pg.evaluate("document.getElementById('lb-title').textContent")
    transform = pg.evaluate("document.getElementById('lb-content').style.transform")
    zoom_label = pg.evaluate("document.getElementById('lb-zoom').textContent")

    print(f"lightbox open: {lb_open}")
    print(f"title: {title}")
    print(f"img element: {has_img}")
    print(f"img info: {img_complete}")
    print(f"transform: {transform}")
    print(f"zoom label: {zoom_label}")

    pg.screenshot(path=str(SCREENSHOT), full_page=False)
    print(f"screenshot: {SCREENSHOT}")

    if console_errors:
        print("\nCONSOLE MESSAGES:")
        for e in console_errors:
            print(" ", e)

    if not lb_open:
        errors.append("lightbox did not open")
    if not has_img:
        errors.append("no <img> in lightbox content")
    if img_complete and not img_complete.get("complete"):
        errors.append("img did not complete loading")
    if img_complete and img_complete.get("naturalWidth", 0) == 0:
        errors.append(f"img naturalWidth is 0 (src={img_complete.get('src')})")

    br.close()

if errors:
    print("\nFAIL:")
    for e in errors:
        print(" -", e)
    sys.exit(1)
print("\nPASS")
