"""Frische Kaufsignale je Lead: LinkedIn-Posts (über den Suchindex), News, Hiring, Funding.

Schnittstelle für pipeline.py:
    signals(cands, niche, top=25) -> cands
hängt an die ersten `top` Kandidaten `signals`, `signal_score`, `freshest_signal_days`.

Bewertung nach Arvanas buying-signal-detector (research/ARVANA_WORKFLOW.md):
Stärke hoch 3, mittel 2, niedrig 1, +2 bei Kombination aus mindestens zwei Signaltypen,
nur Signale jünger als 6 Monate.

Nur öffentliche Quellen ohne Login. LinkedIn wird nie direkt abgerufen, nur über
Google-Treffer via serper.dev (SERPER_API_KEY aus der Umgebung / .env).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

import httpx

TIMEOUT = 10.0
MAX_AGE_DAYS = 182
CACHE_TTL_S = 6 * 3600
CACHE = Path(__file__).resolve().parent.parent / "data" / "cache" / "signals"
UA = {"User-Agent": "Mozilla/5.0 (Arvantir research bot; public data only)"}

STRENGTH = {"funding": 3, "hiring_sales": 3, "hiring": 2, "news": 2,
            "linkedin_post_fresh": 2, "linkedin_post": 1, "event": 1, "website_change": 1}
SALES_ROLES = re.compile(r"\b(sales|vertrieb|sdr|bdr|business development|account (executive|manager)"
                         r"|growth|marketing|key account|außendienst|aussendienst)\b", re.I)
FUNDING_FEEDS = ["https://startupdetector.de/feed/", "https://www.deutsche-startups.de/feed/"]
LEGAL = re.compile(r"\b(gmbh\s*&\s*co\.?\s*kg|gmbh|ug \(haftungsbeschränkt\)|ug|ag|kg|ohg|e\.\s?k\.|gbr|"
                   r"mbh|se|ltd\.?|inc\.?|s\.p\.a\.|sgr|zweigniederlassung deutschland|e\.v\.)\b", re.I)

_feed_lock = Lock()
_feed_items: Optional[List[dict]] = None


# ---------- Helfer ----------

def _today() -> date:
    return datetime.now(timezone.utc).date()


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _core_name(name: str) -> str:
    core = LEGAL.sub(" ", name or "")
    core = re.sub(r"[|,(].*$", "", core)
    return _fold(core)


def _mentions(text: str, core: str, raw_name: str = "") -> bool:
    """Firma im Text? Einwortige Namen ("elio", "hmmh") sind mehrdeutig: dann muss das Wort in der
    Schreibweise des Originalnamens vorkommen (Groß/Klein), sonst zählt der Treffer nicht."""
    if not core or len(core) < 4 or f" {core} " not in f" {_fold(text)} ":
        return False
    if " " in core or not raw_name:
        return True
    token = re.sub(LEGAL, " ", raw_name).strip().split()[0] if raw_name.strip() else ""
    return bool(token) and re.search(rf"(?<!\w){re.escape(token)}(?!\w)", text) is not None


def _domain_stem(website: str) -> str:
    host = urlparse(website if "//" in (website or "") else f"https://{website}").hostname or ""
    host = host.removeprefix("www.")
    return host.split(".")[0] if host else ""


_REL = [
    (re.compile(r"(\d+)\s*(min|minute|minuten|std|stunde|stunden|hour|hours|h)\b", re.I), 0),
    (re.compile(r"(\d+)\s*(tag|tage|tagen|day|days|d)\b", re.I), 1),
    (re.compile(r"(\d+)\s*(woche|wochen|week|weeks|w)\b", re.I), 7),
    (re.compile(r"(\d+)\s*(monat|monate|monaten|month|months|mo)\b", re.I), 30),
    (re.compile(r"(\d+)\s*(jahr|jahre|jahren|year|years|y)\b", re.I), 365),
]
_MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
_MONTHS.update({"mär": 3, "mai": 5, "okt": 10, "dez": 12})


def _parse_date(s: str) -> Optional[date]:
    """'vor 3 Tagen', '2 days ago', '31.10.2026', 'Oct 29, 2026', ISO, RFC 2822."""
    if not s:
        return None
    s = s.strip()
    for rx, mult in _REL:
        m = rx.search(s)
        if m:
            return _today() - timedelta(days=int(m.group(1)) * mult)
    if re.search(r"\b(heute|today|gestern|yesterday)\b", s, re.I):
        return _today() - timedelta(days=0 if re.search(r"heute|today", s, re.I) else 1)
    m = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", s)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    m = re.search(r"([A-Za-zäÄ]{3})[a-zä]*\.?\s+(\d{1,2}),?\s+(\d{4})", s)
    if m and m.group(1).lower() in _MONTHS:
        try:
            return date(int(m.group(3)), _MONTHS[m.group(1).lower()], int(m.group(2)))
        except ValueError:
            pass
    try:
        return parsedate_to_datetime(s).date()
    except (TypeError, ValueError):
        return None


def _sig(type_: str, title: str, url: str, d: Optional[date], strength_key: str) -> Optional[dict]:
    if d is None:
        return None
    age = (_today() - d).days
    if age < 0:
        age = 0
    if age > MAX_AGE_DAYS:
        return None
    return {"type": type_, "title": (title or "").strip()[:200], "url": url,
            "date": d.isoformat(), "age_days": age, "score": STRENGTH[strength_key]}


# ---------- Quellen ----------

def _serper(client: httpx.Client, endpoint: str, q: str, tbs: str, num: int = 10) -> List[dict]:
    key = os.getenv("SERPER_API_KEY")
    if not key:
        raise httpx.HTTPError("SERPER_API_KEY fehlt")
    r = client.post(f"https://google.serper.dev/{endpoint}",
                    headers={"X-API-KEY": key, "Content-Type": "application/json"},
                    json={"q": q, "gl": "de", "hl": "de", "tbs": tbs, "num": num}, timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json()
    return data.get("news" if endpoint == "news" else "organic", []) or []


_LI_ID = re.compile(r"(?:activity|share|ugcPost)[-:](\d{18,20})")


def _li_date(url: str) -> Optional[date]:
    """LinkedIn-Post-IDs tragen den Zeitstempel: die oberen 41 Bit sind Millisekunden seit 1970."""
    m = _LI_ID.search(url or "")
    if not m:
        return None
    try:
        return datetime.fromtimestamp((int(m.group(1)) >> 22) / 1000, timezone.utc).date()
    except (ValueError, OverflowError, OSError):
        return None


def _local_search(client: httpx.Client, q: str, domains: List[str]) -> List[dict]:
    """Eigener Such-Dienst (tavily-clone, OWN_SEARCH_URL), kostenlos, als Fallback ohne Serper-Credits."""
    base = os.getenv("OWN_SEARCH_URL", "http://127.0.0.1:8000")
    r = client.post(f"{base}/search", json={"query": q, "max_results": 10, "include_domains": domains},
                    timeout=TIMEOUT)
    r.raise_for_status()
    return [{"title": h.get("title", ""), "link": h.get("url", ""), "snippet": h.get("content", "")}
            for h in r.json().get("results", [])]


def _exa_linkedin(client: httpx.Client, q: str) -> List[dict]:
    """Exa-Suche auf linkedin.com, letzte 180 Tage, mit publishedDate (EXA_API_KEY aus der Umgebung)."""
    key = os.getenv("EXA_API_KEY")
    if not key:
        raise httpx.HTTPError("EXA_API_KEY fehlt")
    start = (_today() - timedelta(days=MAX_AGE_DAYS)).isoformat() + "T00:00:00.000Z"
    r = client.post("https://api.exa.ai/search", headers={"x-api-key": key, "Content-Type": "application/json"},
                    json={"query": q, "includeDomains": ["linkedin.com"], "startPublishedDate": start,
                          "numResults": 5, "contents": {"text": {"maxCharacters": 400}}}, timeout=TIMEOUT)
    r.raise_for_status()
    return [{"title": h.get("title") or "", "link": h.get("url", ""), "snippet": h.get("text") or "",
             "date": h.get("publishedDate") or ""} for h in r.json().get("results", [])]


def _linkedin(client: httpx.Client, c: dict, core: str) -> List[dict]:
    q = f'"{c["name"]}" (site:linkedin.com/posts OR site:linkedin.com/pulse)'
    # Stufen: Serper -> Exa -> eigener Such-Dienst (jeweils nur, wenn die vorige scheitert)
    try:
        hits = _serper(client, "search", q, "qdr:m")
    except httpx.HTTPError:
        try:
            hits = _exa_linkedin(client, f'{c["name"]} {c.get("city") or ""}'.strip())
        except httpx.HTTPError:
            hits = _local_search(client, f'"{c["name"]}"', ["linkedin.com"])
    out = []
    for hit in hits:
        link = hit.get("link", "")
        if "linkedin.com/posts" not in link and "linkedin.com/pulse" not in link:
            continue
        if not _mentions(f'{hit.get("title", "")} {hit.get("snippet", "")}', core, c["name"]):
            continue
        # Datum: Post-ID > Datum im Treffer > nichts (ohne Datum kein Signal, keine geratene Frische)
        d = _li_date(link) or _parse_date(hit.get("date", ""))
        if d is None:
            continue
        s = _sig("linkedin_post", hit.get("title", ""), link, d,
                 "linkedin_post_fresh" if (_today() - d).days <= 7 else "linkedin_post")
        if s:
            out.append(s)
    return out[:3]


def _google_news(client: httpx.Client, q: str) -> List[dict]:
    """Google-News-RSS, keyless, mit echtem pubDate."""
    r = client.get("https://news.google.com/rss/search",
                   params={"q": f"{q} when:180d", "hl": "de", "gl": "DE", "ceid": "DE:de"}, timeout=TIMEOUT)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    return [{"title": it.findtext("title", ""), "link": it.findtext("link", ""), "snippet": "",
             "source": it.findtext("source", ""), "date": it.findtext("pubDate", "")} for it in root.iter("item")]


def _news(client: httpx.Client, c: dict, core: str) -> List[dict]:
    q = f'"{c["name"]}" {c.get("city") or ""}'.strip()
    try:
        hits = _serper(client, "news", q, "qdr:m6")
    except httpx.HTTPError:
        hits = _google_news(client, f'"{_core_name(c["name"]) or c["name"]}"')
    out = []
    for hit in hits:
        if "linkedin.com" in hit.get("link", ""):
            continue
        if not _mentions(f'{hit.get("title", "")} {hit.get("snippet", "")}', core, c["name"]):
            continue
        src = f' ({hit["source"]})' if hit.get("source") and hit["source"] not in hit.get("title", "") else ""
        s = _sig("news", f'{hit.get("title", "")}{src}', hit.get("link", ""), _parse_date(hit.get("date", "")), "news")
        if s:
            out.append(s)
    return out[:3]


def _ats(client: httpx.Client, stem: str) -> List[dict]:
    """Öffentliche Job-Boards ohne Key: Greenhouse, Lever, Ashby, Personio."""
    if not stem or len(stem) < 3:
        return []
    jobs: List[tuple] = []  # (titel, url, datum)
    try:
        r = client.get(f"https://boards-api.greenhouse.io/v1/boards/{stem}/jobs", timeout=TIMEOUT)
        if r.status_code == 200:
            for j in r.json().get("jobs", []):
                jobs.append((j.get("title", ""), j.get("absolute_url", ""), _parse_date(j.get("updated_at", ""))))
    except (httpx.HTTPError, ValueError):
        pass
    try:
        r = client.get(f"https://api.lever.co/v0/postings/{stem}?mode=json", timeout=TIMEOUT)
        if r.status_code == 200 and isinstance(r.json(), list):
            for j in r.json():
                ts = j.get("createdAt")
                d = datetime.fromtimestamp(ts / 1000, timezone.utc).date() if ts else None
                jobs.append((j.get("text", ""), j.get("hostedUrl", ""), d))
    except (httpx.HTTPError, ValueError):
        pass
    try:
        r = client.get(f"https://api.ashbyhq.com/posting-api/job-board/{stem}", timeout=TIMEOUT)
        if r.status_code == 200:
            for j in r.json().get("jobs", []):
                jobs.append((j.get("title", ""), j.get("jobUrl", ""), _parse_date(j.get("publishedAt", ""))))
    except (httpx.HTTPError, ValueError):
        pass
    try:
        r = client.get(f"https://{stem}.jobs.personio.de/xml", timeout=TIMEOUT)
        if r.status_code == 200 and "<position" in r.text:
            root = ET.fromstring(r.content)
            for p in root.iter("position"):
                jobs.append((p.findtext("name", ""), f"https://{stem}.jobs.personio.de/job/{p.findtext('id', '')}",
                             _parse_date(p.findtext("createdAt", ""))))
    except (httpx.HTTPError, ET.ParseError):
        pass

    out = []
    for title, url, d in sorted(jobs, key=lambda j: j[2] or date.min, reverse=True):
        s = _sig("hiring", title, url, d, "hiring_sales" if SALES_ROLES.search(title or "") else "hiring")
        if s:
            out.append(s)
    # stärkste zuerst, höchstens 3
    return sorted(out, key=lambda s: (-s["score"], s["age_days"]))[:3]


def _karriere(client: httpx.Client, website: str) -> List[dict]:
    """Karriereseite mit offenen Stellen. Abruf über harvest.fetch (prüft jede Weiterleitung, nur
    öffentliche IPs, SSRF-Schutz). Kein Veröffentlichungsdatum: Abrufdatum, niedrigste Stärke."""
    if not website:
        return []
    from arvantir.harvest import fetch  # später Import, damit signals ohne harvest importierbar bleibt
    p = urlparse(website if "//" in website else f"https://{website}")
    base = f"{p.scheme}://{p.netloc}"
    for path in ("/karriere", "/jobs", "/career", "/careers"):
        html, final = fetch(base + path, TIMEOUT)
        if html and re.search(r"(m/w/d|w/m/d|m/f/d|offene stellen|stellenangebot|wir suchen)", html, re.I):
            s = _sig("hiring", "Karriereseite mit offenen Stellen (Stand Abruf, kein Datum auf der Seite)",
                     final, _today(), "website_change")
            return [s] if s else []
    return []


def _load_feeds(client: httpx.Client) -> List[dict]:
    global _feed_items
    with _feed_lock:
        if _feed_items is not None:
            return _feed_items
        items = []
        for url in FUNDING_FEEDS:
            try:
                r = client.get(url, timeout=TIMEOUT, headers=UA)
                root = ET.fromstring(r.content)
                for it in root.iter("item"):
                    items.append({"title": it.findtext("title", ""), "link": it.findtext("link", ""),
                                  "desc": re.sub(r"<[^>]+>", " ", it.findtext("description", "") or ""),
                                  "date": _parse_date(it.findtext("pubDate", ""))})
            except (httpx.HTTPError, ET.ParseError):
                continue
        _feed_items = items
        return items


def _funding(client: httpx.Client, core: str) -> List[dict]:
    out = []
    for it in _load_feeds(client):
        if _mentions(f'{it["title"]} {it["desc"]}', core):
            kind = "funding" if re.search(r"(finanzierung|investment|series|seed|millionen|mio|funding|kapital)",
                                          f'{it["title"]} {it["desc"]}', re.I) else "news"
            s = _sig(kind, it["title"], it["link"], it["date"], kind)
            if s:
                out.append(s)
    return out[:2]


# ---------- Cache + Bewertung ----------

def _cache_path(c: dict) -> Path:
    key = hashlib.sha1(f'{_fold(c.get("name", ""))}|{c.get("website", "")}'.encode()).hexdigest()[:16]
    return CACHE / f"{key}.json"


def _score(sigs: List[dict]) -> int:
    """Höchstens zwei Signale je Typ zählen, damit zehn Artikel derselben Meldung nicht inflationieren."""
    per_type: Dict[str, List[int]] = {}
    for s in sigs:
        per_type.setdefault(s["type"], []).append(s["score"])
    total = sum(sum(sorted(v, reverse=True)[:2]) for v in per_type.values())
    if len({s["type"] for s in sigs}) >= 2:
        total += 2
    return total


def _one(client: httpx.Client, c: dict) -> dict:
    path = _cache_path(c)
    try:
        if path.exists() and time.time() - path.stat().st_mtime < CACHE_TTL_S:
            return json.loads(path.read_text("utf-8"))
    except (OSError, ValueError):
        pass

    core = _core_name(c.get("name", ""))
    stem = _domain_stem(c.get("website", ""))
    sigs: List[dict] = []
    for fn, args in ((_linkedin, (c, core)), (_news, (c, core)), (_ats, (stem,)),
                     (_karriere, (c.get("website", ""),)), (_funding, (core,))):
        try:
            sigs.extend(fn(client, *args))
        except Exception:  # eine kaputte Quelle stoppt den Lauf nie
            continue
    # Dubletten über die URL entfernen, jüngste zuerst
    seen, uniq = set(), []
    for s in sorted(sigs, key=lambda s: s["age_days"]):
        if s["url"] not in seen:
            seen.add(s["url"])
            uniq.append(s)
    res = {"signals": uniq, "signal_score": _score(uniq),
           "freshest_signal_days": min((s["age_days"] for s in uniq), default=None)}
    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(res, ensure_ascii=False), "utf-8")
    except OSError:
        pass
    return res


def signals(cands: List[dict], niche: str, top: int = 25) -> List[dict]:
    """Hängt frische Signale an die ersten `top` Kandidaten. Fehler je Firma werden geschluckt."""
    head = [c for c in cands[:top] if c.get("name")]
    if not head:
        return cands
    with httpx.Client(headers=UA, follow_redirects=True) as client, ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(lambda c: _safe(client, c), head))
    for c, res in zip(head, results):
        c.update(res)
    return cands


def _safe(client: httpx.Client, c: dict) -> dict:
    try:
        return _one(client, c)
    except Exception:
        return {"signals": [], "signal_score": 0, "freshest_signal_days": None}


if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    load_dotenv()
    demo = json.loads(sys.argv[1]) if len(sys.argv) > 1 else [
        {"name": "Personio GmbH", "website": "https://www.personio.de", "city": "München"}]
    for c in signals(demo, "test", top=len(demo)):
        print(c["name"], c.get("signal_score"), c.get("freshest_signal_days"))
        for s in c.get("signals", []):
            print("   ", s["type"], s["score"], s["date"], s["title"][:90])
