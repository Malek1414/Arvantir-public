"""trace: run the repo's own command under OpenTelemetry and record what actually runs, with no code change in the repo.

    python -m repograph trace <repo> [--graph docs/graph/graph.json] [--out docs/graph/trace.json] \
        [--skip-layers tests,web] -- -m arvantir run "Waschanlagen"

How it works:
- OpenTelemetry TracerProvider with an in-memory exporter (no collector needed). Swapping in an OTLP exporter later
  sends the same spans to Jaeger/Tempo/Langfuse (live monitor)
- every module function in the graph is wrapped at runtime by a span wrapper (in its own module AND everywhere it
  was imported by name), attributes: repograph.node, code.function, items_in/items_out (length of list/dict
  arguments and return values), error status on exceptions
- httpx auto-instrumentation records every web request as a CLIENT span (host, status)
- output: aggregates per module/function plus the longest/most important spans as a timeline for the replay
"""
from __future__ import annotations

import functools
import inspect
import json
import os
import runpy
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

MAX_SPANS = 4000
MIN_SPAN_MS = 15.0


def _size(x: Any) -> Optional[int]:
    if isinstance(x, (list, tuple, set)):
        return len(x)
    if isinstance(x, dict):  # Pipelines geben oft {"leads": [...], ...} zurück
        lists = [v for v in x.values() if isinstance(v, list)]
        return max((len(v) for v in lists), default=None)
    return None


def _wrap(fn, tracer, node: str):
    if getattr(fn, "__repograph__", False):
        return fn
    name = f"{node}.{fn.__name__}"

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        from opentelemetry.trace import Status, StatusCode
        with tracer.start_as_current_span(name, record_exception=False) as span:
            span.set_attribute("repograph.node", node)
            span.set_attribute("code.function", fn.__name__)
            span.set_attribute("thread.id", threading.get_ident())
            n_in = next((s for s in (_size(a) for a in args[:2]) if s is not None), None)
            if n_in is not None:
                span.set_attribute("repograph.items_in", n_in)
            try:
                out = fn(*args, **kwargs)
            except BaseException as e:
                span.set_status(Status(StatusCode.ERROR, f"{type(e).__name__}: {str(e)[:120]}"))
                raise
            n_out = _size(out)
            if n_out is not None:
                span.set_attribute("repograph.items_out", n_out)
            return out

    wrapper.__repograph__ = True
    return wrapper


def instrument(repo: Path, graph: dict, tracer, skip_layers: set) -> Dict[str, int]:
    """Import the graph's modules, wrap their own functions, patch every name reference. Returns functions per module."""
    import importlib
    sys.path.insert(0, str(repo))
    mods = {}
    for n in graph["nodes"]:
        if n["layer"] in skip_layers or n.get("entry") and n["id"].endswith("__main__"):
            continue
        try:
            mods[n["id"]] = importlib.import_module(n["id"])
        except Exception as e:  # noqa: BLE001 - optional modules (missing deps) are simply not traced
            print(f"[trace] not importable, skipped: {n['id']} ({type(e).__name__})")
    originals: Dict[int, Any] = {}
    count: Dict[str, int] = {}
    for name, m in mods.items():
        for attr, obj in list(vars(m).items()):
            if inspect.isfunction(obj) and obj.__module__ == m.__name__:
                w = _wrap(obj, tracer, name)
                setattr(m, attr, w)
                originals[id(obj)] = w
                count[name] = count.get(name, 0) + 1
    for m in mods.values():  # "from .harvest import harvest" has already bound the original by name
        for attr, obj in list(vars(m).items()):
            if id(obj) in originals and not getattr(obj, "__repograph__", False):
                setattr(m, attr, originals[id(obj)])
    return count


