"""Arvantir-Lauf -> Clay-Table (CSV, JSON oder Webhook).

    python -m adapters.clay data/run_130450.json                    # Arvana-Format, CSV + JSON
    python -m adapters.clay --latest --min-tier B \
        --sperrliste sperrliste.txt --bekannt leads_export.csv     # nur A/B, gesperrt + bekannt markiert
    python -m adapters.clay --latest --format clay                  # Clay-Standardnamen (Company Name ...)
    python -m adapters.clay --latest --webhook                      # Zeile für Zeile an CLAY_WEBHOOK_URL

Zwei Spaltensätze:
- arvana (Standard): die ersten 8 Spalten sind exakt Arvanas leads_export.csv
  (vorname, nachname, email, position, firma, domain, quelle, erfasst_am),
  dahinter die Arvantir-Spalten in ihren Begriffen (tier, datenluecken,
  konfidenz belegt/wahrscheinlich/unbekannt, gesperrt, kanal). Upload ohne Mapping.
- clay: Clays Standard-Eingaben (Company Name, Company Domain, Full Name,
  Work Email ...), damit Clays eigene Enrichments die Spalten sofort erkennen.
Score, Tier und Datenlücken in beiden Fällen wie im icp-scorer-Skill.

Nur Standardbibliothek. Liest Felder, die Maleks normalize/darkcheck/enrich
später liefern (in_ai_ark, decision_maker, register_*, email ...), falls da.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
import unicodedata
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

DATA = Path(__file__).resolve().parent.parent / "data"
RUN_FILE = re.compile(r"^run_\d+(_\d+)?\.json$")  # nur Pipeline-Läufe, nicht unsere _arvana/_clay-Exporte

# Tiers wie im icp-scorer von claude-gtm-skills
TIERS = [(80, "A"), (60, "B"), (40, "C"), (0, "D")]

COLUMNS = [
    # Firma, Clay-Standardnamen
    "Company Name", "Company Domain", "Website", "Legal Form",
    "Street", "Postal Code", "City", "Country",
    "Register Court", "Register Number", "VAT ID",
    "Company Phone", "Company Email", "Company Fax",
    # Entscheider
    "Full Name", "First Name", "Last Name", "Job Title",
    "Work Email", "Email Confidence", "LinkedIn Profile",
    # Bewertung (icp-scorer-Form)
    "ICP Score", "ICP Tier", "ICP Reason", "ICP Reason Source",
    "Confidence", "Needs Human Review", "Data Gaps",
    # Dark TAM
    "In AI Ark", "Dark TAM", "Source Count", "Source List", "Source Type",
    "Best Channel", "Draft",
    # Herkunft
    "Arvantir Entity Key", "Entity Key Kind", "Arvantir Niche", "Arvantir Run", "Found At",
]

ARVANA_COLUMNS = [
    # identisch mit Arvanas leads_export.csv
    "vorname", "nachname", "email", "position", "firma", "domain", "quelle", "erfasst_am",
    # Arvantir
    "quelle_url", "firmen_key", "icp_score", "tier", "datenluecken", "konfidenz",
    "begruendung", "begruendung_quelle", "mensch_prueft", "in_ai_ark", "gesperrt",
    "bekannt", "kanal", "website", "telefon", "plz", "ort", "nische", "lauf",
]

# Ranking-Sicherheit / Feld-Konfidenz -> Arvanas drei Stufen (technographic-qualifier)
KONFIDENZ = {"hoch": "belegt", "mittel": "wahrscheinlich", "niedrig": "unbekannt"}


def norm_domain(raw: str) -> str:
    """Wie Arvanas Sperrliste gemeint ist: Groß/klein, www., Leerzeichen, URL egal."""
    raw = (raw or "").strip().lower()
    return domain(raw) if raw else ""


def load_domains(path: Optional[str], column: str = "domain") -> set:
    """Sperrliste (eine Domain pro Zeile, # = Kommentar) oder CSV mit Spalte domain."""
    if not path:
        return set()
    text = Path(path).read_text(encoding="utf-8")
    if path.endswith(".csv"):
        return {norm_domain(r.get(column, "")) for r in csv.DictReader(text.splitlines())} - {""}
    return {norm_domain(l) for l in text.splitlines() if l.strip() and not l.lstrip().startswith("#")}


def _quelle(c: Dict) -> str:
    """Konkrete Fundstelle statt 'listenkauf': z. B. verband:eco.de."""
    typ = fold(c.get("source_type") or "verzeichnis").split(" ")[0] or "verzeichnis"
    return f"{typ}:{domain(c.get('source_url', ''))}" if c.get("source_url") else typ


# Felder, deren Fehlen als Datenlücke zählt (Reihenfolge = Waterfall-Priorität)
# Kurze Schlüssel, damit Clay danach filtern kann; Nachkauf-Weg steht in adapters/README.md
GAP_FIELDS = [
    ("decision_maker", "entscheider"),
    ("email", "email"),
    ("phone", "telefon"),
    ("postcode", "plz"),
    ("register_number", "hrb"),
    ("in_ai_ark", "ai_ark"),
]

LEGAL_FORMS = [
    "GmbH & Co. KG", "UG (haftungsbeschränkt)", "gGmbH", "GmbH", "AG", "KGaA", "KG",
    "OHG", "GbR", "e.K.", "e.V.", "eG", "SE", "PartG mbB", "PartG", "mbH",
]


def tier(score: Optional[float]) -> str:
    if score is None:
        return ""
    return next(t for lim, t in TIERS if float(score) >= lim)


def domain(url: str) -> str:
    """Registrierbare Domain ohne www (einfach, ohne tldextract; .co.uk-Fälle egal für DACH)."""
    if not url:
        return ""
    host = urlparse(url if "//" in url else "//" + url).netloc.lower().split(":")[0]
    host = host[4:] if host.startswith("www.") else host
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def split_legal(name: str) -> tuple:
    for lf in LEGAL_FORMS:
        m = re.search(r"\s+" + re.escape(lf) + r"\.?\s*$", name or "", re.I)
        if m:
            return name[: m.start()].strip(" ,"), lf
    return (name or "").strip(), ""


def fold(s: str) -> str:
    s = (s or "").lower().replace("ß", "ss").replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def entity_key(c: Dict) -> tuple:
    """Stabiler Schlüssel: Gericht+HRB > Domain > (gefalteter Name, PLZ). Wie in supabase.sql."""
    court, hrb = c.get("register_court") or "", c.get("register_number") or ""
    if court and hrb:
        hrb_clean = re.sub(r"\s+", "", hrb.upper())
        return f"reg:{fold(court)}|{hrb_clean}", "register"
    d = c.get("domain") or domain(c.get("website", ""))
    if d:
        return f"dom:{d}", "domain"
    base, _ = split_legal(c.get("name", ""))
    return f"name:{fold(base)}|{c.get('postcode') or ''}", "name_plz"


def _person(c: Dict) -> Dict:
    dm = c.get("decision_maker")
    if isinstance(dm, dict):
        full = dm.get("name") or dm.get("full_name") or ""
        p = {"full": full, "title": dm.get("role") or dm.get("title") or "",
             "email": dm.get("email") or "", "linkedin": dm.get("linkedin") or "",
             "email_conf": dm.get("email_confidence") or ""}
    else:
        p = {"full": dm or "", "title": c.get("decision_maker_role", ""), "email": "",
             "linkedin": "", "email_conf": ""}
    p["email"] = p["email"] or c.get("personal_email", "")
    bits = p["full"].split()
    p["first"], p["last"] = (bits[0], " ".join(bits[1:])) if len(bits) > 1 else ("", "")
    return p


def gaps(c: Dict) -> List[str]:
    out = []
    for key, label in GAP_FIELDS:
        v = c.get(key)
        if key == "email":
            v = v or _person(c)["email"]
        if v in (None, "", [], {}):
            out.append(label)
    return out


def _yes(v) -> str:
    if v in (True, "True", "true", 1):
        return "yes"
    if v in (False, "False", "false", 0):
        return "no"
    return ""


def to_row(c: Dict, niche: str = "", run: str = "") -> Dict:
    name = c.get("name", "")
    _, lf = split_legal(name)
    key, kind = entity_key(c)
    p = _person(c)
    score = c.get("score")
    score = int(float(score)) if score not in (None, "") else None
    ark = c.get("in_ai_ark")
    srcs = c.get("sources") or ([c["source_url"]] if c.get("source_url") else [])
    return {
        "Company Name": name,
        "Company Domain": c.get("domain") or domain(c.get("website", "")),
        "Website": c.get("website", ""),
        "Legal Form": c.get("legal_form") or lf,
        "Street": c.get("street", ""),
        "Postal Code": c.get("postcode", ""),
        "City": c.get("city", ""),
        "Country": c.get("country", ""),
        "Register Court": c.get("register_court", ""),
        "Register Number": c.get("register_number", ""),
        "VAT ID": c.get("vat_id", ""),
        "Company Phone": c.get("phone", ""),
        "Company Email": c.get("email", ""),
        "Company Fax": c.get("fax", ""),
        "Full Name": p["full"], "First Name": p["first"], "Last Name": p["last"],
        "Job Title": p["title"], "Work Email": p["email"],
        "Email Confidence": p["email_conf"], "LinkedIn Profile": p["linkedin"],
        "ICP Score": score if score is not None else "",
        "ICP Tier": tier(score),
        "ICP Reason": c.get("reason", ""),
        "ICP Reason Source": c.get("reason_source", ""),
        "Confidence": c.get("confidence", ""),
        "Needs Human Review": _yes(c.get("needs_human")),
        "Data Gaps": "; ".join(gaps(c)),
        "In AI Ark": _yes(ark),
        "Dark TAM": "yes" if ark in (False, "False", "false") else "",
        "Source Count": c.get("source_count") or len(srcs),
        "Source List": " | ".join(srcs),
        "Source Type": c.get("source_type", ""),
        "Best Channel": c.get("channel", ""),
        "Draft": c.get("draft", ""),
        "Arvantir Entity Key": key,
        "Entity Key Kind": kind,
        "Arvantir Niche": niche,
        "Arvantir Run": run,
        "Found At": c.get("ts") or time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def to_arvana(row: Dict, c: Dict, gesperrt: set, bekannt: set) -> Dict:
    """Clay-Zeile + Lead -> Arvanas Spalten. Datum nur als Tag, wie in ihrem Export."""
    dom = row["Company Domain"]
    conf = c.get("website_confidence") if not row["Full Name"] else (
        (c.get("decision_maker") or {}).get("confidence") if isinstance(c.get("decision_maker"), dict) else None)
    return {
        "vorname": row["First Name"], "nachname": row["Last Name"], "email": row["Work Email"],
        "position": row["Job Title"], "firma": row["Company Name"], "domain": dom,
        "quelle": _quelle(c), "erfasst_am": row["Found At"][:10],
        "quelle_url": c.get("detail_url") or c.get("source_url", ""),
        "firmen_key": row["Arvantir Entity Key"],
        "icp_score": row["ICP Score"], "tier": row["ICP Tier"],
        "datenluecken": row["Data Gaps"],
        "konfidenz": KONFIDENZ.get(str(conf or "").lower(), "unbekannt"),
        "begruendung": row["ICP Reason"], "begruendung_quelle": row["ICP Reason Source"],
        "mensch_prueft": "ja" if row["Needs Human Review"] == "yes" else "nein",
        "in_ai_ark": {"yes": "ja", "no": "nein"}.get(row["In AI Ark"], "unbekannt"),
        "gesperrt": "ja" if dom and norm_domain(dom) in gesperrt else "nein",
        "bekannt": "ja" if dom and norm_domain(dom) in bekannt else "nein",
        "kanal": row["Best Channel"], "website": row["Website"], "telefon": row["Company Phone"],
        "plz": row["Postal Code"], "ort": row["City"],
        "nische": row["Arvantir Niche"], "lauf": row["Arvantir Run"],
    }


PHONE = re.compile(r"^[+-][\d\s()/.-]+$")


def safe(v):
    """Formel-Injection in Clay/Sheets/Excel verhindern (wie pipeline._cell).
    Telefonnummern wie +49 30 ... bleiben unverändert, sonst bricht Clays Phone-Enrichment."""
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r") and not PHONE.match(v):
        return "'" + v
    return v


def run_id(path: Path) -> str:
    """Pipeline-Stempel hat nur die Uhrzeit, Datum aus der Datei davor: 20261031_run_130450."""
    return time.strftime("%Y%m%d", time.localtime(path.stat().st_mtime)) + "_" + path.stem


def tier_ok(t: str, min_tier: str) -> bool:
    return bool(t) and t in "ABCD"[: "ABCD".index(min_tier.upper()) + 1]


def write_csv(rows: List[Dict], path: Path, columns: List[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        w.writerows({k: safe(r.get(k, "")) for k in columns} for r in rows)


def post_webhook(rows: List[Dict], url: str, token: str = "") -> int:
    """Clay-Webhook-Quelle: eine Zeile pro POST. Token nur aus der Umgebung."""
    if urlparse(url).scheme != "https":
        raise SystemExit("CLAY_WEBHOOK_URL muss https sein")
    sent = 0
    for r in rows:
        req = urllib.request.Request(url, data=json.dumps(r, ensure_ascii=False).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        if token:
            req.add_header("x-clay-webhook-auth", token)
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                sent += 200 <= resp.status < 300
        except Exception as e:  # noqa: BLE001 - eine kaputte Zeile stoppt nicht den Rest
            print(f"[clay] Zeile übersprungen ({(r.get('firma') or r.get('Company Name') or '')[:40]}): {type(e).__name__}")
        time.sleep(0.1)  # Clay drosselt Webhooks
    return sent


def latest_run() -> Path:
    runs = sorted((p for p in DATA.glob("run_*.json") if RUN_FILE.match(p.name)),
                  key=lambda p: p.stat().st_mtime)
    if not runs:
        raise SystemExit("kein Lauf in data/, erst: python -m arvantir run \"<Nische>\" \"<ICP>\"")
    return runs[-1]


def tier_summary(rows: List[Dict]) -> str:
    n = len(rows) or 1
    parts = [f"{t}: {sum(r['ICP Tier'] == t for r in rows)}" for t in "ABCD"]
    human = sum(r["Needs Human Review"] == "yes" for r in rows)
    dark = sum(r["Dark TAM"] == "yes" for r in rows)
    gap_count: Dict[str, int] = {}
    for r in rows:
        for g in filter(None, r["Data Gaps"].split("; ")):
            gap_count[g] = gap_count.get(g, 0) + 1
    top_gaps = ", ".join(f"{g} ({c})" for g, c in sorted(gap_count.items(), key=lambda x: -x[1])[:3])
    return (f"Tiers {' | '.join(parts)} · Mensch prüft: {human} · Dark TAM: {dark}/{len(rows)}"
            f" ({100 * dark // n} %)\nhäufigste Lücken: {top_gaps or '-'}")


def main(argv: Optional[List[str]] = None) -> None:
    ap = argparse.ArgumentParser(description="Arvantir-Lauf als Clay-Table")
    ap.add_argument("run", nargs="?", help="data/run_*.json")
    ap.add_argument("--latest", action="store_true", help="neuesten Lauf in data/ nehmen")
    ap.add_argument("--min-tier", default="D", choices=list("ABCDabcd"))
    ap.add_argument("--out", help="Zielpfad ohne Endung (Standard: neben dem Lauf, _clay)")
    ap.add_argument("--format", default="arvana", choices=["arvana", "clay"])
    ap.add_argument("--sperrliste", help="Domains, die nie angeschrieben werden (sperrliste.txt)")
    ap.add_argument("--bekannt", help="bestehende Liste (leads_export.csv), markiert schon bekannte Firmen")
    ap.add_argument("--webhook", action="store_true", help="an CLAY_WEBHOOK_URL senden (ohne Gesperrte)")
    a = ap.parse_args(argv)
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    path = Path(a.run) if a.run else latest_run() if a.latest else None
    if not path:
        ap.error("Lauf-Datei angeben oder --latest")
    run = json.loads(path.read_text(encoding="utf-8"))
    leads = run.get("leads", [])
    found = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(path.stat().st_mtime))
    for c in leads:
        c.setdefault("ts", found)  # erfasst_am = Laufzeit, nicht Exportzeit
    pairs = [(to_row(c, run.get("niche", ""), run_id(path)), c) for c in leads]
    pairs = [(r, c) for r, c in pairs if tier_ok(r["ICP Tier"], a.min_tier)]
    rows = [r for r, _ in pairs]
    gesperrt, bekannt = load_domains(a.sperrliste), load_domains(a.bekannt)
    if a.format == "arvana":
        out_rows = [to_arvana(r, c, gesperrt, bekannt) for r, c in pairs]
        cols = ARVANA_COLUMNS
    else:
        out_rows, cols = rows, COLUMNS
    out = Path(a.out) if a.out else path.with_name(f"{path.stem}_{a.format}")
    write_csv(out_rows, out.with_suffix(".csv"), cols)
    out.with_suffix(".json").write_text(json.dumps(out_rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(out_rows)} Zeilen -> {out.with_suffix('.csv')}\n{tier_summary(rows)}")
    if a.format == "arvana" and (gesperrt or bekannt):
        print(f"gesperrt: {sum(r['gesperrt'] == 'ja' for r in out_rows)} · "
              f"schon bekannt: {sum(r['bekannt'] == 'ja' for r in out_rows)}")
    if a.webhook:
        url = os.getenv("CLAY_WEBHOOK_URL", "")
        if not url:
            sys.exit("CLAY_WEBHOOK_URL fehlt in .env")
        # Gesperrte nie rausschicken, Abgleich über die Domain, gleich für beide Formate
        send = [o for o, (r, _) in zip(out_rows, pairs)
                if not (r["Company Domain"] and norm_domain(r["Company Domain"]) in gesperrt)]
        print(f"Clay-Webhook: {post_webhook(send, url, os.getenv('CLAY_WEBHOOK_TOKEN', ''))}/{len(send)} gesendet")


if __name__ == "__main__":
    main()
