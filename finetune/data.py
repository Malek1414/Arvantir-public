"""Paare fürs Fine-Tuning bauen und laden (eine Wahrheit für teacher, gold, train, bench).

    .venv/bin/python -m finetune.data          # baut data/pairs.jsonl aus data/runs/ + rank_pairs.jsonl

Paar-Herkunft (origin):
- own        Lead aus Nische X gegen ICP von X (Label offen, Lehrer entscheidet)
- cross      Lead aus Nische X gegen ICP von Y (harter Negativ-Kandidat, kostenlos)
- directory  Verzeichnisseite (aus discover) gegen einen ICP (Task A, Negativ)
- source     Suchtreffer gegen "Liste vieler {Nische}-Firmen" (Task B)
Split immer nach company_id, nie nach Paar.
"""
from __future__ import annotations

import hashlib
import json
import random
import re
from pathlib import Path
from typing import Dict, Iterable, List
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RUNS = DATA / "runs"
PAIRS = DATA / "pairs.jsonl"
RAW_PAIRS = DATA / "rank_pairs.jsonl"
SILVER = DATA / "labels_silver.jsonl"
GOLD = DATA / "gold.jsonl"
GOLD_SAMPLE = DATA / "gold_sample.jsonl"
MAIN_NICHES = ["baeckereien_metzgereien", "waschanlagen", "it_dienstleister",
               "aerzte_apotheken", "family_offices", "immobilien_asset_manager"]
CROSS_PER_DOC = 2  # so viele fremde ICPs pro Lead als Negativ-Kandidat


def niches() -> List[Dict]:
    from .collect import load_niches
    return load_niches()