def _summarize(spans, t0_ns: int, graph: dict) -> dict:
    nodes: Dict[str, dict] = {}
    http = {"requests": 0, "errors": 0, "ms": 0.0, "hosts": {}}
    rows: List[dict] = []
    flow_calls = {(s["node"], s["call"]) for fl in graph.get("flows", []) for s in fl["steps"]}
    owner = {s.context.span_id: (s.attributes or {}).get("repograph.node") for s in spans}
    parent_of = {s.context.span_id: (s.parent.span_id if s.parent else None) for s in spans}

    stage_nodes = {s["node"] for fl in graph.get("flows", []) for s in fl["steps"]}

    def caller(sid):
        """Credit to the OUTERMOST product-flow stage in the parent chain (enrich -> impressum -> harvest.fetch
        counts as enrich), else the nearest repo function. Worker threads keep their parent via ThreadingInstrumentor."""
        nearest = stage = None
        for _ in range(200):
            sid = parent_of.get(sid)
            if sid is None:
                break
            node = owner.get(sid)
            if node and nearest is None:
                nearest = node
            if node in stage_nodes:
                stage = node
        return stage or nearest

    for s in spans:
        a = dict(s.attributes or {})
        dur = (s.end_time - s.start_time) / 1e6
        start = (s.start_time - t0_ns) / 1e6
        err = s.status.status_code.name == "ERROR"
        if "repograph.node" in a:
            node, fn = a["repograph.node"], a.get("code.function", "")
            N = nodes.setdefault(node, {"calls": 0, "ms": 0.0, "errors": 0, "items_in": 0, "items_out": 0, "functions": {}})
            F = N["functions"].setdefault(fn, {"calls": 0, "ms": 0.0, "errors": 0})
            for d in (N, F):
                d["calls"] += 1
                d["ms"] += dur
                d["errors"] += err
            N["items_in"] += a.get("repograph.items_in", 0) or 0
            N["items_out"] += a.get("repograph.items_out", 0) or 0
            # a stage call made inside another stage (enrich -> channel per company) belongs to that stage in the replay
            inside = caller(s.context.span_id) if (node, fn) in flow_calls else None
            nested = inside if inside in stage_nodes and inside != node else None
            row = {"kind": "function", "node": node, "fn": fn, "start_ms": round(start, 1), "dur_ms": round(dur, 1),
                   "items_in": a.get("repograph.items_in"), "items_out": a.get("repograph.items_out"),
                   "status": "error" if err else "ok", "thread": a.get("thread.id"),
                   "flow": (node, fn) in flow_calls and not nested}
            if nested:
                row["in"] = nested
            rows.append(row)
        else:  # httpx CLIENT spans
            url = a.get("url.full") or a.get("http.url") or ""
            host = urlparse(str(url)).hostname or "?"
            code = a.get("http.response.status_code") or a.get("http.status_code")
            bad = err or (isinstance(code, int) and code >= 400)
            http["requests"] += 1
            http["errors"] += bad
            http["ms"] += dur
            http["hosts"][host] = http["hosts"].get(host, 0) + 1
            cls = f"{str(code)[0]}xx" if isinstance(code, int) else "no response"
            http.setdefault("status", {})
            http["status"][cls] = http["status"].get(cls, 0) + 1
            if bad:
                http.setdefault("fail_hosts", {})
                http["fail_hosts"][host] = http["fail_hosts"].get(host, 0) + 1
            by = caller(s.context.span_id)
            if by:
                http.setdefault("by_node", {})
                http["by_node"][by] = http["by_node"].get(by, 0) + 1
            rows.append({"kind": "http", "node": "external:web", "fn": host, "start_ms": round(start, 1),
                         "dur_ms": round(dur, 1), "status": "error" if bad else "ok", "code": code, "by": by})
    for N in nodes.values():
        N["ms"] = round(N["ms"], 1)
        for F in N["functions"].values():
            F["ms"] = round(F["ms"], 1)
    http["ms"] = round(http["ms"], 1)
    http["hosts"] = dict(sorted(http["hosts"].items(), key=lambda kv: -kv[1])[:40])
    http["fail_hosts"] = dict(sorted(http.get("fail_hosts", {}).items(), key=lambda kv: -kv[1])[:15])
    # web requests always stay (the replay counts them), plus flow calls and spans >= MIN_SPAN_MS
    keep = [r for r in rows if r["kind"] == "http" or r.get("flow") or r.get("in") or r["dur_ms"] >= MIN_SPAN_MS]
    keep.sort(key=lambda r: (r["kind"] != "http" and not r.get("flow"), -r["dur_ms"]))
    keep = sorted(keep[:MAX_SPANS], key=lambda r: r["start_ms"])
    return {"nodes": nodes, "http": http, "spans": keep, "spans_total": len(rows)}


