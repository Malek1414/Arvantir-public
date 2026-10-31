"""pipeline: Smoke-Test von Anfang bis Datei, mit gemockten discover/harvest/Netz."""
from __future__ import annotations

import csv
import json

import pytest

import arvantir.pipeline as p


def _companies(prefix, n, evil=False):
    out = []
    for i in range(n):
        name = f"{prefix} {i} GmbH"
        if evil and i == 0:
            name = '=HYPERLINK("http://evil.example","klick") GmbH'
        out.append({"name": name, "website": f"https://{prefix.lower()}{i}.de", "detail_url": "",
                    "postcode": f"1011{i % 10}", "city": "Berlin", "raw_text": name,
                    "profile": f"{name} ist ein Systemhaus mit Managed Services. Wir betreuen den Mittelstand.",
                    "profile_source": f"https://{prefix.lower()}{i}.de", "source_url": "https://liste.de"})
    return out


@pytest.fixture
def mocked(monkeypatch, tmp_path, fake_rr):
    sources = [{"url": "https://nav.de/menu", "type": "Verzeichnis", "score": 90},
               {"url": "https://liste.de/a", "type": "Verband", "score": 80},
               {"url": "https://liste.de/b", "type": "Messe", "score": 70}]
    monkeypatch.setattr(p, "discover", lambda seed: {"niche": "IT-Dienstleister", "sources": sources,
                                                     "candidates_total": 3, "queries": []})
    lists = {
        "https://nav.de/menu": [{"name": w, "website": "", "detail_url": "", "postcode": ""}
                                for w in ["Start", "News", "Team", "Jobs", "Blog", "FAQ", "Hilfe", "Shop", "Mehr"]],
        "https://liste.de/a": _companies("Alpha", 12, evil=True),
        "https://liste.de/b": _companies("Beta", 9),
    }
    monkeypatch.setattr(p, "harvest", lambda url, niche, **k: {"candidates": [dict(c) for c in lists[url]]})
    monkeypatch.setattr(p, "resolve_websites", lambda c, limit=60: c)
    monkeypatch.setattr(p, "fetch_profiles", lambda c, limit=60: c)
    monkeypatch.setattr(p, "_optional", lambda module, func: None)  # normalize/darkcheck/enrich/signals aus
    monkeypatch.setattr(p, "DATA", tmp_path)
    fake_rr({}, default=30)
    return tmp_path


def test_run_funnel_and_files(mocked):
    steps = []
    out = p.run("IT-Dienstleister", "Systemhaus für den Mittelstand",
                on_step=lambda name, n, extra: steps.append((name, n)))
    assert [s for s, _ in steps] == ["Quellen gefunden", "Firmen ausgelesen", "eindeutige Firmen", "eine Firma, eine Zeile", "mit Website",
                                     "gerankt"]
    assert dict(steps)["Firmen ausgelesen"] == 21          # Navigationsliste verworfen
    assert [s["url"] for s in out["sources"]] == ["https://liste.de/a", "https://liste.de/b"]
    assert len(out["leads"]) == 21
    assert {"score", "tier", "reason", "needs_human", "konfidenz", "datenluecken"} <= set(out["leads"][0])
    saved = json.loads(open(out["file"], encoding="utf-8").read())
    assert saved["funnel"][-1]["step"] == "gerankt"
    assert list(mocked.glob("run_*.csv"))


def test_run_csv_escapes_formulas(mocked):
    out = p.run("IT-Dienstleister", "ICP")
    csv_path = out["file"].replace(".json", ".csv")
    rows = list(csv.DictReader(open(csv_path, encoding="utf-8")))
    evil = [r for r in rows if "HYPERLINK" in r["name"]]
    assert evil and evil[0]["name"].startswith("'=")
    assert not any(v.startswith(("=", "+", "@")) for r in rows for v in r.values() if v)


@pytest.mark.parametrize("v,exp", [("=1+1", "'=1+1"), ("+49", "'+49"), ("-x", "'-x"), ("@SUM(A1)", "'@SUM(A1)"),
                                   ("\tx", "'\tx"), ("Müller GmbH", "Müller GmbH"), (42, 42), (None, None)])
def test_cell(v, exp):
    assert p._cell(v) == exp


def test_icp_for_picks_matching_niche():
    icp = p.icp_for("Waschanlagen")
    assert "Waschanlagen" in icp or "Waschstraßen" in icp
