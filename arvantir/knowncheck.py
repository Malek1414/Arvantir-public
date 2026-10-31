"""knowncheck: steht die Firma schon in einer großen öffentlichen Firmen-Datenbank?

Offline-Ersatz für darkcheck, solange kein AIARK_API_KEY da ist. Quelle ist ein freier
Datensatz von Hugging Face (Data Legion, 28 Mio. Firmen, oder BigPicture, 17 Mio.), aus dem
`build` einen kleinen SQLite-Index macht: alle Domains plus Name+Ort der DACH-Firmen.

    python -m arvantir.knowncheck build data/ext/<datei oder ordner> [name]
    python -m arvantir.knowncheck bench data/run_*.json

Ehrliche Grenze: das ist nicht AI Ark. Die Aussage lautet "nicht in einer Datenbank mit
N Mio. Firmen", nie "nicht in AI Ark". Ohne Index bleibt in_known_db = None.
"""
from __future__ import annotations

import csv
import gzip
import json
import os
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path
from typing import Dict, Iterator, List, Optional

from .common import DATA
from .normalize import domain_of, name_key

INDEX = Path(os.getenv("KNOWN_DB", str(DATA / "ext" / "known.db")))
DACH = {"germany", "de", "deutschland", "austria", "at", "österreich", "switzerland", "ch", "schweiz"}
COLS = {  # erste passende Spalte gewinnt, je Datensatz anders benannt
    "domain": ["domain", "primary_domain", "website", "website_url", "url"],
    "name": ["name", "company_name", "legal_name"],
    "city": ["locality", "city", "hq_city", "location_city"],
    "country": ["country", "country_name", "hq_country", "location_country", "country_code"],
}


CITY_EN = {"munich": "munchen", "cologne": "koln", "vienna": "wien", "nuremberg": "nurnberg",
           "zurich": "zurich", "hanover": "hannover", "brunswick": "braunschweig", "geneva": "genf"}


def _city(s: str) -> str:
    """Ort ohne Umlaut-Varianten: München, Muenchen, Munchen und Munich ergeben denselben Schlüssel."""
    s = unicodedata.normalize("NFKD", re.split(r"[,(/]", s or "")[0].strip().lower()).replace("ß", "ss")
    s = re.sub(r"[^a-z]", "", s.encode("ascii", "ignore").decode())
    s = re.sub(r"([aou])e", r"\1", s)
    return CITY_EN.get(s, s)


def _pick(header: List[str]) -> Dict[str, Optional[str]]:
    low = {h.lower(): h for h in header}
    return {k: next((low[c] for c in cands if c in low), None) for k, cands in COLS.items()}


def _rows(src: Path) -> Iterator[Dict]:
    files = sorted(src.rglob("*.parquet")) if src.is_dir() else [src]
    for f in files:
        if f.suffix == ".parquet":
            import pyarrow.parquet as pq
            pf = pq.ParquetFile(f)
            for batch in pf.iter_batches(batch_size=200_000):
                yield from batch.to_pylist()
        else:
            opener = gzip.open if f.suffix == ".gz" else open
            with opener(f, "rt", encoding="utf-8", errors="replace", newline="") as fh:
                yield from csv.DictReader(fh)


