"""Playwright validation of the portal biomarker pane."""
import os
from playwright.sync_api import sync_playwright

PORTAL_URL = "file:///f:/\u2295Workspace/reports/portal.html"
BIOMARKER_PATH = r"f:\∞Life\tmp\biomarker_dashboard.html"

with sync_playwright() as p:
    br = p.chromium.launch()
    pg = br.new_page(viewport={"width": 1400, "height": 900})
    pg.goto(PORTAL_URL, timeout=15000, wait_until="load")
    pg.wait_for_timeout(3000)

    title = pg.title()
    iframe_src = pg.evaluate("document.querySelector('#pane-0 iframe') && document.querySelector('#pane-0 iframe').src")
    frames = pg.frames
    file_exists = os.path.exists(BIOMARKER_PATH)

    print(f"Portal title: {title}")
    print(f"Frame count: {len(frames)}")
    print(f"Biomarker iframe src: {iframe_src}")
    print(f"biomarker_dashboard.html on disk: {file_exists}")

    # Check iframe content
    if len(frames) > 1:
        for i, frame in enumerate(frames[1:], 1):
            try:
                frame_title = frame.title()
                has_chart = frame.evaluate("!!document.getElementById('nutritionChart')")
                has_weight = frame.evaluate("!!document.getElementById('weightChart')")
                print(f"Frame {i} title: {frame_title}")
                print(f"  nutritionChart: {has_chart}, weightChart: {has_weight}")
            except Exception as e:
                print(f"Frame {i} error: {e}")

    pg.screenshot(path=r"f:\∞Life\tmp\portal_biomarker_test.png", full_page=False)
    print("Screenshot: f:\\∞Life\\tmp\\portal_biomarker_test.png")
    br.close()
