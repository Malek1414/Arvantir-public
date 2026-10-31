import sys, pathlib
from playwright.sync_api import sync_playwright
V = pathlib.Path(sys.argv[1]); BASE = "http://127.0.0.1:8400"; W, H = 1920, 1080
with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", headless=True)
    ctx = b.new_context(viewport={"width": W, "height": H}, record_video_dir=str(V / "raw2"), record_video_size={"width": W, "height": H})
    page = ctx.new_page()
    # B4 Demo: Nische eintippen, Funnel, Tabelle, Lead-Karte ACATIS
    page.goto(BASE + "/"); page.evaluate("document.getElementById('demo').scrollIntoView()"); page.wait_for_timeout(500)
    page.click("#niche"); page.fill("#niche", ""); page.type("#niche", "Immobilien Asset Manager", delay=60); page.wait_for_timeout(300)
    page.select_option("#runs", "run_145130.json"); page.click("#replay"); page.wait_for_timeout(200)
    page.evaluate("document.getElementById('funnelSec').scrollIntoView({behavior: 'smooth'})"); page.wait_for_timeout(9300)
    page.evaluate("document.getElementById('leadSec').scrollIntoView({behavior: 'smooth'})"); page.wait_for_timeout(1800)
    page.click("tbody tr[data-i='3']"); page.wait_for_timeout(4200)
    page.click("#x"); page.wait_for_timeout(300)
    # kurz Bäcker und Metzger mit Kanal Brief
    page.goto(BASE + "/?replay=run_143435.json"); page.wait_for_timeout(300)
    page.evaluate("document.getElementById('funnelSec').scrollIntoView({behavior: 'smooth'})"); page.wait_for_timeout(8700)
    page.evaluate("document.getElementById('leadSec').scrollIntoView({behavior: 'smooth'})"); page.wait_for_timeout(1600)
    page.click("tbody tr[data-i='0']"); page.wait_for_timeout(3200)
    # B5 Beweis: Architektur-Animation komplett
    page.goto(BASE + "/architecture?play&solo")
    page.wait_for_timeout(18500)
    ctx.close(); b.close()
print("fertig")
