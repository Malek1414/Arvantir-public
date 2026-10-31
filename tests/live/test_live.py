"""Echter Lauf mit Netz: python -m pytest -m live  (dauert 1 bis 2 Minuten)."""
from __future__ import annotations

import time

import pytest

pytestmark = pytest.mark.live


def test_waschanlagen_end_to_end():
    from arvantir.pipeline import run

    t0 = time.time()
    out = run("Waschanlagen")
    seconds = time.time() - t0
    leads = out["leads"]
    tiers = {l["tier"] for l in leads}
    print(f"\n{len(leads)} Leads in {seconds:.0f} s, Tiers {sorted(tiers)}, Datei {out['file']}")
    assert len(leads) >= 50, out["funnel"]
    assert len(tiers) >= 3, "Tiers streuen nicht"
    assert seconds < 120
    assert all(l.get("source_url") for l in leads), "Lead ohne Fundstelle"
    assert [s["step"] for s in out["funnel"]][0] == "Quellen gefunden"
    # Qualität: keine Website darf für viele verschiedene Firmen stehen (Schwesterportal-Fehler)
    from collections import Counter
    hosts = Counter(l["website"].split("/")[2] for l in leads if l.get("website"))
    host, n = hosts.most_common(1)[0]
    assert n <= 5, f"{n} Leads teilen sich die Website {host}"
