"""discover: Branche oder Beispiel-Lead -> sortierte Liste von Quellen (Verzeichnisse, Listen, PDFs).

1. Suchanfragen in deutschem Verzeichnis-Vokabular bauen (LLM, sonst feste Vorlagen)
2. Parallel über searchify.search suchen, Treffer zusammenführen
3. Kuratierte Quellen aus research/sources.json dazunehmen
4. Mit dem Cross-Encoder gegen "Liste vieler {Branche}-Firmen" re-ranken
"""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List
from urllib.parse import urlparse

from searchify import score as rr_score
from searchify import search

from .common import llm_json, log_pairs, to_100

ROOT = Path(__file__).resolve().parent.parent

TEMPLATES = [
    "{n} Mitgliederverzeichnis",
    "{n} Mitglieder Liste Verband",
    "{n} Innung Mitgliedsbetriebe",
    "{n} Ausstellerverzeichnis Messe 2026",
    "{n} Partnerverzeichnis Deutschland",
    "{n} Verzeichnis Anbieter Deutschland",
    "{n} Vergleichsportal Anbieter",
    "Mitgliederliste {n} filetype:pdf",
]

# Seiten, die nie eine Firmenliste für den Dark TAM sind
BLOCK = re.compile(r"(linkedin\.|facebook\.|instagram\.|youtube\.|wikipedia\.|indeed\.|stepstone\.|"
                   r"xing\.|twitter\.|x\.com|tiktok\.|amazon\.|ebay\.|imdb\.|netflix\.)")

# Nur DACH-Länderendungen plus generische; alles andere (zw, ru, cn, ...) fliegt raus
TLD_OK = {"de", "at", "ch", "com", "org", "net", "eu", "info", "io", "biz", "berlin", "bayern", "nrw",
          "hamburg", "koeln", "cologne", "ruhr", "saarland", "sachsen", "app", "online", "digital", "gmbh", "ag"}
ADULT = re.compile(r"(xnxx|xhamster|porn|hentai|xxx|sex|nude|escort|erotik|onlyfans|camgirl|casino|bet\d|"
                   r"redtube|youporn|pornhub|xvideos|brazzers)", re.I)
MIN_SCORE = 20  # darunter sind Suchtreffer fast nie Firmenlisten


def _allowed(url: str, title: str = "") -> bool:
    host = urlparse(url).netloc.lower()
    tld = host.rsplit(".", 1)[-1] if "." in host else ""
    return (tld in TLD_OK and not BLOCK.search(host) and not ADULT.search(url)
            and not ADULT.search(title))


TYPE_HINTS = [
    ("pdf", re.compile(r"\.pdf($|\?)|filetype", re.I)),
    ("Aussteller", re.compile(r"ausstell|exhibitor|messe", re.I)),
    ("Partnerverzeichnis", re.compile(r"partner", re.I)),
    ("Verband", re.compile(r"mitglied|innung|verband|member", re.I)),
    ("Vergleichsportal", re.compile(r"vergleich|bewertung|test|ranking|top-?\d+", re.I)),
    ("Register", re.compile(r"register|bafin|datenbank|suche", re.I)),
]


def _guess_type(url: str, text: str) -> str:
    for name, rx in TYPE_HINTS:
        if rx.search(url) or rx.search(text[:300]):
            return name
    return "Verzeichnis"


def understand(seed: str) -> Dict:
    """Beispiel-URL oder Freitext -> {niche, queries, list_query}."""
    is_url = bool(re.match(r"https?://", seed.strip()))
    niche = seed.strip()
    queries: List[str] = []
    data = llm_json(
        "Wir suchen den Dark TAM: deutsche Firmen einer Nische, die in keiner Lead-Datenbank stehen. "
        "Sie stehen in Verbands- und Innungslisten, Messe-Ausstellerverzeichnissen, Partnerverzeichnissen "
        "von Software-Herstellern, Vergleichsportalen, öffentlichen Registern und PDF-Mitgliederlisten.\n"
        f"Eingabe ({'Beispiel-Firma' if is_url else 'Nische'}): {seed}\n"
        'Gib JSON: {"niche": "kurze deutsche Bezeichnung der Nische", '
        '"queries": ["10 bis 14 deutsche Suchanfragen, die genau solche Listen finden, mit konkreten '
        'Verbands-, Messe- und Softwarenamen, mindestens 2 mit filetype:pdf"]}'
    )
    if data:
        niche = data.get("niche") or niche
        queries = [q for q in data.get("queries", []) if isinstance(q, str)]
    if not queries:
        # "&" und "und" zerlegen: "Bäckereien & Metzgereien" -> zwei Nischen, sonst liefert DDG Müll
        parts = [p.strip() for p in re.split(r"\s*(?:&|\bund\b|,|/)\s*", niche) if len(p.strip()) > 2]
        queries = [t.format(n=p) for p in parts or [niche] for t in TEMPLATES]
    return {
        "niche": niche,
        "queries": queries,
        "list_query": f"Verzeichnis oder Liste vieler {niche} Firmen in Deutschland: "
                      f"Mitgliederliste, Ausstellerverzeichnis, Partnerverzeichnis",
    }


