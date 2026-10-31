"""harvest: Listenblöcke ohne Vorwissen, Hubs, Paginierung, Navigationsmüll, SSRF."""
from __future__ import annotations

import pytest

import arvantir.harvest as h
from conftest import PAGES


def _list(key, max_pages=1):
    return h._harvest_list(PAGES[key]["url"], "test", max_pages=max_pages)


# ---------------------------------------------------------------- echte Seiten

def test_eco_mitglieder_block_and_legal_names(serve):
    serve()
    r = _list("eco_mitglieder")
    names = [c["name"] for c in r["candidates"]]
    assert "ml_picture_wrapper" in r["block"]
    assert len(names) >= 400
    assert "1&1 Versatel GmbH" in names
    with_legal = sum(bool(h.LEGAL.search(n)) for n in names) / len(names)
    assert with_legal > 0.5
    assert all(c["detail_url"].startswith("https://www.eco.de/mitglieder/") for c in r["candidates"][:20])


def test_shopware_partner_entries(serve):
    serve()
    r = _list("shopware_partner")
    names = [c["name"] for c in r["candidates"]]
    assert "partner--item" in r["block"]
    assert {"elio GmbH", "AGIQON GmbH"} <= set(names)
    assert sum(h.company_like(c) for c in r["candidates"]) >= 10


def test_waschanlagen_city_page_has_postcodes(serve):
    serve()
    r = _list("waschanlagen_berlin")
    c = r["candidates"]
    assert r["block"] == "li.card"
    assert len(c) >= 100
    assert sum(1 for e in c if e["postcode"].startswith(("10", "12", "13", "14"))) / len(c) > 0.8


def test_city_without_trailing_label(serve):
    serve()
    cities = {e["city"] for e in _list("waschanlagen_berlin")["candidates"] if e["city"]}
    assert cities == {"Berlin"}


def test_bafin_table_rows(serve):
    serve()
    names = [c["name"] for c in _list("bafin")["candidates"]]
    assert "A. Messner Leasing GmbH & Co. KG" in names
    assert len(names) >= 40


def test_bafin_header_row_is_not_a_company(serve):
    serve()
    assert "Unternehmen" not in [c["name"] for c in _list("bafin")["candidates"]]


# ---------------------------------------------------------------- Hub

def test_hub_detected_and_followed(serve):
    calls = serve()
    hub = PAGES["waschanlagen_hub"]["url"]
    first = _list("waschanlagen_hub")
    assert h._is_hub(first["candidates"], hub)
    r = h.harvest(hub, "Waschanlagen", max_items=500)
    # größte Unterliste zuerst: das Bundesland NRW (eigene Fixture), nicht die Städte
    assert r["hub"][0] == PAGES["waschanlagen_nrw"]["url"]
    assert PAGES["waschanlagen_nrw"]["url"] in calls
    assert len(r["candidates"]) >= 100
    assert all(c["source_url"] == hub for c in r["candidates"])
    assert r["candidates"][0]["sub_source"] == PAGES["waschanlagen_nrw"]["url"]
    assert not h._is_hub(r["candidates"], PAGES["waschanlagen_nrw"]["url"])  # NRW ist schon eine Firmenliste


def test_company_list_is_not_a_hub(serve):
    serve()
    r = _list("eco_mitglieder")
    assert not h._is_hub(r["candidates"], PAGES["eco_mitglieder"]["url"])


# ---------------------------------------------------------------- Paginierung

def _page(n, nxt):
    items = "".join(f'<li class="firma"><a href="/firma/{n}-{i}">Firma {n}{i} GmbH</a> 1011{i} Berlin</li>'
                    for i in range(10))
    link = f'<a class="pager" href="{nxt}">weiter</a>' if nxt else ""
    return f"<html><body><ul>{items}</ul>{link}</body></html>"


def test_pagination_follows_weiter(serve):
    base = "https://verband.example.de/mitglieder"
    calls = serve({base: _page(1, base + "?p=2"), base + "?p=2": _page(2, base + "?p=3"),
                   base + "?p=3": _page(3, None)})
    r = h._harvest_list(base, "x", max_pages=5)
    assert r["pages"] == 3
    assert len(r["candidates"]) == 30
    assert calls == [base, base + "?p=2", base + "?p=3"]


def test_pagination_stops_at_max_pages(serve):
    base = "https://verband.example.de/mitglieder"
    serve({base: _page(1, base + "?p=2"), base + "?p=2": _page(2, base + "?p=3"),
           base + "?p=3": _page(3, None)})
    assert h._harvest_list(base, "x", max_pages=2)["pages"] == 2


def test_next_page_on_bafin():
    from bs4 import BeautifulSoup
    from conftest import page
    soup = BeautifulSoup(page("bafin"), "lxml")
    nxt = h.next_page(soup, PAGES["bafin"]["final"], set())
    assert nxt and "p=2" in nxt


def test_next_page_never_leaves_domain():
    from bs4 import BeautifulSoup
    soup = BeautifulSoup('<a href="https://evil.example.com/p2">weiter</a>', "lxml")
    assert h.next_page(soup, "https://verband.de/liste", set()) is None


# ---------------------------------------------------------------- Navigationsmüll

