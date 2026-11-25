"""Capture real screenshots of every dashboard page (used in the report and PPT).
Start the app first:  streamlit run app.py   then:  python tools/capture_screens.py"""
import asyncio
import sys
from pathlib import Path

from playwright.async_api import async_playwright

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "screenshots")
OUT.mkdir(exist_ok=True)
URL = "http://localhost:8501/?page={}"

SHOTS = [  # (file name, page, tab to click or None)
    ("01_overview", "home", None),
    ("02_cpu", "cpu", None),
    ("03_memory_replacement", "memory", None),
    ("04_memory_belady", "memory", "Belady's anomaly"),
    ("05_memory_translation", "memory", "Address translation"),
    ("06_disk", "disk", None),
    ("07_sync_race", "sync", None),
    ("08_sync_prodcons", "sync", "Producer–consumer"),
    ("09_sync_philosophers", "sync", "Dining philosophers"),
    ("10_deadlock_bankers", "deadlock", None),
    ("11_deadlock_waitfor", "deadlock", "Wait-for graph"),
    ("12_battery_lab", "lab", None),
    ("13_history", "history", None),
]


async def settle(page):
    await page.wait_for_load_state("networkidle")
    for _ in range(60):                              # wait until Streamlit stops "Running…"
        if await page.locator("[data-testid='stStatusWidget']").count() == 0:
            break
        await page.wait_for_timeout(250)
    await page.wait_for_timeout(1500)


async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
        for name, key, tab in SHOTS:
            await page.goto(URL.format(key))
            await settle(page)
            if tab:
                await page.get_by_role("tab", name=tab).click()
                await settle(page)
            # Streamlit scrolls inside its main container, so grow the window to the content height
            h = await page.evaluate("document.querySelector('[data-testid=\"stMain\"]').scrollHeight")
            await page.set_viewport_size({"width": 1440, "height": max(900, int(h) + 40)})
            await settle(page)
            await page.screenshot(path=str(OUT / f"{name}.png"))
            # every chart on the page as its own image (for slides)
            charts = page.locator("[data-testid='stPlotlyChart'], [data-testid='stGraphVizChart']")
            for i in range(await charts.count()):
                el = charts.nth(i)
                if await el.is_visible():
                    await el.screenshot(path=str(OUT / f"{name}__chart{i + 1}.png"))
            await page.set_viewport_size({"width": 1440, "height": 900})
            print("captured", name)
        await browser.close()

asyncio.run(main())
