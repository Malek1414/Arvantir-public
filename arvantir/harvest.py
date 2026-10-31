"""harvest: Quelle (Listenseite) -> rohe Firmen-Kandidaten.

Ohne Vorwissen über die Seite:
1. Rohes HTML holen (httpx, bei leerer oder JS-Seite r.jina.ai als Renderer)
2. Wiederholte Blöcke finden (gleiches Tag + gleiche Klasse, viele Geschwister) = Einträge
3. Bester Block = viele, verschiedene, kurze Texte mit Link. Mit LLM-Key wählt das LLM unter den Top-Kandidaten
4. Pro Eintrag: Name, Detail-Link, externe Website, PLZ + Ort
5. Paginierung über rel=next oder "weiter"-Links, höchstens max_pages
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import ipaddress
import socket

import httpx
import warnings

from bs4 import BeautifulSoup, Tag, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

from .common import llm_json

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129 Safari/537.36")
PLZ_ORT = re.compile(r"\b(\d{5})\s+([A-ZÄÖÜ][\wäöüß.\-]+(?:\s(?:an der|am|im|in der|bei|ob der|vor der)\s[A-ZÄÖÜ][\wäöüß.\-]+|\s\([^)]{2,30}\))?)")
NEXT_TXT = re.compile(r"^\s*(weiter|vor|nächste|next|›|»|>)\s*$", re.I)
SKIP_LINK = re.compile(r"(mailto:|tel:|javascript:|#$|linkedin|facebook|instagram|twitter|xing|youtube)", re.I)
LEGAL = re.compile(r"\b(GmbH|mbH|AG|UG|KG|KGaA|e\.\s?K\.|GbR|OHG|Ltd|Inc|SE|e\.V\.|Co\.)\b")
LAYOUT = re.compile(r"\.(col|row|container|wrapper|flex|grid|tw-|clearfix|inner)", re.I)
LEGAL_NAME = re.compile(r"[A-ZÄÖÜ0-9][\w&.,'\- ]{1,60}?\s(?:GmbH & Co\.\s?KG|GmbH|AG|UG(?: \(haftungsbeschränkt\))?|KG|e\.\s?K\.|GbR|OHG|SE|mbH)\b")
NOISE = re.compile(r"^(mehr|details|weiterlesen|profil|zum profil|more|read more|ansehen|website)$", re.I)


def is_public_url(url: str) -> bool:
    """Nur http(s) auf öffentliche Hosts: keine privaten, Loopback- oder Link-Local-Adressen (SSRF)."""
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        return False
    try:
        infos = socket.getaddrinfo(p.hostname, None)
    except socket.gaierror:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False
    return True


def fetch(url: str, timeout: float = 25) -> Tuple[str, str]:
    """(html, final_url). Fällt bei JS-Seiten auf r.jina.ai (HTML-Modus) zurück."""
    html, final = "", url
    if not is_public_url(url):
        print(f"[harvest] abgelehnt (keine öffentliche URL): {url}")
        return "", url
    try:
        with httpx.Client(headers={"User-Agent": UA, "Accept-Language": "de-DE,de;q=0.9"},
                          timeout=timeout, follow_redirects=False) as cl:
            r = cl.get(url)
            for _ in range(5):  # Redirects einzeln prüfen
                if not r.is_redirect:
                    break
                nxt = urljoin(str(r.url), r.headers.get("location", ""))
                if not is_public_url(nxt):
                    return "", url
                r = cl.get(nxt)
        html, final = r.text, str(r.url)
    except httpx.HTTPError as e:
        print(f"[harvest] direkt fehlgeschlagen ({type(e).__name__}): {url}")
    if len(re.sub(r"<script.*?</script>", "", html, flags=re.S)) < 5000:
        try:
            r = httpx.get(f"https://r.jina.ai/{url}", headers={"X-Return-Format": "html"},
                          timeout=60)
            if r.status_code == 200 and len(r.text) > len(html):
                html = r.text
        except httpx.HTTPError:
            pass
    return html, final


ZEBRA = {"even", "odd", "alt", "alternate", "first", "last", "active"}


def _sig(el: Tag) -> str:
    return el.name + "." + ".".join(sorted(c for c in el.get("class", []) if c.lower() not in ZEBRA))


def _text(el: Tag) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True))


def candidate_groups(soup: BeautifulSoup) -> List[Dict]:
    """Gruppen gleichartiger Elemente, bewertet danach, wie sehr sie nach Einträgen aussehen."""
    groups: Dict[str, List[Tag]] = defaultdict(list)
    for el in soup.find_all(["li", "div", "article", "tr", "section", "a", "p"]):
        if el.get("class") or el.name in ("tr", "li", "article"):
            groups[_sig(el)].append(el)
    out = []
    for sig, els in groups.items():
        if not 8 <= len(els) <= 6000:
            continue
        texts = [_text(e) for e in els]
        good = [t for t in texts if 3 <= len(t) <= 400]
        if len(good) < 8:
            continue
        uniq = len(set(good)) / len(good)
        linked = sum(1 for e in els if e.name == "a" or e.find("a", href=True)) / len(els)
        avg = sum(map(len, good)) / len(good)
        nav = any(w in sig.lower() for w in ("nav", "menu", "filter", "select", "letter", "footer",
                                              "breadcrumb", "toc", "schwerpunkt", "tag"))
        legal = sum(1 for t in good if LEGAL.search(t)) / len(good)
        hrefs = [a.get("href", "") for e in els for a in ([e] if e.name == "a" else e.find_all("a", href=True))[:1]]
        hrefs = [h for h in hrefs if h and not h.startswith("#")]
        distinct = len(set(hrefs)) / len(els) if els else 0
        layout = bool(LAYOUT.search(sig)) or sig.endswith(".")
        score = (len(good) * uniq * (0.2 + linked) * (0.2 + distinct) * (1 + 4 * legal)
                 * (1.0 if 8 <= avg <= 250 else 0.3) * (0.1 if nav else 1) * (0.4 if layout else 1))
        out.append({"sig": sig, "els": els, "score": score, "n": len(els),
                    "sample": [t[:90] for t in good[:4]]})
    out.sort(key=lambda g: -g["score"])
    return out


def pick_group(groups: List[Dict], niche: str) -> Optional[Dict]:
    if not groups:
        return None
    top = groups[:6]
    data = llm_json(
        f"Auf einer Verzeichnisseite ({niche}) gibt es diese wiederholten HTML-Blöcke. "
        "Welcher Block ist EIN Firmeneintrag (nicht Navigation, Filter, Buchstaben)? "
        'Antworte {"index": n} oder {"index": -1} wenn keiner.\n'
        + "\n".join(f"{i}: {g['sig'][:80]} x{g['n']} Beispiele: {g['sample']}" for i, g in enumerate(top))
    )
    if data and isinstance(data.get("index"), int):
        i = data["index"]
        return top[i] if 0 <= i < len(top) else None
    return top[0]


def parse_entry(el: Tag, base: str) -> Optional[Dict]:
    host = urlparse(base).netloc.replace("www.", "")
    name = ""
    attrs = [el.get("title", "")] + [a.get("title", "") for a in el.find_all("a", title=True)[:1]]
    attrs += [re.sub(r"\s*(logo|bild|image)$", "", i.get("alt", ""), flags=re.I) for i in el.find_all("img", alt=True)[:1]]
    for t in attrs:
        if 2 <= len(t.strip()) <= 120:
            name = t.strip()
            break
    m_legal = LEGAL_NAME.search(_text(el))
    if not name and m_legal:
        name = m_legal.group(0).strip()
    for sel in ([] if name else ["h1", "h2", "h3", "h4", "h5", "strong", "b", "[class*=title]", "[class*=name]", "a"]):
        node = el.select_one(sel)
        if node:
            t = _text(node)
            if 2 <= len(t) <= 120 and not NOISE.match(t):
                name = t
                break
    if not name:
        t = _text(el)
        name = t[:120] if 2 <= len(t) <= 160 else ""
    if not name:
        return None
    detail, website = "", ""
    links = ([el] if el.name == "a" else []) + el.find_all("a", href=True)
    for a in links:
        href = a.get("href", "")
        if not href or SKIP_LINK.search(href):
            continue
        absu = urljoin(base, href)
        dom = urlparse(absu).netloc.replace("www.", "")
        if dom and dom != host and not website:
            website = absu
        elif dom == host and not detail:
            detail = absu
    m = PLZ_ORT.search(_text(el))
    return {"name": name, "website": website, "detail_url": detail,
            "postcode": m.group(1) if m else "", "city": m.group(2).strip() if m else "",
            "raw_text": _text(el)[:500]}


def next_page(soup: BeautifulSoup, base: str, seen: set) -> Optional[str]:
    link = soup.find("a", rel="next") or soup.find("link", rel="next")
    cands = [link] if link else []
    cands += [a for a in soup.find_all("a", href=True)
              if NEXT_TXT.match(_text(a)) or "next" in " ".join(a.get("class", [])).lower()]
    for a in cands:
        u = urljoin(base, a.get("href", ""))
        if u.startswith("http") and u not in seen and _reg(urlparse(u).netloc) == _reg(urlparse(base).netloc):
            return u
    return None


NAV_NOISE = re.compile(r"(navigation|sprungziel|impressum|datenschutz|kontakt|startseite|öffnet|cookie|"
                       r"login|anmelden|newsletter|suche|menü|menu|barrierefrei|hauptinhalt|zum inhalt|"
                       r"nach oben|drucken|teilen|sitemap|agb|presse|karriere|über uns|footer|header|"
                       r"geschäftsstelle|vorstand|mitglied werden|termine|aktuelles|downloads)", re.I)


def company_like(e: Dict) -> bool:
    """Sieht der Eintrag nach einer Firma aus (Rechtsform, PLZ oder eigene Website, kein Navigationstext)?"""
    if NAV_NOISE.search(e["name"]) and not LEGAL.search(e["name"]):
        return False
    return bool(LEGAL.search(e["name"]) or e.get("postcode") or e.get("website"))


def _is_hub(entries: List[Dict], source_url: str) -> bool:
    """Hub = Seite, deren Einträge auf Unterlisten UNTER ihrem eigenen Pfad zeigen (Städte, Kategorien)."""
    if len(entries) < 5:
        return False
    base = urlparse(source_url).path.rstrip("/")
    sub = sum(1 for e in entries if e.get("detail_url") and not company_like(e)
              and urlparse(e["detail_url"]).path.startswith(base + "/")) / len(entries)
    return sub >= 0.7


def harvest(source_url: str, niche: str = "", max_pages: int = 5, max_items: int = 500,
            max_hubs: int = 4, _depth: int = 0) -> Dict:
    """Alle Einträge einer Listenquelle. Hub-Seiten (Städte, Kategorien) werden eine Ebene tief verfolgt."""
    first = _harvest_list(source_url, niche, max_pages, max_items)
    if _depth == 0 and _is_hub(first["candidates"], source_url):
        def size(e: Dict) -> int:  # "Berlin 119" -> 119, größte Unterlisten zuerst
            m = re.search(r"(\d[\d.]*)\s*$", e["name"])
            return int(m.group(1).replace(".", "")) if m else 0
        subs = sorted(first["candidates"], key=size, reverse=True)[:max_hubs]
        items: List[Dict] = []
        for e in subs:
            r = harvest(e["detail_url"], niche, max_pages=2, max_items=max_items, _depth=1)
            for c in r["candidates"]:
                c["source_url"] = source_url
                c["sub_source"] = e["detail_url"]
            items += r["candidates"]
            if len(items) >= max_items:
                break
        return {"source_url": source_url, "block": first["block"], "pages": first["pages"],
                "hub": [e["detail_url"] for e in subs], "candidates": items[:max_items]}
    return first


def _harvest_list(source_url: str, niche: str = "", max_pages: int = 5, max_items: int = 500) -> Dict:
    url, seen, items, sig = source_url, set(), [], None
    pages = 0
    while url and pages < max_pages and len(items) < max_items:
        seen.add(url)
        html, final = fetch(url)
        pages += 1
        if not html:
            break
        soup = BeautifulSoup(html, "lxml")
        groups = candidate_groups(soup)
        if sig is None:
            g = pick_group(groups, niche)
            if not g:
                break
            sig, els = g["sig"], g["els"]
        else:  # Folgeseiten: gleicher Blocktyp wie auf Seite 1
            els = next((x["els"] for x in groups if x["sig"] == sig), [])
        for el in els:
            if el.name == "tr" and el.find("th") and not el.find("td"):
                continue  # Kopfzeile, keine Firma
            e = parse_entry(el, final)
            if e and not (NAV_NOISE.search(e["name"]) and not LEGAL.search(e["name"])):
                e["source_url"] = source_url
                items.append(e)
        url = next_page(soup, final, seen)
    uniq, keys = [], set()
    for e in items:
        k = (e["name"].lower(), e["website"] or e["detail_url"])
        if k not in keys:
            keys.add(k)
            uniq.append(e)
    return {"source_url": source_url, "block": sig, "pages": pages,
            "candidates": uniq[:max_items]}


BAD_DOMAINS = ("google.", "apple.", "cookiebot", "usercentrics", "w3.org", "schema.org", "gstatic",
               "cloudflare", "gravatar", "wordpress.org", "jquery", "bootstrapcdn", "hubspot", "matomo",
               "openstreetmap", "osm.org", "maps.", "goo.gl", "bing.com", "here.com", "amazon.", "booking.",
               "tripadvisor", "yelp.", "trustpilot", "waze.")


def _reg(netloc: str) -> str:
    """Registrierbare Domain grob: letzte zwei Labels (reicht für .de/.com)."""
    parts = netloc.lower().split(":")[0].split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else netloc.lower()


def resolve_websites(cands: List[Dict], limit: int = 60, workers: int = 8) -> List[Dict]:
    """Fehlende Firmen-Website über die Detailseite im Verzeichnis nachholen."""
    from concurrent.futures import ThreadPoolExecutor

    def one(e: Dict) -> Dict:
        if e.get("website") or not e.get("detail_url"):
            return e
        html, final = fetch(e["detail_url"], timeout=15)
        host = _reg(urlparse(final).netloc)
        soup = BeautifulSoup(html, "lxml")
        tokens = [t for t in re.findall(r"[a-z0-9]{4,}", e["name"].lower())
                  if t not in ("gmbh", "group", "deutschland", "gesellschaft", "germany")]
        best, fallback = "", ""
        for a in soup.find_all("a", href=True):
            if a.find_parent(["footer", "nav", "header"]) or a.find_parent(
                    class_=re.compile(r"footer|nav|menu|header|related|partner|portal", re.I)):
                continue  # Schwesterportale und Navigation sind nie die Firmen-Website
            u = urljoin(final, a["href"])
            dom = _reg(urlparse(u).netloc)
            if not u.startswith("http") or not dom or dom == host or SKIP_LINK.search(u) \
                    or any(x in dom for x in BAD_DOMAINS):
                continue
            if any(t in dom.replace("-", "") for t in tokens):
                best = u
                break
            if not fallback and re.search(r"website|homepage|webseite|internetseite|www\.", _text(a) + " " + a.get("title", ""), re.I):
                fallback = u  # nur ausdrücklich als Website verlinkt
        if best or fallback:
            e["website"] = best or fallback
            e["website_confidence"] = "hoch" if best else "niedrig"
        if not e.get("postcode"):
            m = PLZ_ORT.search(_text(soup.body) if soup.body else "")
            if m:
                e["postcode"], e["city"] = m.group(1), m.group(2).strip()
        return e

    head, tail = cands[:limit], cands[limit:]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        head = list(pool.map(one, head))
    # Eine Domain, die sich mehrere Firmen teilen, ist ein Portal, keine Firmen-Website
    from collections import Counter
    shared = Counter(_reg(urlparse(e["website"]).netloc) for e in head if e.get("website"))
    for e in head:
        if e.get("website") and shared[_reg(urlparse(e["website"]).netloc)] >= 3 \
                and e.get("website_confidence") != "hoch":
            e.pop("website", None)
            e["website_confidence"] = "keine"
    return head + tail