NAV_PAGE = """<html><body>
<ul class="nav">""" + "".join(f'<li class="nav-item"><a href="/{w.lower()}">{w}</a></li>' for w in
    ["Startseite", "Impressum", "Datenschutz", "Kontakt", "Newsletter", "Login", "Sitemap", "Presse",
     "Karriere", "Über uns"]) + """</ul>
<div class="list">""" + "".join(
    f'<div class="member"><h3>Bäckerei Muster{i} GmbH</h3><a href="https://baeckerei{i}.de">Website</a>'
    f' Hauptstr. {i}, 1411{i} Potsdam</div>' for i in range(10)) + """</div>
<footer>""" + "".join(f'<p class="foot">{w}</p>' for w in
    ["Impressum", "Datenschutz", "Cookie-Einstellungen", "AGB", "Barrierefreiheit", "Nach oben",
     "Drucken", "Teilen", "Kontakt", "Menü"]) + """</footer></body></html>"""


def test_navigation_noise_is_dropped(serve):
    url = "https://innung.example.de/betriebe"
    serve({url: NAV_PAGE})
    r = h._harvest_list(url, "Bäckereien")
    names = [c["name"] for c in r["candidates"]]
    assert r["block"] == "div.member"
    assert len(names) == 10
    assert not any(w in " ".join(names) for w in ("Impressum", "Datenschutz", "Kontakt"))
    assert r["candidates"][0]["website"] == "https://baeckerei0.de"
    assert r["candidates"][0]["postcode"] == "14110"


@pytest.mark.parametrize("entry,ok", [
    ({"name": "Müller Backwaren GmbH"}, True),
    ({"name": "Waschpark Nord", "postcode": "10115"}, True),
    ({"name": "Autopflege Süd", "website": "https://autopflege.de"}, True),
    ({"name": "Impressum"}, False),
    ({"name": "Kontakt", "website": "https://x.de"}, False),
    ({"name": "Datenschutz GmbH"}, True),  # Rechtsform schlägt Navigationswort
    ({"name": "Berlin 119", "detail_url": "https://x.de/berlin/"}, False),
])
def test_company_like(entry, ok):
    assert h.company_like(entry) is ok


# ---------------------------------------------------------------- SSRF

@pytest.mark.parametrize("url", [
    "http://127.0.0.1/", "http://localhost:8400/runs", "http://169.254.169.254/latest/meta-data/",
    "http://10.0.0.5/admin", "http://192.168.1.1/", "http://172.16.0.1/", "http://[::1]/",
    "http://0.0.0.0/", "file:///etc/passwd", "ftp://example.com/x", "gopher://127.0.0.1:6379/",
])
def test_is_public_url_rejects_internal(url):
    assert h.is_public_url(url) is False


def test_is_public_url_accepts_public_ip():
    assert h.is_public_url("https://93.184.215.14/") is True


def test_fetch_never_connects_to_metadata(monkeypatch):
    class Boom:
        def __init__(self, *a, **k):
            raise AssertionError("fetch hat trotz interner URL eine Verbindung aufgebaut")

    monkeypatch.setattr(h.httpx, "Client", Boom)
    monkeypatch.setattr(h.httpx, "get", Boom)
    assert h.fetch("http://169.254.169.254/latest/meta-data/") == ("", "http://169.254.169.254/latest/meta-data/")


def test_fetch_blocks_redirect_to_internal(monkeypatch):
    """Öffentliche URL, die per 302 auf die Metadaten-IP umleitet: Ergebnis leer."""
    monkeypatch.setattr(h, "is_public_url", lambda u: "169.254" not in u)

    class Resp:
        def __init__(self, url, loc=None):
            self.url, self.is_redirect = url, bool(loc)
            self.headers = {"location": loc} if loc else {}
            self.text = "geheim" if "169.254" in url else ""

    class Client:
        def __init__(self, *a, **k): ...
        def __enter__(self): return self
        def __exit__(self, *a): ...
        def get(self, url):
            if "169.254" in url:
                raise AssertionError("Redirect auf interne IP wurde verfolgt")
            return Resp(url, "http://169.254.169.254/latest/")

    monkeypatch.setattr(h.httpx, "Client", Client)
    monkeypatch.setattr(h.httpx, "get", lambda *a, **k: Resp("x"))
    html, _ = h.fetch("https://public.example.com/")
    assert "geheim" not in html


# ---------------------------------------------------------------- Website-Auflösung

DETAIL = """<html><body><h1>Agip Autowaschanlage</h1><p>Ludwigsluster Straße, 12619 Berlin</p>
<footer><a href="https://kinderspielplatz-deutschland.de/">Spielplätze</a>
<a href="https://waschsalons-deutschland.de/">Waschsalons</a></footer></body></html>"""


def test_resolve_website_matches_company_name(serve):
    url = "https://verzeichnis.example.de/anlage/mueller"
    serve({url: '<a href="https://partnerportal.de/">Partner</a> <a href="https://www.mueller-waschpark.de">Website</a>'})
    e = h.resolve_websites([{"name": "Müller Waschpark", "website": "", "detail_url": url, "postcode": ""}])[0]
    assert e["website"] == "https://www.mueller-waschpark.de"
    assert e["website_confidence"] == "hoch"


def test_resolve_website_ignores_footer_portals(serve):
    url = "https://waschanlagen-deutschland.de/anlage/agip-autowaschanlage-berlin/"
    serve({url: DETAIL})
    e = h.resolve_websites([{"name": "Agip Autowaschanlage", "website": "", "detail_url": url, "postcode": ""}])[0]
    assert not e.get("website")
