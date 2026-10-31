"""web: Startseite, Laufliste, Host-Prüfung gegen DNS-Rebinding, kein Pfad-Traversal."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

import web.server as server


@pytest.fixture
def client(monkeypatch, tmp_path):
    (tmp_path / "run_101010.json").write_text(json.dumps({
        "seed": "Waschanlagen", "funnel": [{"step": "gerankt", "n": 2}], "seconds": 12.3,
        "leads": [{"name": "A GmbH", "score": 90, "raw_text": "x" * 5000, "profile": "lang"},
                  {"name": "B GmbH", "score": 40}]}), encoding="utf-8")
    (tmp_path / "run_101010_arvana.json").write_text("[]", encoding="utf-8")
    monkeypatch.setattr(server, "DATA", tmp_path)
    return TestClient(server.app, base_url="http://127.0.0.1")


def test_index(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_runs_lists_only_pipeline_runs(client):
    r = client.get("/runs")
    assert r.status_code == 200
    assert r.json() == [{"file": "run_101010.json", "seed": "Waschanlagen", "leads": 2, "seconds": 12.3,
                         "steps": 1}]


def test_run_file_is_slim(client):
    lead = client.get("/runs/run_101010.json").json()["leads"][0]
    assert lead["name"] == "A GmbH"
    assert "raw_text" not in lead and "profile" not in lead


@pytest.mark.parametrize("name", ["..%2F.env", "run_101010_arvana.json", "run_1.json", "%2E%2E%2Fpages.json"])
def test_run_file_rejects_other_names(client, name):
    assert client.get(f"/runs/{name}").status_code in (400, 404)


@pytest.mark.parametrize("host", ["evil.example.com", "testserver", "127.0.0.1.nip.io"])
def test_foreign_host_rejected(host):
    c = TestClient(server.app, base_url=f"http://{host}")
    assert c.get("/runs").status_code == 400


def test_localhost_allowed():
    assert TestClient(server.app, base_url="http://localhost").get("/").status_code == 200


def test_unknown_run_id(client):
    assert client.get("/result/doesnotexist").status_code == 404
    assert client.get("/events/doesnotexist").status_code == 404


def test_run_input_validated(client):
    assert client.post("/run", json={"niche": "x"}).status_code == 422
    assert client.post("/run", json={"niche": "a" * 201}).status_code == 422


def test_no_cors_headers(client):
    r = client.get("/runs", headers={"Origin": "https://evil.example.com"})
    assert "access-control-allow-origin" not in {k.lower() for k in r.headers}