def read_jsonl(path: Path) -> List[Dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            continue  # halb geschriebene Zeile von einem parallelen Lauf
    return out


def write_jsonl(path: Path, rows: Iterable[Dict]) -> int:
    n = 0
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            n += 1
    return n


_SHARED_HOSTS: set = set()  # Hosts, die für viele Firmen stehen (OSM, Verzeichnis), zählen nicht als Firma


def _host(url: str) -> str:
    return urlparse(url if "//" in url else "//" + url).netloc.lower().removeprefix("www.")


def company_id(c: Dict) -> str:
    """Domain ohne www, sonst normalisierter Name. Gleiche Firma = gleiche ID über Nischen."""
    host = _host(c.get("website") or "")
    if host and host not in _SHARED_HOSTS:
        return host
    name = re.sub(r"[^a-z0-9äöüß]+", "", (c.get("name") or c.get("doc", "")[:60]).lower())
    return "n:" + name[:60]


def pid(*parts: str) -> str:
    return hashlib.sha1("\x1f".join(parts).encode()).hexdigest()[:16]


def latest_runs() -> Dict[str, Dict]:
    """Alle Läufe pro Nischen-Key zusammengeführt (Haupt-Seed + Varianten), ICP vom Hauptlauf."""
    best: Dict[str, Dict] = {}
    for p in sorted(RUNS.glob("*.json")):
        try:
            r = json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            continue
        k = r.get("key")
        if not k:
            continue
        if k not in best:
            best[k] = {**r, "leads": list(r.get("leads", []))}
        else:
            best[k]["leads"] += r.get("leads", [])
            if not r.get("variant"):
                best[k]["icp"], best[k]["niche"] = r.get("icp"), r.get("niche")
    return best


def build(seed: int = 7) -> List[Dict]:
    rng = random.Random(seed)
    nl = {n["key"]: n for n in niches()}
    runs = latest_runs()
    names: Dict[str, set] = {}
    for r in runs.values():
        for c in r.get("leads", []):
            names.setdefault(_host(c.get("website") or ""), set()).add((c.get("name") or "").lower())
    _SHARED_HOSTS.clear()
    _SHARED_HOSTS.update(h for h, n in names.items() if h and len(n) > 3)
    rows: List[Dict] = []
    docs_by_niche: Dict[str, List[Dict]] = {}
    for key, r in runs.items():
        icp = r.get("icp") or nl.get(key, {}).get("icp", "")
        seen = set()
        for c in r.get("leads", []):
            doc = (c.get("doc") or "").strip()
            cid = company_id(c)
            if not doc or cid in seen:
                continue
            seen.add(cid)
            item = {"doc": doc, "company_id": cid, "url": c.get("website", ""),
                    "base_score": c.get("score"), "name": c.get("name", "")}
            docs_by_niche.setdefault(key, []).append(item)
            rows.append({"task": "lead", "niche": key, "query": icp, "origin": "own",
                         "doc_niche": key, **item})
    keys = sorted(docs_by_niche)
    for key in keys:  # gleiche Firma, fremder ICP -> harter Negativ-Kandidat
        others = [k for k in keys if k != key]
        for item in docs_by_niche[key]:
            for other in rng.sample(others, min(CROSS_PER_DOC, len(others))):
                icp = runs[other].get("icp") or nl.get(other, {}).get("icp", "")
                rows.append({"task": "lead", "niche": other, "query": icp, "origin": "cross",
                             "doc_niche": key, **item, "base_score": None})

    niche_by_name = {}
    for p in sorted(RUNS.glob("*.json")):  # auch Varianten-Nischennamen der Quellen zuordnen
        try:
            r = json.loads(p.read_text(encoding="utf-8"))
            niche_by_name[r.get("niche", "")] = r["key"]
        except (ValueError, KeyError):
            continue
    for p in read_jsonl(RAW_PAIRS):
        if p.get("task") != "source" or not p.get("doc"):
            continue
        key = niche_by_name.get(p.get("niche", ""))
        if not key:
            continue
        cid = "src:" + (urlparse(p.get("url", "")).netloc.lower().removeprefix("www.") or p["doc"][:40])
        base = {"doc": p["doc"][:2000], "company_id": cid, "url": p.get("url", ""), "name": ""}
        rows.append({"task": "source", "niche": key, "query": p["query"], "origin": "source",
                     "doc_niche": key, **base, "base_score": p.get("score")})
        if key in runs and rng.random() < 0.5:  # Verzeichnisseite als Lead ist immer falsch
            rows.append({"task": "lead", "niche": key, "query": runs[key].get("icp", ""),
                         "origin": "directory", "doc_niche": key, **base, "base_score": None})

    uniq: Dict[str, Dict] = {}
    for r in rows:
        if not r["query"]:
            continue
        r["pair_id"] = pid(r["task"], r["query"], r["doc"])
        uniq.setdefault(r["pair_id"], r)
    return list(uniq.values())


def labels(path: Path = SILVER) -> Dict[str, Dict]:
    """pair_id -> letzte Label-Zeile (0..3)."""
    return {r["pair_id"]: r for r in read_jsonl(path) if "label" in r}


def gold_labels() -> Dict[str, Dict]:
    """Gold auf derselben 0..3-Skala: passt=3, vielleicht=1, nein=0."""
    m = {"passt": 3, "vielleicht": 1, "nein": 0}
    out: Dict[str, Dict] = {}
    for r in read_jsonl(GOLD):  # Reihenfolge zählt: späterer Klick oder "zurück" (gold=None) gewinnt
        if r.get("gold") in m:
            out[r["pair_id"]] = {**r, "label": m[r["gold"]]}
        elif r.get("gold") is None:
            out.pop(r.get("pair_id"), None)
    return out


def main() -> None:
    rows = build()
    n = write_jsonl(PAIRS, rows)
    by = {}
    for r in rows:
        by[(r["task"], r["origin"])] = by.get((r["task"], r["origin"]), 0) + 1
    print(f"{n} Paare -> {PAIRS}")
    for k, v in sorted(by.items()):
        print(f"  {k[0]:<6} {k[1]:<9} {v}")
    print("Nischen:", sorted({r['niche'] for r in rows}))


if __name__ == "__main__":
    main()
