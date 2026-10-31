"""Ganzer Lauf: discover -> harvest -> (normalize, darkcheck, enrich von Malek) -> rank -> Datei.

Maleks Module werden eingehängt, sobald sie existieren (gleiche Funktionsnamen).
Jede Stufe meldet ihre Zahl an `on_step`, das ist der Funnel für UI und Video.
"""
from __future__ import annotations

import csv
import importlib
import json
import re
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

from .common import DATA
from .discover import discover
from .harvest import LEGAL, company_like, harvest, resolve_websites
from .rank import fetch_profiles, rank


def _optional(module: str, func: str) -> Optional[Callable]:
    try:
        return getattr(importlib.import_module(f"arvantir.{module}"), func)
    except (ImportError, AttributeError):
        return None


def icp_for(niche: str) -> str:
    """ICP-Text aus research/icps.json (Terminal d2), passend zur Nische."""
    path = Path(__file__).resolve().parent.parent / "research" / "icps.json"
    if not path.exists():
        return ""
    words = set(re.findall(r"\w{4,}", niche.lower()))
    best, hit = "", 0
    for x in json.loads(path.read_text(encoding="utf-8")):
        n = len(words & set(re.findall(r"\w{4,}", x.get("niche", "").lower())))
        if n > hit:
            best, hit = x.get("icp_text", ""), n
    return best


def collapse_chains(cands: List[Dict], min_branches: int = 3) -> List[Dict]:
    """Eine Firma, eine Zeile: Filialen derselben Domain zusammenfassen und als Kette markieren."""
    from urllib.parse import urlparse

    from .harvest import _reg

    groups: Dict[str, List[Dict]] = {}
    for c in cands:
        dom = _reg(urlparse(c.get("website", "")).netloc) if c.get("website") else ""
        groups.setdefault(dom or f"_{id(c)}", []).append(c)
    out = []
    for key, grp in groups.items():
        head = dict(grp[0])
        if not key.startswith("_") and len(grp) >= min_branches:
            head["kette"] = True
            head["niche_fields"] = {**(head.get("niche_fields") or {}), "filialen": len(grp)}
            head["datenluecken_hinweis"] = "Kette, laut ICP meist ausgeschlossen"
        out.append(head)
    return out


def run(seed: str, icp: str = "", sources: int = 3, per_source: int = 80, top: int = 60,
        on_step: Callable[[str, int, Dict], None] = lambda *a: None) -> Dict:
    t0 = time.time()
    funnel: List[Dict] = []

    def step(name: str, n: int, extra: Optional[Dict] = None) -> None:
        funnel.append({"step": name, "n": n, "t": round(time.time() - t0, 1)})
        on_step(name, n, extra or {})
        print(f"[{time.time() - t0:5.1f}s] {name}: {n}")

    d = discover(seed)
    step("Quellen gefunden", d["candidates_total"], {"sources": d["sources"][:10]})
    cands: List[Dict] = []
    picked: List[Dict] = []
    for s in d["sources"][:10]:  # Quellen nacheinander testen, nur echte Firmenlisten behalten
        if len(picked) >= sources:
            break
        r = harvest(s["url"], d["niche"], max_pages=3, max_items=per_source)
        got = r["candidates"]
        share = sum(1 for c in got if company_like(c)) / len(got) if got else 0
        s["harvested"], s["company_share"] = len(got), round(share, 2)
        strong = sum(1 for c in got if LEGAL.search(c["name"]) or c.get("postcode"))
        if len(got) < 8 or share < 0.3 or strong < 5:  # Website allein reicht nicht (Navigationslinks)
            print(f"[pipeline] verworfen ({len(got)} Einträge, {share:.0%} Firmen): {s['url']}")
            continue
        picked.append(s)
        for c in got:
            c["source_type"] = s["type"]
        cands += got
    step("Firmen ausgelesen", len(cands), {"sources_used": [p["url"] for p in picked]})

    normalize = _optional("normalize", "normalize")
    if normalize:
        cands = normalize(cands)
    step("eindeutige Firmen", len(cands))

    cands = resolve_websites(cands, limit=top)
    cands = collapse_chains(cands)
    step("eine Firma, eine Zeile", len(cands), {"ketten": sum(1 for c in cands if c.get("kette"))})
    # Firmen ohne Website bleiben drin: das ist der dunkelste Teil des TAM (Kanal: Brief an die Adresse)
    step("mit Website", sum(1 for c in cands if c.get("website")))

    darkcheck = _optional("darkcheck", "darkcheck")
    if darkcheck:
        cands = darkcheck(cands)
        step("NICHT in AI Ark", sum(1 for c in cands if c.get("in_ai_ark") is False))

    enrich = _optional("enrich", "enrich")
    if enrich:
        cands = enrich(cands)
        step("mit Entscheider", sum(1 for c in cands if c.get("decision_maker")))

    sig = _optional("signals", "signals")
    if sig:
        cands = sig(cands, d["niche"], top=min(top, 25))
        step("mit frischem Signal", sum(1 for c in cands if c.get("signals")))

    cands = fetch_profiles(cands, limit=top)
    icp = icp or icp_for(d["niche"]) or icp_for(seed) or f"{d['niche']} in Deutschland"
    ranked = rank(cands[:top], icp, d["niche"])
    for r in ranked:  # harter ICP-Filter nach dem Ranking: Ketten nie über Tier C
        if r.get("kette") and r["tier"] in ("A", "B"):
            r["tier"], r["needs_human"] = "C", True
    step("gerankt", len(ranked), {"needs_human": sum(r["needs_human"] for r in ranked)})

    out = {"seed": seed, "niche": d["niche"], "icp": icp, "funnel": funnel,
           "sources": picked, "leads": ranked, "seconds": round(time.time() - t0, 1)}
    stamp = time.strftime("%H%M%S")
    path = DATA / f"run_{stamp}.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    _csv(ranked, DATA / f"run_{stamp}.csv")
    out["file"] = str(path)
    return out


def _csv(rows: List[Dict], path: Path) -> None:
    cols = ["name", "website", "city", "postcode", "score", "tier", "konfidenz", "datenluecken",
            "needs_human", "decision_maker", "in_ai_ark", "signal_score", "freshest_signal_days",
            "reason", "reason_source", "source_url", "source_type"]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows({k: _cell(r.get(k)) for k in cols} for r in rows)


def _cell(v):
    """Formel-Injection in Excel/Sheets/Clay verhindern."""
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + v
    return v
