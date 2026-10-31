"""knowncheck: Index bauen aus CSV und Parquet, Abgleich per Domain und Name+Ort, ohne Index unbekannt."""
from __future__ import annotations

import csv
import gzip

import pytest

import arvantir.knowncheck as kc


@pytest.fixture
def index(monkeypatch, tmp_path):
    monkeypatch.setattr(kc, "INDEX", tmp_path / "known.db")
    src = tmp_path / "firmen.csv.gz"
    with gzip.open(src, "wt", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["name", "domain", "locality", "country"])
        w.writerow(["Muster Systemhaus GmbH", "www.muster-it.de", "München, Bayern", "germany"])
        w.writerow(["Waschpark Nord GmbH", "", "Berlin", "germany"])
        w.writerow(["Acme Inc", "acme.com", "Austin", "united states"])
    kc.build(src, "test")
    return src


def test_build_and_lookup(index):
    m = kc.meta()
    assert m["rows"] == "3" and m["dach"] == "2"
    leads = [{"name": "X", "website": "https://shop.muster-it.de/impressum"},
             {"name": "Neu GmbH", "website": "https://neu-dunkel.de"},
             {"name": "Waschpark Nord", "city": "Berlin"},
             {"name": "Waschpark Nord", "city": "Hamburg"},
             {"name": "Ohne Ort"}]
    out = kc.knowncheck(leads)
    assert [c["in_known_db"] for c in out] == [True, False, True, False, None]
    assert [c["known_method"] for c in out] == ["domain", "domain", "name+ort", "name+ort", ""]


def test_city_variants():
    keys = {kc._city(x) for x in ["München", "Muenchen", "Munich", "MUNCHEN, Bayern", "München (Altstadt)"]}
    assert keys == {"munchen"}
    assert kc._city("Köln") == kc._city("Cologne") == kc._city("Koeln")


def test_without_index_stays_unknown(monkeypatch, tmp_path):
    monkeypatch.setattr(kc, "INDEX", tmp_path / "fehlt.db")
    out = kc.knowncheck([{"name": "A", "website": "https://a.de"}])
    assert out[0]["in_known_db"] is None


def test_parquet_source(monkeypatch, tmp_path):
    pa = pytest.importorskip("pyarrow")
    import pyarrow.parquet as pq
    monkeypatch.setattr(kc, "INDEX", tmp_path / "known.db")
    d = tmp_path / "pq"
    d.mkdir()
    pq.write_table(pa.table({"company_name": ["Foo AG"], "primary_domain": ["foo.ch"],
                             "city": ["Zürich"], "country": ["Switzerland"]}), d / "a.parquet")
    kc.build(d)
    assert kc.knowncheck([{"name": "Foo", "website": "foo.ch"}])[0]["in_known_db"] is True