SINGULAR = {"ärzte": "arzt", "zahnärzte": "zahnarzt", "steuerberater": "steuerberater",
            "family offices": "family office", "lps": "vermögensverwaltung"}
CITIES = ["berlin", "münchen"]


def _singular(word: str) -> str:
    w = word.strip().lower()
    if w in SINGULAR:
        return SINGULAR[w]
    if w.endswith("eien"):
        return w[:-2]          # bäckereien -> bäckerei
    if w.endswith("en") and not w.endswith("leister"):
        return w[:-1]          # apotheken -> apotheke, waschanlagen -> waschanlage
    return w


def branchenbuch(niche: str) -> List[Dict]:
    """Rückfall für lokale Betriebe: Gelbe Seiten je Nischen-Teil und Stadt (statisches HTML, Name + PLZ)."""
    from urllib.parse import quote
    parts = [p for p in re.split(r"\s*(?:&|\bund\b|,|/)\s*", niche) if len(p.strip()) > 2]
    out = []
    for p in parts:
        term = _singular(p)
        for city in CITIES:
            out.append({"url": f"https://www.gelbeseiten.de/suche/{quote(term)}/{quote(city)}",
                        "title": f"Branchenbuch: {p} in {city.title()}",
                        "content": f"Branchenbuch-Liste vieler {p} Betriebe in {city.title()} mit Adresse, "
                                   f"Postleitzahl und Website. Verzeichnis lokaler Firmen.",
                        "origin": "branchenbuch"})
    return out


def curated(niche: str) -> List[Dict]:
    """Quellen aus der Recherche des Searchify-Terminals, passend zur Nische."""
    path = ROOT / "research" / "sources.json"
    if not path.exists():
        return []
    words = {w for w in re.findall(r"\w{4,}", niche.lower())}
    out = []
    for s in json.loads(path.read_text(encoding="utf-8")):
        hay = (s.get("niche", "") + " " + s.get("note", "")).lower()
        if words & set(re.findall(r"\w{4,}", hay)) and s.get("url", "").startswith("http"):
            out.append({
                "url": s["url"].split(" ")[0],
                "title": f"{s.get('type', '')}: {s.get('niche', '')}",
                "content": f"{s.get('type', '')}. {s.get('entries', '')}. {s.get('note', '')}",
                "origin": "kuratiert",
            })
    return out


def discover(seed: str, limit: int = 15, per_query: int = 8) -> Dict:
    plan = understand(seed)
    with ThreadPoolExecutor(max_workers=6) as pool:
        batches = list(pool.map(lambda q: _safe_search(q, per_query), plan["queries"]))

    seen, hits = set(), []
    for q, batch in zip(plan["queries"], batches):
        for h in batch:
            url = h.get("url", "")
            key = url.split("#")[0].rstrip("/")
            if not url or key in seen or not _allowed(url, h.get("title", "")):
                continue
            seen.add(key)
            hits.append({"url": url, "title": h.get("title", ""),
                         "content": h.get("content", ""), "origin": f"suche: {q}"})
    for c in curated(plan["niche"]) + branchenbuch(plan["niche"]):
        key = c["url"].rstrip("/")
        if key not in seen:
            seen.add(key)
            hits.append(c)

    docs = [f"{h['title']}. {h['content']} ({h['url']})" for h in hits]
    raw = rr_score(plan["list_query"], docs) if docs else []
    for h, d, s in zip(hits, docs, raw):
        h["doc"] = d
        h["score"] = to_100(s)
        if h["origin"] in ("kuratiert", "branchenbuch"):  # geprüft bzw. verlässlich lesbar, leicht vorziehen
            h["score"] = min(100, h["score"] + 10)
        h["type"] = "Branchenbuch" if h["origin"] == "branchenbuch" else \
            _guess_type(h["url"], h["title"] + " " + h["content"])
        h["reason"] = (h["content"] or h["title"])[:180]
    hits = [h for h in hits if h["origin"] in ("kuratiert", "branchenbuch") or h["score"] >= MIN_SCORE]
    hits.sort(key=lambda h: -h["score"])
    log_pairs("source", plan["niche"], plan["list_query"], hits, "doc")
    return {**plan, "sources": hits[:limit], "candidates_total": len(hits)}


def _safe_search(q: str, n: int) -> List[Dict]:
    try:
        return search(q, max_results=n)
    except Exception as e:  # noqa: BLE001 - eine kaputte Anfrage soll den Lauf nicht stoppen
        print(f"[discover] Suche fehlgeschlagen ({type(e).__name__}): {q}")
        return []
