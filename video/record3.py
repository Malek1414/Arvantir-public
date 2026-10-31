import sys, pathlib
from playwright.sync_api import sync_playwright
V = pathlib.Path(sys.argv[1]); BASE = "http://127.0.0.1:8400"; W, H = 1920, 1080
REPLAY = "f => { document.getElementById('runs').value = f; document.getElementById('replay').click(); }"
with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", headless=True)
    ctx = b.new_context(viewport={"width": W, "height": H}, record_video_dir=str(V / "raw3"), record_video_size={"width": W, "height": H})
    page = ctx.new_page()
    # B4 Demo: Nische tippen, Tabelle, Lead-Karte ACATIS
    page.goto(BASE + "/"); page.evaluate("document.getElementById('demo').scrollIntoView()"); page.wait_for_timeout(600)
    page.click("#niche"); page.fill("#niche", ""); page.type("#niche", "Immobilien Asset Manager", delay=65); page.wait_for_timeout(400)
    page.hover("#go"); page.wait_for_timeout(300)
    page.evaluate(REPLAY, "run_145130.json"); page.wait_for_timeout(2300)
    page.evaluate("document.getElementById('leadSec').scrollIntoView({behavior: 'smooth'})"); page.wait_for_timeout(3000)
    page.click("tbody tr[data-i='3']"); page.wait_for_timeout(5000)
    page.click("#x"); page.wait_for_timeout(400)
    # Bäcker und Metzger, Kanal Brief
    page.evaluate("document.getElementById('demo').scrollIntoView({behavior: 'smooth'})"); page.wait_for_timeout(900)
    page.click("#niche"); page.fill("#niche", ""); page.type("#niche", "Bäckereien und Metzgereien", delay=60); page.wait_for_timeout(300)
    page.evaluate(REPLAY, "run_143435.json"); page.wait_for_timeout(2300)
    page.evaluate("document.getElementById('leadSec').scrollIntoView({behavior: 'smooth'})"); page.wait_for_timeout(2600)
    page.click("tbody tr[data-i='0']"); page.wait_for_timeout(4500)
    # B5 Architektur-Animation
    page.goto(BASE + "/architecture?play&solo"); page.wait_for_timeout(18500)
    ctx.close(); b.close()
print("fertig")
