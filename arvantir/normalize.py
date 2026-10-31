"""normalize: rohe Kandidaten -> eine Firma = eine Zeile, jede Quelle bleibt sichtbar.

Schlüssel (Entity-Key): Handelsregister (Gericht + HRB) > registrierbare Domain > Name + PLZ > Name.
Rechtsform wird abgetrennt, der Name für den Abgleich gefaltet (Groß/klein, Umlaute, Satzzeichen),
so dass "Hafenblick Group GmbH", "Hafenblick Group" und "hafenblick group" eine Zeile werden.
"""
from __future__ import annotations

import re
from typing import Dict, List
from urllib.parse import urlparse

LEGAL_FORMS = [  # längste zuerst
    r"GmbH\s*&\s*Co\.?\s*KGaA", r"GmbH\s*&\s*Co\.?\s*KG", r"AG\s*&\s*Co\.?\s*KG",
    r"UG\s*\(haftungsbeschränkt\)(?:\s*&\s*Co\.?\s*KG)?", r"gGmbH", r"GmbH", r"mbH", r"KGaA",
    r"AG", r"SE", r"KG", r"OHG", r"GbR", r"PartG(?:\s*mbB)?", r"e\.\s?K(?:fm|fr)?\.", r"e\.\s?V\.",
    r"eG", r"UG", r"Ltd\.?", r"Inc\.?", r"S\.?A\.?R\.?L\.?", r"Sàrl", r"Sagl",
]
LEGAL_RE = re.compile(r"[\s,]+(" + "|".join(LEGAL_FORMS) + r")\s*$", re.I)
TWO_LEVEL = {"co.uk", "com.au", "co.at", "or.at", "ac.at", "com.tr", "co.nz"}
FOLD = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", "é": "e", "è": "e", "à": "a"})
STOP = {"und", "the", "der", "die", "das", "von", "fuer", "group", "gruppe", "holding",
        "deutschland", "germany", "inh", "inhaber"}


def split_legal(name: str) -> tuple:
    name = re.sub(r"\s+", " ", (name or "").strip().strip("\"'„“”·|-–—,;:"))
    m = LEGAL_RE.search(name)
    if m:
        return name[: m.start()].strip(" ,-"), re.sub(r"\s+", " ", m.group(1))
    return name, ""


def name_key(name: str) -> str:
    base, _ = split_legal(name)
    s = base.lower().translate(FOLD)
    words = [w for w in re.findall(r"[a-z0-9]+", s) if w not in STOP]
    return "".join(words) or re.sub(r"[^a-z0-9]", "", s)


def domain_of(url: str) -> str:
    if not url:
        return ""
    if "://" not in url:
        url = "http://" + url
    host = (urlparse(url).hostname or "").lower().strip(".")
    if host.startswith("www."):
        host = host[4:]
    parts = host.split(".")
    if len(parts) >= 3 and ".".join(parts[-2:]) in TWO_LEVEL:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def entity_key(c: Dict) -> str:
    if c.get("hrb") and c.get("register_court"):
        return f"hr:{c['register_court'].lower()}:{re.sub(r'[^0-9a-z]', '', c['hrb'].lower())}"
    if c.get("domain"):
        return f"dom:{c['domain']}"
    nk = name_key(c.get("name", ""))
    return f"nm:{nk}:{c.get('postcode', '')}" if c.get("postcode") else f"nm:{nk}"


def clean(c: Dict) -> Dict:
    c = dict(c)
    base, form = split_legal(c.get("name", ""))
    c["name_raw"] = c.get("name", "")
    c["name_clean"] = base
    if form and not c.get("legal_form"):
        c["legal_form"] = form
    c["domain"] = c.get("domain") or domain_of(c.get("website", ""))
    if c.get("postcode"):
        c["postcode"] = re.sub(r"\D", "", str(c["postcode"]))[:5]
    if c.get("city"):
        c["city"] = re.sub(r"\s+", " ", c["city"]).strip(" ,")
    return c


def merge(a: Dict, b: Dict) -> Dict:
    """b in a mischen: leere Felder füllen, Quellen und Namensvarianten sammeln."""
    for k, v in b.items():
        if k in ("sources", "aliases"):
            continue
        if v not in (None, "", [], {}) and a.get(k) in (None, "", [], {}):
            a[k] = v
    a["sources"] = list(dict.fromkeys(a.get("sources", []) + b.get("sources", [])))
    a["aliases"] = list(dict.fromkeys(a.get("aliases", []) + b.get("aliases", [])))
    a["source_count"] = len(a["sources"])
    return a


def normalize(cands: List[Dict]) -> List[Dict]:
    """Saubere, deduplizierte Kandidaten; Reihenfolge = erstes Auftreten."""
    out: Dict[str, Dict] = {}
    by_name: Dict[str, str] = {}
    for raw in cands:
        c = clean(raw)
        c.setdefault("sources", [s for s in [raw.get("source_url")] if s])
        c.setdefault("aliases", [c["name_raw"]] if c.get("name_raw") else [])
        key = entity_key(c)
        nk = name_key(c.get("name", ""))
        if key not in out and nk and nk in by_name and (
                not c.get("domain") or by_name[nk].startswith("nm:")):
            key = by_name[nk]  # gleicher Name, eine Seite ohne Domain: dieselbe Firma
        if key in out:
            merge(out[key], c)
        else:
            c["entity_key"] = key
            c["source_count"] = len(c["sources"])
            out[key] = c
            if nk:
                by_name.setdefault(nk, key)
    rows = list(out.values())
    print(f"[normalize] {len(cands)} -> {len(rows)} Firmen")
    return rows
