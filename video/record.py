import sys, time, urllib.parse, pathlib
from playwright.sync_api import sync_playwright
V = pathlib.Path(sys.argv[1]); BASE = "http://127.0.0.1:8400"
W, H = 1920, 1080
def card(page, t, s="", k="", logo=False, hold=4.0):
    q = urllib.parse.urlencode({"t": t, "s": s, "k": k, **({"logo": "1"} if logo else {})})
    page.goto(f"file://{V}/card.html?{q}"); page.wait_for_timeout(int(hold * 1000))
def wheel(page, total, steps=60, pause=40):
    for _ in range(steps):
        page.mouse.wheel(0, total / steps); page.wait_for_timeout(pause)
with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", headless=True)
    ctx = b.new_context(viewport={"width": W, "height": H}, record_video_dir=str(V / "raw"), record_video_size={"width": W, "height": H})
    page = ctx.new_page()
    # 1 Intro: Palantir wird durchgestrichen, Arvantir
    page.goto(BASE + "/"); page.mouse.move(W - 40, H - 40); page.wait_for_timeout(4800)
    # 2 Die Aufgabe laut Folie
    card(page, "Find the dark TAM.", "Companies no lead database knows. Only leads not in AI Ark count.", k="Arvana challenge", hold=4.5)
    # 3 So funktioniert es
    page.goto(BASE + "/"); page.wait_for_timeout(600)
    page.evaluate("document.querySelector('.pipe').scrollIntoView()"); page.wait_for_timeout(4000)
    # 4 Demo: beliebige Nische rein, Company | Decision maker | ICP raus
    card(page, "Give it any niche.", "Get company, decision maker and ICP score.", hold=4)
    page.goto(BASE + "/"); page.evaluate("document.getElementById('demo').scrollIntoView()"); page.wait_for_timeout(700)
    page.click("#niche"); page.fill("#niche", ""); page.type("#niche", "Immobilien Asset Manager", delay=70); page.wait_for_timeout(500)
    page.select_option("#runs", "run_145130.json"); page.wait_for_timeout(400)
    page.click("#replay"); page.wait_for_timeout(300)
    page.evaluate("document.getElementById('funnelSec').scrollIntoView({behavior: 'smooth'})")
    page.wait_for_timeout(9800)
    page.evaluate("document.getElementById('leadSec').scrollIntoView({behavior: 'smooth'})"); page.wait_for_timeout(2200)
    for i in range(5):
        page.hover(f"tbody tr[data-i='{i}']"); page.wait_for_timeout(300)
    page.click("tbody tr[data-i='3']"); page.wait_for_timeout(6000)
    page.click("#x"); page.wait_for_timeout(500)
    # 6 Bäckereien: Kanal Brief
    card(page, "Bakeries don't answer cold email.", "So every lead gets a channel: letter, phone or LinkedIn.", hold=4)
    page.goto(BASE + "/?replay=run_143435.json"); page.wait_for_timeout(400)
    page.evaluate("document.getElementById('funnelSec').scrollIntoView({behavior: 'smooth'})"); page.wait_for_timeout(9400)
    page.evaluate("document.getElementById('leadSec').scrollIntoView({behavior: 'smooth'})"); page.wait_for_timeout(2200)
    page.click("tbody tr[data-i='0']"); page.wait_for_timeout(5500)
    page.click("#x"); page.wait_for_timeout(400)
    # 7 Architektur
    card(page, "Built for Clay, Supabase and Claude Code.", "Raw pages kept, every field with its source.", hold=4)
    page.goto(BASE + "/architecture"); page.wait_for_timeout(3500)
    wheel(page, 700, steps=40, pause=60); page.wait_for_timeout(3000)
    # 8 Schluss
    card(page, "Arvantir.", "The data pipeline for the dark TAM.", logo=True, hold=5)
    ctx.close(); b.close()
print("fertig")
