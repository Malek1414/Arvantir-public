"""repograph: scan (imports, dynamic loading, product flow), trace wrapper (spans, items, errors), build (HTML)."""
import json
import textwrap

import pytest

from repograph.build import build
from repograph.scan import scan


@pytest.fixture()
def mini_repo(tmp_path):
    pkg = tmp_path / "shop"
    pkg.mkdir()
    files = {
        "__init__.py": '"""Shop: a tiny pipeline."""\n',
        "fetch.py": '"""fetch: get items."""\ndef fetch(q):\n    return [q, q]\n',
        "clean.py": '"""clean: dedupe."""\ndef clean(xs):\n    return list(dict.fromkeys(xs))\n',
        "score.py": '"""score: rank."""\ndef score(xs):\n    return sorted(xs)\n',
        "ship.py": '"""ship: export."""\ndef ship(xs):\n    return {"rows": xs}\n',
        "pipeline.py": textwrap.dedent('''
            """pipeline: run everything."""
            import importlib
            from .fetch import fetch
            from .clean import clean
            from . import score

            def _optional(module, func):
                return getattr(importlib.import_module(f"shop.{module}"), func)

            def run(q):
                """Run the whole product."""
                xs = fetch(q)
                xs = clean(xs)
                xs = score.score(xs)
                return _optional("ship", "ship")(xs)
            '''),
        "__main__.py": "from .pipeline import run\nprint(run('a'))\n",
    }
    for name, src in files.items():
        (pkg / name).write_text(src)
    return tmp_path


def test_scan_imports_dynamic_and_flow(mini_repo):
    g = scan(mini_repo)
    ids = {n["id"] for n in g["nodes"]}
    assert {"shop", "shop.fetch", "shop.clean", "shop.score", "shop.ship", "shop.pipeline", "shop.__main__"} <= ids
    edges = {(e["source"], e["target"], e["kind"]) for e in g["edges"]}
    assert ("shop.pipeline", "shop.fetch", "import") in edges
    assert ("shop.pipeline", "shop.score", "import") in edges          # from . import score
    assert ("shop.pipeline", "shop.ship", "dynamic") in edges          # _optional("ship", ...)
    flow = g["flows"][0]
    assert flow["id"] == "shop.pipeline.run"
    assert [s["node"] for s in flow["steps"]] == ["shop.fetch", "shop.clean", "shop.score", "shop.ship"]
    assert next(n for n in g["nodes"] if n["id"] == "shop.fetch")["doc"] == "fetch: get items."
    assert next(n for n in g["nodes"] if n["id"] == "shop.__main__")["entry"] is True


def test_trace_wrapper_records_items_and_errors(mini_repo):
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
    from repograph.trace import _wrap

    exp = InMemorySpanExporter()
    prov = TracerProvider()
    prov.add_span_processor(SimpleSpanProcessor(exp))
    tracer = prov.get_tracer("t")

    def dedupe(xs):
        return list(set(xs))

    def boom(xs):
        raise ValueError("nope")

    assert sorted(_wrap(dedupe, tracer, "m")(["a", "a", "b"])) == ["a", "b"]
    with pytest.raises(ValueError):
        _wrap(boom, tracer, "m")([1])
    spans = {s.name: s for s in exp.get_finished_spans()}
    ok = spans["m.dedupe"]
    assert ok.attributes["repograph.items_in"] == 3 and ok.attributes["repograph.items_out"] == 2
    assert spans["m.boom"].status.status_code.name == "ERROR"


def test_build_inlines_data_safely(mini_repo):
    g = scan(mini_repo)
    g["nodes"][0]["doc"] = "</script><script>alert(1)</script>"
    html = build(g, None, theme="dark", accent="#e3a43b", back="../")
    assert "</script><script>alert(1)" not in html  # "</" is escaped inside the inline JSON
    assert 'data-theme="dark"' in html and "--accent:#e3a43b" in html
    data = html.split('<script id="graph-data" type="application/json">', 1)[1].split("</script>", 1)[0]
    assert json.loads(data)["repo"]["name"] == mini_repo.name


def test_stage_called_inside_another_stage_is_nested():
    """enrich calls channel per company: those calls count under enrich, not as the channel stage starting early."""
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
    from repograph.trace import _summarize, _wrap

    exp = InMemorySpanExporter()
    prov = TracerProvider()
    prov.add_span_processor(SimpleSpanProcessor(exp))
    tracer = prov.get_tracer("t")

    def channel(c):
        return {"kanal": "brief"}

    wrapped_channel = _wrap(channel, tracer, "app.channel")

    def enrich(cs):
        return [wrapped_channel(c) for c in cs]

    _wrap(enrich, tracer, "app.enrich")([1, 2])
    wrapped_channel(3)  # the pipeline's own channel call after rank
    graph = {"repo": {"name": "app"}, "flows": [{"id": "app.run", "steps": [
        {"node": "app.enrich", "call": "enrich", "line": 1}, {"node": "app.channel", "call": "channel", "line": 2}]}]}
    spans = exp.get_finished_spans()
    rows = [r for r in _summarize(spans, min(s.start_time for s in spans), graph)["spans"] if r["node"] == "app.channel"]
    assert sorted((r["flow"], r.get("in")) for r in rows) == [(False, "app.enrich"), (False, "app.enrich"), (True, None)]
