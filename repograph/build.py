"""build: graph.json (+ trace.json) -> a self-contained HTML site (Cytoscape.js + ELK from jsDelivr, data inline).

    python -m repograph build <repo> [--graph ...] [--trace ...] [--out docs/graph/index.html] [--title "..."]
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List

TEMPLATE = Path(__file__).with_name("template.html")


def _inline(obj) -> str:
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


def build(graph: dict, trace: dict | None, title: str = "", theme: str = "", accent: str = "", back: str = "") -> str:
    """theme: "" (follows the OS), "dark" or "light"; accent: CSS color to match the host site; back: link back."""
    html = TEMPLATE.read_text(encoding="utf-8")
    name = title or graph["repo"]["name"]
    if theme in ("dark", "light"):
        html = html.replace('<html lang="en">', f'<html lang="en" data-theme="{theme}">', 1)
    if accent:
        html = html.replace("</style>", f":root,:root[data-theme]{{--accent:{accent};--accent-soft:{accent}2e}}\n</style>", 1)
    if back:
        html = html.replace('<div class="brand">__TITLE__', f'<div class="brand"><a href="{back}" style="color:inherit;text-decoration:none">&larr;</a> __TITLE__', 1)
    return (html.replace("__TITLE__", name)
                .replace("__GRAPH__", _inline(graph))
                .replace("__TRACE__", _inline(trace) if trace else "null"))


def main(argv: List[str]) -> None:
    import argparse
    ap = argparse.ArgumentParser(prog="repograph build")
    ap.add_argument("repo")
    ap.add_argument("--graph", default="")
    ap.add_argument("--trace", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--title", default="")
    ap.add_argument("--theme", default="", choices=["", "dark", "light"])
    ap.add_argument("--accent", default="", help="CSS color, e.g. #e3a43b")
    ap.add_argument("--back", default="", help="link for the back arrow, e.g. ../")
    a = ap.parse_args(argv)
    repo = Path(a.repo).resolve()
    gpath = Path(a.graph) if a.graph else repo / "docs" / "graph" / "graph.json"
    tpath = Path(a.trace) if a.trace else repo / "docs" / "graph" / "trace.json"
    graph = json.loads(gpath.read_text(encoding="utf-8"))
    trace = json.loads(tpath.read_text(encoding="utf-8")) if tpath.exists() else None
    out = Path(a.out) if a.out else repo / "docs" / "graph" / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build(graph, trace, a.title, a.theme, a.accent, a.back), encoding="utf-8")
    print(f"[build] {out} ({out.stat().st_size // 1024} KB, trace: {'yes' if trace else 'no'})")
