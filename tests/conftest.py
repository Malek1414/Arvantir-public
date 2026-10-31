"""Gemeinsame Fixtures: alles offline, kein LLM, kein Netz, keine Schreibzugriffe auf data/."""
from __future__ import annotations

import gzip
import json
import os
import socket
from pathlib import Path

import pytest

FIX = Path(__file__).resolve().parent / "fixtures"
PAGES = json.loads((FIX / "pages.json").read_text(encoding="utf-8"))


def page(key: str) -> str:
    """Gespeicherte echte Listenseite (einmal mit arvantir.harvest.fetch geholt, 31.10.2026)."""
    return gzip.decompress((FIX / f"{key}.html.gz").read_bytes()).decode("utf-8")


@pytest.fixture(autouse=True)
def offline(request, monkeypatch, tmp_path):
    """Kein LLM-Key, kein Paar-Log in data/, kein Netz (außer bei -m live)."""
    if request.node.get_closest_marker("live"):
        yield
        return
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    import arvantir.discover as discover
    import arvantir.rank as rank
    monkeypatch.setattr(discover, "log_pairs", lambda *a, **k: None)
    monkeypatch.setattr(rank, "log_pairs", lambda *a, **k: None)

    real_connect = socket.socket.connect

    def guarded(self, addr):  # nur lokale Sockets (TestClient, Modell-Cache) erlaubt
        host = addr[0] if isinstance(addr, tuple) else addr
        if isinstance(host, str) and host not in ("127.0.0.1", "::1", "localhost") and not host.startswith("/"):
            raise RuntimeError(f"Test wollte ins Netz: {addr}")
        return real_connect(self, addr)

    monkeypatch.setattr(socket.socket, "connect", guarded)
    yield


@pytest.fixture
def serve(monkeypatch):
    """harvest.fetch durch gespeicherte Seiten ersetzen: serve({url: html}) oder serve() für alle Fixtures."""
    import arvantir.harvest as harvest

    def install(extra=None):
        table = {m["url"]: (page(k), m["final"]) for k, m in PAGES.items()}
        for url, html in (extra or {}).items():
            table[url] = (html, url)
        calls = []

        def fake(url, timeout=25):
            calls.append(url)
            return table.get(url, ("", url))

        monkeypatch.setattr(harvest, "fetch", fake)
        return calls

    return install


@pytest.fixture
def fake_rr(monkeypatch):
    """Re-Ranker ersetzen: Ziel-Score 0-100 je Firmenname (Anfang des Profils), geliefert als Logit."""
    def install(table, default=50, module="arvantir.rank"):
        import importlib
        mod = importlib.import_module(module)

        def fake(query, docs):
            out = []
            for d in docs:
                name = d.split(" | ")[0].split(". ")[0]
                out.append(L(table.get(name, default)))
            return out

        monkeypatch.setattr(mod, "rr_score", fake)
        return fake

    return install


def L(score: float) -> float:
    """Logit, den common.to_100 genau auf `score` (0-100) abbildet. Fakes liefern Logits wie das echte Modell."""
    import math
    from arvantir.common import CAL_CENTER, CAL_SCALE
    score = min(max(score, 0.5), 99.5)
    return CAL_CENTER + CAL_SCALE * math.log(score / (100 - score))


def model_cached() -> bool:
    name = os.getenv("RERANKER_MODEL", "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1")
    if Path(name).exists():
        return True
    hub = Path(os.getenv("HF_HOME", Path.home() / ".cache" / "huggingface")) / "hub"
    return (hub / ("models--" + name.replace("/", "--"))).exists()
