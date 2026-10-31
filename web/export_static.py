"""Statische, öffentliche Fassung der Website bauen (nur Replay, keine Live-Läufe).

Aufruf:  .venv/bin/python -m web.export_static <zielordner>
Personendaten: nur eine Whitelist an Feldern geht raus, Entscheider nur mit Initialen und Rolle,
keine E-Mails, Telefonnummern, Faxnummern, Straßen.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

from web import server

WEB = Path(__file__).resolve().parent
# saubere Läufe mit Maleks Modulen (laut Orchestrator), Video-Standard zuerst
RUNS = ["run_145130.json", "run_143435.json", "run_142923.json", "run_142828.json", "run_143910.json", "run_144623.json"]
KEEP = {"name", "website", "city", "postcode", "score", "tier", "konfidenz", "confidence", "datenluecken",
        "reason", "reason_source", "source_url", "source_type", "signal_score", "freshest_signal_days",
        "kanal", "in_ai_ark", "needs_human", "ausland", "legal_form"}
TITLES = {"dr.", "prof.", "herr", "frau", "dipl.-ing.", "dipl.", "ing."}


def _mask(dm):
    """'Dennis Jeske (Geschäftsführung)' -> 'D. J. (Geschäftsführung)'."""
    if not dm:
        return None
    text = dm if isinstance(dm, str) else str(dm.get("name", ""))
    m = re.match(r"\s*([^()]+?)\s*(\(([^)]*)\))?\s*$", text)
    name, role = (m.group(1), m.group(3)) if m else (text, None)
    parts = [w for w in name.split() if w.lower() not in TITLES]
    initials = " ".join(w[0].upper() + "." for w in parts if w[:1].isalpha())
    return f"{initials} ({role})" if role else initials or None


EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
PHONE = re.compile(r"(\+|\b0)[\d\s()/.-]{7,}\d")
STREET = re.compile(r"\b[A-ZÄÖÜ][\wäöüß.-]*(straße|strasse|str\.|weg|platz|allee|ring|damm|gasse)\s*\d+\w?", re.I)


def _names(l):
    """Vollständige Namen der Entscheider, damit sie auch aus Freitext verschwinden."""
    raw = [l.get("decision_maker")] + list(l.get("decision_makers") or [])
    out = set()
    for d in raw:
        text = d if isinstance(d, str) else (d or {}).get("name", "") if isinstance(d, dict) else ""
        name = re.sub(r"\(.*?\)", "", text or "")
        for w in name.split():
            if len(w) > 2 and w.lower() not in TITLES:
                out.add(w.strip(",."))
    return out


def _scrub(text, names):
    if not text:
        return text
    text = EMAIL.sub("[E-Mail]", text)
    text = PHONE.sub("[Telefon]", text)
    text = STREET.sub("[Adresse]", text)
    for n in names:
        text = re.sub(rf"\b{re.escape(n)}\b", "…", text)
    return text


def _signals(sigs, names):
    return [{**{k: s.get(k) for k in ("type", "url", "date", "age_days")}, "title": _scrub(s.get("title"), names)}
            for s in (sigs or [])]


def _lead(l):
    names = _names(l)
    out = {k: l.get(k) for k in KEEP if k in l}
    out["decision_maker"] = _mask(l.get("decision_maker"))
    # Begründung aus dem Impressum nicht veröffentlichen, sonst Freitext säubern
    src = str(l.get("reason_source") or "").lower()
    out["reason"] = None if "impressum" in src or "imprint" in src else _scrub(l.get("reason"), names)
    out["signals"] = _signals(l.get("signals"), names)
    return out


def build(dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    (dst / "runs").mkdir(parents=True)
    flag = "<script>window.ARVANTIR_STATIC = true;</script>\n<script>"
    page = (WEB / "index.html").read_text(encoding="utf-8").replace("<script>", flag, 1)
    (dst / "index.html").write_text(page, encoding="utf-8")
    shutil.copy(WEB / "arch-anim.js", dst / "arch-anim.js")
    for name in ("architecture", "logo"):
        (dst / name).mkdir()
        shutil.copy(WEB / f"{name}.html", dst / name / "index.html")
    listing = []
    for f in RUNS:
        p = server.DATA / f
        if not p.exists():
            continue
        d = server._slim(json.loads(p.read_text(encoding="utf-8")))
        d["leads"] = [_lead(l) for l in d["leads"]]
        (dst / "runs" / f).write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        listing.append({"file": f, "seed": d["seed"], "leads": len(d["leads"]), "seconds": d["seconds"],
                        "steps": len(d["funnel"])})
    (dst / "runs.json").write_text(json.dumps(listing, ensure_ascii=False), encoding="utf-8")
    server._status_cache["data"] = None
    (dst / "status.json").write_text(json.dumps(server.status(), ensure_ascii=False), encoding="utf-8")
    (dst / "bench.json").write_text(server.bench().body.decode("utf-8"), encoding="utf-8")
    print(f"{len(listing)} Läufe nach {dst}")


if __name__ == "__main__":
    build(Path(sys.argv[1]).resolve())