def main(argv: List[str]) -> None:
    import argparse
    if "--" not in argv:
        sys.exit("trace needs a command after --, e.g.:  -- -m arvantir run \"Waschanlagen\"")
    i = argv.index("--")
    own, cmd = argv[:i], argv[i + 1:]
    ap = argparse.ArgumentParser(prog="repograph trace")
    ap.add_argument("repo")
    ap.add_argument("--graph", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--skip-layers", default="tests,repograph,web")
    a = ap.parse_args(own)
    repo = Path(a.repo).resolve()
    gpath = Path(a.graph) if a.graph else repo / "docs" / "graph" / "graph.json"
    graph = json.loads(gpath.read_text(encoding="utf-8"))

    from opentelemetry import trace as ot
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
    exporter = InMemorySpanExporter()
    provider = TracerProvider(resource=Resource.create({"service.name": graph["repo"]["name"]}))
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    ot.set_tracer_provider(provider)
    tracer = ot.get_tracer("repograph")
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        HTTPXClientInstrumentor().instrument()
    except Exception as e:  # noqa: BLE001
        print(f"[trace] httpx instrumentation off ({type(e).__name__})")
    try:  # carry the span context into Thread/ThreadPoolExecutor workers, so their calls keep their parent stage
        from opentelemetry.instrumentation.threading import ThreadingInstrumentor
        ThreadingInstrumentor().instrument()
    except Exception as e:  # noqa: BLE001
        print(f"[trace] threading instrumentation off ({type(e).__name__}): worker-thread calls start new chains")

    os.chdir(repo)
    wrapped = instrument(repo, graph, tracer, {x for x in a.skip_layers.split(",") if x})
    print(f"[trace] {sum(wrapped.values())} functions in {len(wrapped)} modules instrumented, starting: {' '.join(cmd)}")
    t0_ns, t0 = time.time_ns(), time.time()
    exit_info = "ok"
    try:
        if cmd[0] == "-m":
            sys.argv = [cmd[1]] + cmd[2:]
            runpy.run_module(cmd[1], run_name="__main__", alter_sys=True)
        else:
            sys.argv = cmd
            runpy.run_path(cmd[0], run_name="__main__")
    except SystemExit as e:
        exit_info = "ok" if e.code in (None, 0) else f"exit {e.code}"
    except BaseException as e:  # noqa: BLE001 - a failed run is shown in the site too
        exit_info = f"error: {type(e).__name__}: {str(e)[:200]}"
    provider.force_flush()
    summary = _summarize(exporter.get_finished_spans(), t0_ns, graph)
    out = {"run": {"command": " ".join(cmd), "repo": graph["repo"].get("remote") or repo.name,
                   "commit": graph["repo"].get("commit", ""), "started_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t0)),
                   "duration_ms": round((time.time() - t0) * 1000), "exit": exit_info,
                   "otel": {"service.name": graph["repo"]["name"], "exporter": "in-memory -> JSON"}},
           **summary}
    opath = Path(a.out) if a.out else repo / "docs" / "graph" / "trace.json"
    opath.parent.mkdir(parents=True, exist_ok=True)
    opath.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    sys.__stdout__.write(f"[trace] {out['spans_total']} spans ({len(out['spans'])} in timeline), "
                         f"{out['http']['requests']} web requests, {out['run']['duration_ms'] / 1000:.1f} s, {exit_info} -> {opath}\n")
