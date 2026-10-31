"""enrich: Entscheider und Kontakt ohne Lead-Datenbank, jedes Feld mit Quelle und Konfidenz.

Reihenfolge (gratis zuerst): eigene Website + Impressum (httpx -> echter Chrome als Rückfall
-> LLM nur wenn ein Key da ist). Konfidenz nach Arvanas icp-scorer: belegt / wahrscheinlich /
unbekannt; was fehlt, landet in `datenluecken`. Danach Dedupe über den HRB-Schlüssel.
Bezahlte Stufen (Blitz, Lusha) hängen später nur an den Top-Leads.
"""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List

from ..channel import channel
from ..normalize import entity_key, merge, name_key
from . import impressum

KONF = {"http": "belegt", "realbrowser": "belegt", "llm": "wahrscheinlich"}


def _pick_email(emails: List[str], people: List[Dict]) -> tuple:
    last = {p["name"].split()[-1].lower() for p in people}
    first = {p["name"].split()[0].lower() for p in people}
    for e in emails:
        local = e.split("@")[0]
        if any(x and x in local for x in last | first):
            return e, "persönlich"
    for e in emails:
        if not impressum.GENERIC.match(e):
            return e, "persönlich?"
    return (emails[0], "generisch") if emails else ("", "")


def enrich_one(c: Dict) -> Dict:
    if not c.get("website"):
        c.setdefault("datenluecken", []).append("website")
        return c
    fields, url, via = impressum.get(c["website"])
    prov, konf = c.setdefault("provenienz", {}), KONF.get(via, "wahrscheinlich")
    people = fields.get("decision_makers", [])
    if people:
        c["decision_makers"] = people
        c["decision_maker"] = f"{people[0]['name']} ({people[0]['role']})"
        prov["decision_maker"] = {"quelle": url, "konfidenz": konf, "weg": via}
    email, kind = _pick_email(fields.get("emails", []), people)
    if email:
        c["email"], c["email_typ"] = email, kind
        prov["email"] = {"quelle": url, "konfidenz": konf if kind != "persönlich?" else "wahrscheinlich"}
    for f in ("phone", "fax", "hrb", "register_court", "vat_id", "street", "postcode", "city"):
        if fields.get(f) and not c.get(f):
            c[f] = fields[f]
            prov[f] = {"quelle": url, "konfidenz": konf}
    c["impressum_url"], c["enrich_weg"] = url, via
    gaps = c.setdefault("datenluecken", [])
    gaps += [f for f in ("decision_maker", "email", "hrb") if not c.get(f) and f not in gaps]
    c["konfidenz"] = "belegt" if c.get("decision_maker") and konf == "belegt" else \
        "wahrscheinlich" if c.get("decision_maker") else "unbekannt"
    c.update(channel(c))
    return c


def enrich(cands: List[Dict]) -> List[Dict]:
    limit = int(os.getenv("ENRICH_LIMIT", "60"))
    order = sorted(range(len(cands)), key=lambda i: (cands[i].get("in_ai_ark") is True, i))
    todo = [cands[i] for i in order if cands[i].get("website")][:limit]
    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(enrich_one, todo))
    # zweiter Dedupe-Durchgang: jetzt kennen wir HRB-Nummern
    out: Dict[str, Dict] = {}
    for c in cands:
        k = entity_key(c) if c.get("hrb") and c.get("register_court") else c.get("entity_key") or name_key(c.get("name", ""))
        c["entity_key"] = k
        if k in out:
            merge(out[k], c)
        else:
            out[k] = c
    rows = list(out.values())
    dm = sum(1 for c in rows if c.get("decision_maker"))
    print(f"[enrich] {len(todo)} Websites gelesen, {dm} mit Entscheider, "
          f"{sum(1 for c in rows if c.get('enrich_weg') == 'realbrowser')} über echten Chrome")
    return rows
