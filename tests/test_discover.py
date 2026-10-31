"""discover: DACH- und Erwachsenen-Filter, Nischen mit & zerlegen, Re-Ranking der Quellen (search gemockt)."""
from __future__ import annotations

import pytest

import arvantir.discover as d
from conftest import L


@pytest.mark.parametrize("url,title,ok", [
    ("https://www.eco.de/mitglieder/", "", True),
    ("https://www.wko.at/branchen", "", True),
    ("https://verband.ch/mitglieder", "", True),
    ("https://partner.shopware.com/liste", "", True),
    ("https://firmen.ru/list", "", False),
    ("https://companies.cn/de", "", False),
    ("https://business.zw/directory", "", False),
    ("https://de.linkedin.com/company/x", "", False),
    ("https://de.wikipedia.org/wiki/Bäckerei", "", False),
    ("https://xhamster.com/baecker", "", False),
    ("https://verzeichnis.de/sexy-escort-berlin", "", False),
    ("https://harmlos.de/liste", "Hot Porn Videos", False),
])
def test_allowed(url, title, ok):
    assert d._allowed(url, title) is ok


@pytest.mark.parametrize("niche,parts", [
    ("Bäckereien & Metzgereien", ["Bäckereien", "Metzgereien"]),
    ("Ärzte und Apotheken", ["Ärzte", "Apotheken"]),
    ("Family Offices / LPs", ["Family Offices", "LPs"]),
])
def test_understand_splits_niche_without_llm(niche, parts):
    plan = d.understand(niche)
    for p in parts:
        assert any(q.startswith(p + " ") or q.endswith(" " + p) for q in plan["queries"]), p
    assert not any("&" in q for q in plan["queries"])
    assert len(plan["queries"]) == len(parts) * len(d.TEMPLATES)


def test_discover_filters_and_ranks(monkeypatch):
    hits = {
        "good": {"url": "https://www.baeckerinnung-berlin.de/mitglieder", "title": "Mitgliedsbetriebe der Innung",
                 "content": "Liste aller Innungsbäckereien in Berlin"},
        "weak": {"url": "https://www.einzelbaecker.de/", "title": "Bäckerei Schulz",
                 "content": "Unsere Brötchen"},
        "ru": {"url": "https://baker.ru/list", "title": "Bakers", "content": "list"},
        "adult": {"url": "https://www.xnxx.com/bakery", "title": "x", "content": "x"},
        "social": {"url": "https://www.linkedin.com/company/baecker", "title": "LinkedIn", "content": "x"},
    }
    monkeypatch.setattr(d, "search", lambda q, max_results=8: list(hits.values()))
    monkeypatch.setattr(d, "curated", lambda niche: [])
    seen_docs = []

    def fake_score(query, docs):
        seen_docs.extend(docs)
        return [L(95) if "Innung" in doc else L(5) for doc in docs]

    monkeypatch.setattr(d, "rr_score", fake_score)
    res = d.discover("Bäckereien")
    urls = [s["url"] for s in res["sources"]]
    assert urls == [hits["good"]["url"]]  # weak liegt unter MIN_SCORE, der Rest ist gefiltert
    assert res["sources"][0]["score"] == 95
    assert res["sources"][0]["type"] == "Verband"
    assert not any("baker.ru" in doc or "xnxx" in doc or "linkedin" in doc for doc in seen_docs)


def test_discover_dedupes_urls_and_survives_failing_search(monkeypatch):
    calls = {"n": 0}

    def flaky(q, max_results=8):
        calls["n"] += 1
        if calls["n"] % 2:
            raise TimeoutError("DDG hängt")
        return [{"url": "https://verband.de/mitglieder#a", "title": "Mitglieder", "content": "Liste"},
                {"url": "https://verband.de/mitglieder/", "title": "Mitglieder", "content": "Liste"}]

    monkeypatch.setattr(d, "search", flaky)
    monkeypatch.setattr(d, "curated", lambda niche: [])
    monkeypatch.setattr(d, "rr_score", lambda q, docs: [L(90)] * len(docs))
    res = d.discover("Waschanlagen")
    assert len(res["sources"]) == 1


def test_curated_sources_get_bonus(monkeypatch):
    monkeypatch.setattr(d, "search", lambda q, max_results=8: [])
    monkeypatch.setattr(d, "rr_score", lambda q, docs: [L(15)] * len(docs))  # 15 < MIN_SCORE
    res = d.discover("Waschanlagen")
    assert res["sources"], "kuratierte Quellen aus research/sources.json fehlen"
    assert all(s["origin"] == "kuratiert" and s["score"] == 25 for s in res["sources"])
