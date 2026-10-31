"""darkcheck: kennt AI Ark die Firma? Nur Firmen mit in_ai_ark = False zählen (Folie 01).

AI Ark Company Search, Suche per Domain mit size=1:
    POST https://api.ai-ark.com/api/developer-portal/v1/companies, Header X-TOKEN
    Treffer kostet 0,1 Credit, kein Treffer kostet nichts. Dunkel = totalElements == 0.
Ohne Domain bleibt in_ai_ark = None ("unbekannt"), das kostet nie Credits.
Budget-Schutz: AIARK_MAX_CREDITS (Standard 30 von den 100 Gratis-Credits pro Lauf).
Ergebnisse werden in data/aiark_cache.json gespeichert, jede Domain wird nur einmal bezahlt.
"""
from __future__ import annotations

import json
import os
import time
from typing import Dict, List, Optional

import httpx

from .common import DATA
from .normalize import domain_of

URL = "https://api.ai-ark.com/api/developer-portal/v1/companies"
CACHE = DATA / "aiark_cache.json"
COST_PER_HIT = 0.1


def _load() -> Dict:
    try:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _lookup(client: httpx.Client, domain: str) -> Optional[Dict]:
    body = {"page": 0, "size": 1, "account": {"domain": {"any": {"include": [domain]}}}}
    for attempt in range(3):
        r = client.post(URL, json=body)
        if r.status_code == 429:
            time.sleep(1.0 + attempt)
            continue
        if r.status_code >= 400:
            print(f"[darkcheck] HTTP {r.status_code} für {domain}: {r.text[:120]}")
            return None
        d = r.json()
        content = d.get("content") or []
        return {"total": d.get("totalElements", len(content)),
                "id": content[0].get("id") if content else None, "ts": time.time()}
    return None


def darkcheck(cands: List[Dict]) -> List[Dict]:
    key = os.getenv("AIARK_API_KEY", "")
    if not key:
        print("[darkcheck] kein AIARK_API_KEY, in_ai_ark bleibt unbekannt")
        for c in cands:
            c.setdefault("in_ai_ark", None)
        return cands
    budget = float(os.getenv("AIARK_MAX_CREDITS", "30"))
    spent, asked, cache = 0.0, 0, _load()
    headers = {"X-TOKEN": key, "Content-Type": "application/json"}
    with httpx.Client(headers=headers, timeout=20) as client:
        for c in cands:
            dom = c.get("domain") or domain_of(c.get("website", ""))
            if not dom:
                c["in_ai_ark"] = None
                continue
            hit = cache.get(dom)
            if hit is None:
                if spent + COST_PER_HIT > budget:
                    c["in_ai_ark"] = None
                    c.setdefault("datenluecken", []).append("ai_ark_budget")
                    continue
                time.sleep(0.25)  # unter 5 Anfragen pro Sekunde bleiben
                hit = _lookup(client, dom)
                asked += 1
                if hit is None:
                    c["in_ai_ark"] = None
                    continue
                cache[dom] = hit
                spent += COST_PER_HIT if hit["total"] else 0.0
            c["in_ai_ark"] = bool(hit["total"])
            c["ai_ark_id"] = hit.get("id")
    CACHE.write_text(json.dumps(cache, indent=1), encoding="utf-8")
    dark = sum(1 for c in cands if c.get("in_ai_ark") is False)
    known = sum(1 for c in cands if c.get("in_ai_ark") is True)
    print(f"[darkcheck] {asked} Anfragen, ~{spent:.1f} Credits; dunkel {dark}, bekannt {known}, "
          f"unbekannt {len(cands) - dark - known}")
    return cands