def build(src: Path, label: str = "") -> Dict:
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    tmp = INDEX.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.executescript("CREATE TABLE dom(d TEXT PRIMARY KEY) WITHOUT ROWID;"
                     "CREATE TABLE nm(k TEXT, c TEXT, PRIMARY KEY(k, c)) WITHOUT ROWID;"
                     "CREATE TABLE meta(k TEXT PRIMARY KEY, v TEXT);")
    cols, n, dach, buf_d, buf_n = None, 0, 0, [], []
    for row in _rows(src):
        if cols is None:
            cols = _pick(list(row))
            print(f"[knowncheck] Spalten: {cols}")
        n += 1
        dom = domain_of(str(row.get(cols["domain"]) or "")) if cols["domain"] else ""
        if dom:
            buf_d.append((dom,))
        country = str(row.get(cols["country"]) or "").strip().lower() if cols["country"] else ""
        if country in DACH and cols["name"]:
            dach += 1
            k = name_key(str(row.get(cols["name"]) or ""))
            if len(k) >= 4:
                buf_n.append((k, _city(str(row.get(cols["city"]) or "")) if cols["city"] else ""))
        if len(buf_d) >= 500_000:
            db.executemany("INSERT OR IGNORE INTO dom VALUES (?)", buf_d)
            db.executemany("INSERT OR IGNORE INTO nm VALUES (?, ?)", buf_n)
            buf_d, buf_n = [], []
            print(f"[knowncheck] {n:,} Zeilen")
    db.executemany("INSERT OR IGNORE INTO dom VALUES (?)", buf_d)
    db.executemany("INSERT OR IGNORE INTO nm VALUES (?, ?)", buf_n)
    meta = {"label": label or src.name, "rows": str(n), "dach": str(dach)}
    db.executemany("INSERT INTO meta VALUES (?, ?)", list(meta.items()))
    db.commit()
    db.close()
    tmp.replace(INDEX)
    print(f"[knowncheck] fertig: {n:,} Firmen, davon {dach:,} DACH -> {INDEX}")
    return meta


def _open() -> Optional[sqlite3.Connection]:
    if not INDEX.exists():
        return None
    return sqlite3.connect(f"file:{INDEX}?mode=ro", uri=True)


def meta() -> Dict:
    db = _open()
    if not db:
        return {}
    with db:
        return dict(db.execute("SELECT k, v FROM meta").fetchall())


def lookup(db: sqlite3.Connection, c: Dict) -> Dict:
    """Domain zuerst; ohne Domain Name+Ort (Name allein ist zu unscharf und zählt als unbekannt)."""
    dom = c.get("domain") or domain_of(c.get("website", ""))
    if dom:
        hit = db.execute("SELECT 1 FROM dom WHERE d = ?", (dom,)).fetchone()
        return {"in_known_db": bool(hit), "known_method": "domain"}
    k, city = name_key(c.get("name", "")), _city(c.get("city", ""))
    if len(k) >= 4 and city:
        hit = db.execute("SELECT 1 FROM nm WHERE k = ? AND c = ?", (k, city)).fetchone()
        return {"in_known_db": bool(hit), "known_method": "name+ort"}
    return {"in_known_db": None, "known_method": ""}


def knowncheck(cands: List[Dict]) -> List[Dict]:
    db = _open()
    if not db:
        print(f"[knowncheck] kein Index unter {INDEX}, in_known_db bleibt unbekannt")
        for c in cands:
            c.setdefault("in_known_db", None)
        return cands
    with db:
        for c in cands:
            c.update(lookup(db, c))
    return cands


def bench(paths: List[str]) -> List[Dict]:
    """Bestehende Läufe gegen den Index: je Nische Anteil dunkel, getrennt nach Methode."""
    out = []
    db = _open()
    if not db:
        sys.exit(f"kein Index unter {INDEX}, erst build")
    with db:
        for p in paths:
            run = json.loads(Path(p).read_text(encoding="utf-8"))
            leads = run.get("leads", [])
            r = {"niche": run.get("niche"), "run": Path(p).stem, "leads": len(leads),
                 "domain_checked": 0, "domain_known": 0, "name_checked": 0, "name_known": 0, "unchecked": 0}
            for c in leads:
                res = lookup(db, c)
                if res["known_method"] == "domain":
                    r["domain_checked"] += 1
                    r["domain_known"] += res["in_known_db"]
                elif res["known_method"] == "name+ort":
                    r["name_checked"] += 1
                    r["name_known"] += res["in_known_db"]
                else:
                    r["unchecked"] += 1
            out.append(r)
    return out


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "build" and len(sys.argv) >= 3:
        build(Path(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else "")
    elif cmd == "bench" and len(sys.argv) >= 3:
        print(json.dumps({"index": meta(), "runs": bench(sys.argv[2:])}, ensure_ascii=False, indent=1))
    else:
        sys.exit(__doc__)
