"""adapters: Clay-Spalten exakt wie Arvanas leads_export.csv, Sperrliste, Schlüssel, Supabase-Payload."""
from __future__ import annotations

import csv
import json

import pytest

import adapters.clay as clay
import adapters.supabase as supa
from conftest import FIX


def _run(tmp_path, leads, name="run_120000.json"):
    path = tmp_path / name
    path.write_text(json.dumps({"seed": "Test", "niche": "Test", "icp": "ICP", "funnel": [], "leads": leads}),
                    encoding="utf-8")
    return path


LEADS = [
    {"name": "Silberbach Consulting GmbH", "website": "https://www.silberbach-consulting.de", "score": 91,
     "source_url": "https://verband.de/liste", "source_type": "Verband", "reason": "passt",
     "needs_human": False, "website_confidence": "hoch"},
    {"name": "Uferblick Consulting GmbH", "website": "http://uferblick-consulting.de/", "score": 70,
     "source_url": "https://verband.de/liste", "source_type": "Verband", "needs_human": True},
    {"name": "Neue Firma GmbH", "website": "https://neue-firma.de", "score": 45, "phone": "+49 30 1234567",
     "source_url": "https://messe.de/aussteller", "source_type": "Aussteller"},
    {"name": "=cmd|' /C calc'!A0", "website": "https://boese.de", "score": 10,
     "source_url": "https://messe.de/aussteller", "source_type": "Aussteller"},
]


def test_first_columns_match_leads_export():
    header = next(csv.reader(open(FIX / "leads_export_head.csv", encoding="utf-8")))
    assert clay.ARVANA_COLUMNS[:len(header)] == header


def test_export_arvana_format(tmp_path):
    run = _run(tmp_path, LEADS)
    clay.main([str(run), "--sperrliste", str(FIX / "sperrliste.txt")])
    rows = list(csv.DictReader(open(tmp_path / "run_120000_arvana.csv", encoding="utf-8")))
    by = {r["domain"]: r for r in rows}
    assert by["silberbach-consulting.de"]["gesperrt"] == "ja"     # Sperrliste in GROSSBUCHSTABEN
    assert by["uferblick-consulting.de"]["gesperrt"] == "ja"      # Sperrliste mit www.
    assert by["neue-firma.de"]["gesperrt"] == "nein"
    assert by["silberbach-consulting.de"]["tier"] == "A"
    assert by["uferblick-consulting.de"]["tier"] == "B"
    assert by["uferblick-consulting.de"]["mensch_prueft"] == "ja"
    assert by["neue-firma.de"]["quelle"] == "aussteller:messe.de"
    assert by["neue-firma.de"]["telefon"] == "+49 30 1234567"     # Telefon ohne Formel-Apostroph
    assert by["boese.de"]["firma"].startswith("'=")                # Formel neutralisiert
    assert by["silberbach-consulting.de"]["firmen_key"] == "dom:silberbach-consulting.de"
    assert "entscheider" in by["neue-firma.de"]["datenluecken"]


def test_min_tier_filter(tmp_path):
    clay.main([str(_run(tmp_path, LEADS)), "--min-tier", "B"])
    rows = list(csv.DictReader(open(tmp_path / "run_120000_arvana.csv", encoding="utf-8")))
    assert {r["tier"] for r in rows} == {"A", "B"}


@pytest.mark.parametrize("fmt", ["arvana", "clay"])
def test_webhook_never_sends_blocked(tmp_path, monkeypatch, fmt):
    sent = []
    monkeypatch.setattr(clay, "post_webhook", lambda rows, url, token="": sent.extend(rows) or len(rows))
    monkeypatch.setenv("CLAY_WEBHOOK_URL", "https://api.clay.example/hook")
    clay.main([str(_run(tmp_path, LEADS)), "--format", fmt, "--webhook",
               "--sperrliste", str(FIX / "sperrliste.txt")])
    names = {r.get("firma") or r.get("Company Name") for r in sent}
    assert "Silberbach Consulting GmbH" not in names and "Uferblick Consulting GmbH" not in names
    assert "Neue Firma GmbH" in names


def test_known_list_marks_existing(tmp_path):
    known = tmp_path / "leads.csv"
    known.write_text("vorname,nachname,email,position,firma,domain,quelle,erfasst_am\n"
                     "A,B,,,Neue Firma,NEUE-FIRMA.DE,altbestand,2025-01-01\n", encoding="utf-8")
    clay.main([str(_run(tmp_path, LEADS)), "--bekannt", str(known)])
    rows = {r["domain"]: r for r in csv.DictReader(open(tmp_path / "run_120000_arvana.csv", encoding="utf-8"))}
    assert rows["neue-firma.de"]["bekannt"] == "ja"
    assert rows["boese.de"]["bekannt"] == "nein"


@pytest.mark.parametrize("c,key", [
    ({"name": "Hafenblick Group GmbH", "website": "https://www.hafenblick-group.de",
      "register_court": "Amtsgericht Hamburg", "register_number": "HRB 12 345"}, "reg:amtsgericht hamburg|HRB12345"),
    ({"name": "Hafenblick Group GmbH", "website": "https://www.hafenblick-group.de/kontakt"}, "dom:hafenblick-group.de"),
    ({"name": "hafenblick group", "website": "hafenblick-group.de"}, "dom:hafenblick-group.de"),
    ({"name": "Bäckerei Müller GmbH", "postcode": "14467"}, "name:baeckerei mueller|14467"),
])
def test_entity_key(c, key):
    assert clay.entity_key(c)[0] == key


def test_latest_run_ignores_exports(tmp_path, monkeypatch):
    monkeypatch.setattr(clay, "DATA", tmp_path)
    _run(tmp_path, LEADS, "run_090000.json")
    (tmp_path / "run_090000_arvana.json").write_text("[]")
    assert clay.latest_run().name == "run_090000.json"


def test_supabase_build_dedupes_and_keeps_sources(tmp_path):
    dup = dict(LEADS[0], source_url="https://andere-liste.de", sources=["https://andere-liste.de"] * 2)
    data = supa.build({"seed": "x", "leads": LEADS + [dup]}, "20261031_run_120000")
    keys = [c["entity_key"] for c in data["companies"]]
    assert len(keys) == len(set(keys)) == 4
    silber = next(c for c in data["companies"] if c["entity_key"] == "dom:silberbach-consulting.de")
    assert silber["source_count"] == 2
    pairs = [(s["entity_key"], s["source_url"]) for s in data["company_sources"]]
    assert len(pairs) == len(set(pairs))
    for table, rows in data.items():  # PostgREST-Bulk braucht gleiche Keys in jeder Zeile
        assert len({tuple(sorted(r)) for r in rows}) <= 1, table


def test_supabase_schema_has_immutable_raw_pages():
    sql = (FIX.parent.parent / "adapters" / "supabase.sql").read_text(encoding="utf-8")
    assert "before update or delete on raw_pages" in sql
    assert "enable row level security" in sql
