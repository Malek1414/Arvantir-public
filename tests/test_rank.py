"""rank: Tiers wie Arvanas icp-scorer, needs_human-Band, Konfidenz, Datenlücken, plus ein echter Modelltest."""
from __future__ import annotations

import pytest

import arvantir.rank as rank
from arvantir.common import tier, to_100
from conftest import L, model_cached


@pytest.mark.parametrize("score,t", [(100, "A"), (80, "A"), (79, "B"), (60, "B"), (59, "C"),
                                     (40, "C"), (39, "D"), (0, "D")])
def test_tier_bounds(score, t):
    assert tier(score) == t


def test_to_100_is_monotonic_and_centered():
    from arvantir.common import CAL_CENTER
    assert to_100(CAL_CENTER) == 50
    vals = [to_100(x) for x in (-10, -5, -2, 0, 1, 5)]
    assert vals == sorted(vals) and 0 <= vals[0] and vals[-1] <= 100
    for s in (10, 45, 80, 95):
        assert to_100(L(s)) == s


def _lead(name, **kw):
    return {"name": name, "website": f"https://{name.lower()}.de", **kw}


@pytest.fixture
def absolute(monkeypatch):
    monkeypatch.setenv("RR_MIX", "1.0")  # nur absoluter Score, damit Grenzen exakt prüfbar sind


def test_scores_tiers_and_order(fake_rr, absolute):
    fake_rr({"Alpha": 91, "Beta": 65, "Gamma": 45, "Delta": 10})
    out = rank.rank([_lead("Delta"), _lead("Beta"), _lead("Alpha"), _lead("Gamma")], "ICP")
    assert [(r["name"], r["score"], r["tier"]) for r in out] == [
        ("Alpha", 91, "A"), ("Beta", 65, "B"), ("Gamma", 45, "C"), ("Delta", 10, "D")]


@pytest.mark.parametrize("p,human,conf", [
    (50, True, "niedrig"), (62, True, "niedrig"), (38, True, "niedrig"),
    (63, False, "mittel"), (80, False, "mittel"), (81, False, "hoch"), (5, False, "hoch"),
])
def test_needs_human_band_and_confidence(fake_rr, absolute, p, human, conf):
    fake_rr({"Firma": p})
    r = rank.rank([_lead("Firma")], "ICP")[0]
    assert r["needs_human"] is human
    assert r["confidence"] == conf


def test_konfidenz_levels(fake_rr, absolute):
    fake_rr({"Belegt": 90, "Knapp": 52, "Roh": 90, "Leer": 90})
    out = {r["name"]: r["konfidenz"] for r in rank.rank([
        _lead("Belegt", profile="Wir sind ein Systemhaus für den Mittelstand."),
        _lead("Knapp", profile="Wir sind ein Systemhaus für den Mittelstand."),
        _lead("Roh", raw_text="Roh GmbH, 10115 Berlin"),
        {"name": "Leer"},
    ], "ICP")}
    assert out == {"Belegt": "belegt", "Knapp": "wahrscheinlich", "Roh": "wahrscheinlich", "Leer": "unbekannt"}


def test_datenluecken(fake_rr, absolute):
    fake_rr({})
    full = _lead("Voll", profile="Profiltext lang genug für einen Satz hier.", postcode="10115",
                 decision_maker="Erika Muster", email="e@voll.de")
    empty = {"name": "Leer"}
    out = {r["name"]: r["datenluecken"] for r in rank.rank([full, empty], "ICP")}
    assert out["Voll"] == ""
    assert out["Leer"] == "website, profil, plz, entscheider, email"


def test_reason_is_best_sentence_with_source(fake_rr, absolute, monkeypatch):
    def fake(query, docs):
        return [L(90) if "Managed Services" in doc else L(10) for doc in docs]
    monkeypatch.setattr(rank, "rr_score", fake)
    lead = _lead("Systemhaus", profile="Willkommen auf unserer Seite heute. Wir liefern Managed Services "
                                       "für den Mittelstand in NRW.", profile_source="https://sys.de/ueber")
    r = rank.rank([lead], "ICP")[0]
    assert "Managed Services" in r["reason"]
    assert r["reason_source"] == "https://sys.de/ueber"


def test_rank_mix_spreads_tiers(fake_rr, monkeypatch):
    """Standard RR_MIX=0.5: auch wenn das Basismodell alles niedrig bewertet, streuen die Tiers."""
    monkeypatch.delenv("RR_MIX", raising=False)
    fake_rr({f"F{i}": 2 + i for i in range(20)})
    tiers = {r["tier"] for r in rank.rank([_lead(f"F{i}") for i in range(20)], "ICP")}
    assert len(tiers) >= 3


def test_empty_input():
    assert rank.rank([], "ICP") == []


@pytest.mark.model
@pytest.mark.skipif(not model_cached(), reason="mMiniLM nicht im lokalen Cache")
def test_real_model_it_beats_bakery(monkeypatch):
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("RR_MIX", "1.0")
    from searchify import score as real
    monkeypatch.setattr(rank, "rr_score", real)
    icp = ("Deutscher IT-Dienstleister oder Systemhaus mit Managed Services, Cloud und IT-Sicherheit "
           "für den Mittelstand")
    it = _lead("Nordwerk IT GmbH", profile="Wir betreuen als Systemhaus 300 mittelständische Kunden mit "
                                          "Managed Services, Microsoft 365, Cloud-Hosting und IT-Security.")
    bak = _lead("Bäckerei Krume", profile="Seit 1987 backen wir in dritter Generation Brot und Brötchen "
                                         "in unserer eigenen Backstube mit vier Filialen.")
    out = rank.rank([bak, it], icp)
    assert out[0]["name"] == "Nordwerk IT GmbH"
    assert out[0]["score"] - out[1]["score"] >= 20
