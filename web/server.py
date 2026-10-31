"""Arvantir Live-Demo: startet einen Pipeline-Lauf und streamt den Funnel per SSE.

Start (nur lokal):  .venv/bin/uvicorn web.server:app --host 127.0.0.1 --port 8400
Kein CORS: Seite und API kommen vom selben Origin.
"""
from __future__ import annotations

import asyncio
import importlib
import importlib.util
import json
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
BENCH = ROOT / "bench"
INDEX = Path(__file__).resolve().parent / "index.html"

RUN_FILE = re.compile(r"^run_\d{6}\.json$")
MAX_PARALLEL = 2
# Felder, die nur intern gebraucht werden und die Antwort aufblähen
HEAVY = {"raw_text", "profile", "doc"}

app = FastAPI(title="Arvantir", docs_url=None, redoc_url=None)
# Schutz gegen DNS-Rebinding: nur echte Localhost-Hostnamen werden bedient
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])

_runs: Dict[str, Dict] = {}
_lock = threading.Lock()


class RunIn(BaseModel):
    niche: str = Field(min_length=2, max_length=200)
    icp: Optional[str] = Field(default="", max_length=2000)


def _slim(out: Dict) -> Dict:
    leads = [{k: v for k, v in l.items() if k not in HEAVY} for l in out.get("leads", [])]
    return {"seed": out.get("seed"), "niche": out.get("niche"), "icp": out.get("icp"),
            "funnel": out.get("funnel", []), "seconds": out.get("seconds"),
            "sources": [{k: s.get(k) for k in ("url", "title", "type", "harvested", "company_share")}
                        for s in out.get("sources", [])],
            "leads": leads}


def _worker(rid: str, niche: str, icp: str) -> None:
    run = _runs[rid]

    def on_step(name: str, n: int, extra: Dict) -> None:
        safe = {}
        if "sources" in extra:
            safe["sources"] = [{"url": s.get("url"), "type": s.get("type")} for s in extra["sources"]]
        if "sources_used" in extra:
            safe["sources_used"] = list(extra["sources_used"])
        if "needs_human" in extra:
            safe["needs_human"] = extra["needs_human"]
        run["events"].append({"type": "step", "step": name, "n": n, "extra": safe,
                              "t": round(time.time() - run["t0"], 1)})

    try:
        from arvantir.pipeline import run as pipeline_run  # spät laden, Start bleibt schnell
        out = pipeline_run(niche, icp=icp, on_step=on_step)
        run["result"] = _slim(out)
        run["status"] = "done"
        run["events"].append({"type": "done", "leads": len(out.get("leads", [])),
                              "file": Path(out.get("file", "")).name})
    except Exception as e:  # Fehlertext ohne Stacktrace an die Seite
        run["status"] = "error"
        run["events"].append({"type": "error", "message": type(e).__name__ + ": " + str(e)[:200]})


@app.get("/")
def index() -> FileResponse:
    return FileResponse(INDEX, headers={"Cache-Control": "no-store"})


@app.post("/run")
def start(body: RunIn) -> Dict:
    with _lock:
        active = sum(1 for r in _runs.values() if r["status"] == "running")
        if active >= MAX_PARALLEL:
            raise HTTPException(429, "Es laufen schon zwei Läufe, bitte kurz warten.")
        rid = uuid.uuid4().hex[:12]
        _runs[rid] = {"status": "running", "events": [], "result": None, "t0": time.time(),
                      "niche": body.niche.strip()}
    threading.Thread(target=_worker, args=(rid, body.niche.strip(), (body.icp or "").strip()),
                     daemon=True).start()
    return {"id": rid}


@app.get("/events/{rid}")
async def events(rid: str) -> StreamingResponse:
    if rid not in _runs:
        raise HTTPException(404, "Lauf unbekannt")

    async def stream():
        sent = 0
        idle = 0
        while True:
            evs: List[Dict] = _runs[rid]["events"]
            while sent < len(evs):
                yield f"data: {json.dumps(evs[sent], ensure_ascii=False)}\n\n"
                sent += 1
                idle = 0
            if _runs[rid]["status"] != "running" and sent >= len(evs):
                break
            idle += 1
            if idle % 30 == 0:  # Keep-alive alle ~15 s
                yield ": ping\n\n"
            await asyncio.sleep(0.5)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@app.get("/result/{rid}")
def result(rid: str) -> Dict:
    run = _runs.get(rid)
    if not run:
        raise HTTPException(404, "Lauf unbekannt")
    if run["status"] != "done":
        raise HTTPException(409, run["status"])
    return run["result"]


@app.get("/runs")
def runs() -> List[Dict]:
    out = []
    for p in sorted(DATA.glob("run_*.json"), reverse=True):
        if not RUN_FILE.match(p.name):
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        out.append({"file": p.name, "seed": d.get("seed"), "leads": len(d.get("leads", [])),
                    "seconds": d.get("seconds"), "steps": len(d.get("funnel", []))})
    return out


@app.get("/runs/{name}")
def run_file(name: str) -> Dict:
    if not RUN_FILE.match(name):  # kein Pfad-Traversal
        raise HTTPException(400, "ungültiger Dateiname")
    p = DATA / name
    if not p.exists():
        raise HTTPException(404, "nicht gefunden")
    return _slim(json.loads(p.read_text(encoding="utf-8")))


ENGINE = ["discover", "harvest", "normalize", "darkcheck", "enrich", "signals", "rank", "channel"]
ARCH = Path(__file__).resolve().parent / "architecture.html"
_status_cache: Dict = {"t": 0.0, "data": None}


def _lines(p: Path) -> int:
    try:
        with p.open("rb") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


@app.get("/architecture")
def architecture() -> FileResponse:
    return FileResponse(ARCH, headers={"Cache-Control": "no-store"})


@app.get("/status")
def status() -> Dict:
    """Welche Module und Schritte der Lernschleife existieren schon (für die Architektur-Seite)."""
    if _status_cache["data"] and time.time() - _status_cache["t"] < 5:
        return _status_cache["data"]
    importlib.invalidate_caches()
    modules = {}
    for m in ENGINE:
        try:  # find_spec prüft Importierbarkeit, ohne das Modul auszuführen
            modules[m] = importlib.util.find_spec(f"arvantir.{m}") is not None
        except (ImportError, ValueError):
            modules[m] = False
    model_dir = ROOT / "models" / "arvantir-rr-v1"
    loop = {
        "runs": len([p for p in DATA.glob("run_*.json") if RUN_FILE.match(p.name)]),
        "pairs": _lines(DATA / "rank_pairs.jsonl"),
        "labels": _lines(DATA / "labels_silver.jsonl"),
        "gold": _lines(DATA / "gold.jsonl"),
        "gold_sample": _lines(DATA / "gold_sample.jsonl"),
        "train": (ROOT / "finetune" / "train.py").exists(),
        "model": model_dir.exists() and any(model_dir.iterdir()),
        "bench": (BENCH / "results.md").exists() or (BENCH / "results.json").exists(),
    }
    data = {"modules": modules, "loop": loop}
    _status_cache.update(t=time.time(), data=data)
    return data


@app.get("/bench")
def bench() -> JSONResponse:
    j, m = BENCH / "results.json", BENCH / "results.md"
    if j.exists():
        try:
            return JSONResponse({"kind": "json", "data": json.loads(j.read_text(encoding="utf-8"))})
        except ValueError:
            pass
    if m.exists():
        return JSONResponse({"kind": "md", "data": m.read_text(encoding="utf-8")[:50000]})
    return JSONResponse({"kind": "none"})
