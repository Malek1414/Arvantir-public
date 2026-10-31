"""scan: Python-Repo -> graph.json (Schichten, Module, Abhängigkeiten, Produkt-Fluss). Deterministisch, ohne LLM.

    python -m repograph scan <repo> [--out docs/graph/graph.json] [--exclude video,pitch]

- Schicht  = oberster Ordner (Paket) im Repo, Modul = .py-Datei
- Kanten   = interne Imports (import / from . import / from paket.x import), plus "dynamisch":
             Aufrufe mit einem String-Argument, das ein Geschwister-Modul benennt (z. B. _optional("normalize", ...))
- Fluss    = Orchestrator-Funktionen: Funktionen, die nacheinander >= 4 verschiedene interne Module aufrufen;
             die Reihenfolge der Aufrufe im Quelltext ist die Produkt-Reihenfolge
- Texte    = erste Docstring-Zeile je Modul/Funktion (das LLM kann später nur Beschriftungen ergänzen)
"""
from __future__ import annotations

import ast
import json
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", "build", "dist", ".mypy_cache", ".pytest_cache"}


def _first_line(doc: Optional[str]) -> str:
    if not doc:
        return ""
    for line in doc.strip().splitlines():
        if line.strip():
            return line.strip()[:240]
    return ""


def module_name(root: Path, path: Path) -> str:
    rel = path.relative_to(root).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def find_modules(root: Path, exclude: Set[str]) -> Dict[str, Path]:
    mods: Dict[str, Path] = {}
    for p in sorted(root.rglob("*.py")):
        rel = p.relative_to(root)
        if any(part in SKIP_DIRS or part.startswith(".") for part in rel.parts[:-1]):
            continue
        if rel.parts[0] in exclude:
            continue
        name = module_name(root, p)
        if name:
            mods[name] = p
    return mods


def _resolve_relative(current: str, is_pkg: bool, level: int, target: Optional[str]) -> str:
    base = current.split(".") if is_pkg else current.split(".")[:-1]
    base = base[: len(base) - (level - 1)] if level > 1 else base
    return ".".join(base + ([target] if target else []))


def _internal(name: str, mods: Dict[str, Path]) -> Optional[str]:
    """Längstes bekanntes Modul-Präfix von name (a.b.c -> a.b, wenn a.b ein Modul ist)."""
    parts = name.split(".")
    for i in range(len(parts), 0, -1):
        cand = ".".join(parts[:i])
        if cand in mods:
            return cand
    return None


class _Visitor(ast.NodeVisitor):
    def __init__(self, mod: str, is_pkg: bool, mods: Dict[str, Path]):
        self.mod, self.is_pkg, self.mods = mod, is_pkg, mods
        self.imports: Dict[str, Set[str]] = {}   # Zielmodul -> importierte Namen
        self.bound: Dict[str, Tuple[str, str]] = {}  # lokaler Name -> (Modul, Originalname)
        self.dynamic: Set[str] = set()
        self.funcs: List[dict] = []
        self.classes: List[str] = []
        self._fn: Optional[dict] = None

    def _add(self, target: str, name: str = "") -> Optional[str]:
        t = _internal(target, self.mods)
        if t and t != self.mod:
            self.imports.setdefault(t, set())
            if name:
                self.imports[t].add(name)
        return t

    def visit_Import(self, node: ast.Import) -> None:
        for a in node.names:
            t = self._add(a.name)
            if t:
                self.bound[a.asname or a.name.split(".")[0]] = (t, "")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        base = _resolve_relative(self.mod, self.is_pkg, node.level, node.module) if node.level else (node.module or "")
        for a in node.names:
            sub = f"{base}.{a.name}" if base else a.name
            if sub in self.mods:  # from paket import modul
                t = self._add(sub)
                if t:
                    self.bound[a.asname or a.name] = (t, "")
            else:
                t = self._add(base, a.name)
                if t:
                    self.bound[a.asname or a.name] = (t, a.name)

    def visit_FunctionDef(self, node) -> None:
        outer = self._fn
        if outer is None:  # nur Funktionen auf Modulebene
            self._fn = {"name": node.name, "line": node.lineno, "doc": _first_line(ast.get_docstring(node)), "calls": []}
            self.funcs.append(self._fn)
        self.generic_visit(node)
        self._fn = outer

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if self._fn is None:
            self.classes.append(node.name)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        target = None
        f = node.func
        if isinstance(f, ast.Name) and f.id in self.bound:
            target = self.bound[f.id]
        elif isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id in self.bound:
            m, _ = self.bound[f.value.id]
            target = (_internal(f"{m}.{f.attr}", self.mods) or m, f.attr)
        # dynamisch: String-Argument benennt ein Geschwister-Modul, z. B. _optional("normalize", "normalize")
        pkg = self.mod if self.is_pkg else self.mod.rsplit(".", 1)[0] if "." in self.mod else ""
        for arg in node.args[:2]:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and arg.value.isidentifier():
                cand = f"{pkg}.{arg.value}" if pkg else arg.value
                if cand in self.mods and cand != self.mod:
                    self.dynamic.add(cand)
                    if self._fn is not None and target is None:
                        target = (cand, arg.value)
        if target and self._fn is not None and target[0] != self.mod:
            self._fn["calls"].append({"module": target[0], "name": target[1], "line": node.lineno})
        self.generic_visit(node)


def _git(root: Path, *args: str) -> str:
    try:
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def scan(root: Path, exclude: Optional[Set[str]] = None, min_flow_modules: int = 4) -> dict:
    root = root.resolve()
    exclude = set(exclude or ())
    own = Path(__file__).resolve().parent
    if own.parent == root:  # repograph vendored into the repo it maps: leave itself out of the graph
        exclude.add(own.name)
    mods = find_modules(root, exclude)
    nodes, edges, flows = [], [], []
    for name, path in mods.items():
        src = path.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        v = _Visitor(name, path.name == "__init__.py", mods)
        v.visit(tree)
        entry = path.name == "__main__.py" or 'if __name__ == "__main__"' in src or "if __name__ == '__main__'" in src
        nodes.append({
            "id": name, "label": name.rsplit(".", 1)[-1], "layer": name.split(".")[0],
            "path": str(path.relative_to(root)), "loc": src.count("\n") + 1,
            "doc": _first_line(ast.get_docstring(tree)), "entry": entry,
            "functions": [{"name": f["name"], "line": f["line"], "doc": f["doc"]} for f in v.funcs],
            "classes": v.classes,
        })
        for t, names in sorted(v.imports.items()):
            edges.append({"source": name, "target": t, "kind": "import", "names": sorted(names)})
        for t in sorted(v.dynamic - set(v.imports)):
            edges.append({"source": name, "target": t, "kind": "dynamic", "names": []})
        for f in v.funcs:  # Orchestratoren: viele verschiedene interne Module nacheinander
            steps, seen = [], set()
            for c in f["calls"]:
                if c["module"] not in seen:
                    seen.add(c["module"])
                    steps.append({"node": c["module"], "call": c["name"], "line": c["line"]})
            if len(steps) >= min_flow_modules:
                flows.append({"id": f"{name}.{f['name']}", "label": f"{name}.{f['name']}", "doc": f["doc"],
                              "owner": name, "steps": steps})
    layers = {}
    for n in nodes:
        L = layers.setdefault(n["layer"], {"id": n["layer"], "label": n["layer"], "modules": 0, "loc": 0, "doc": ""})
        L["modules"] += 1
        L["loc"] += n["loc"]
        if n["id"] == n["layer"] and n["doc"]:
            L["doc"] = n["doc"]
    flows.sort(key=lambda fl: -len(fl["steps"]))
    remote = _git(root, "config", "--get", "remote.origin.url")
    name = remote.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git") if remote else root.name
    return {
        "repo": {"name": name or root.name, "commit": _git(root, "rev-parse", "--short", "HEAD"),
                 "remote": remote,
                 "generated_at": time.strftime("%Y-%m-%d %H:%M")},
        "layers": sorted(layers.values(), key=lambda l: -l["loc"]),
        "nodes": nodes, "edges": edges, "flows": flows,
    }


def main(argv: List[str]) -> None:
    import argparse
    ap = argparse.ArgumentParser(prog="repograph scan")
    ap.add_argument("repo")
    ap.add_argument("--out", default="")
    ap.add_argument("--exclude", default="", help="kommagetrennte oberste Ordner, z. B. video,pitch")
    a = ap.parse_args(argv)
    g = scan(Path(a.repo), {x for x in a.exclude.split(",") if x})
    out = Path(a.out) if a.out else Path(a.repo) / "docs" / "graph" / "graph.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(g, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[scan] {len(g['layers'])} Schichten, {len(g['nodes'])} Module, {len(g['edges'])} Kanten, "
          f"{len(g['flows'])} Flüsse -> {out}")
    for fl in g["flows"][:3]:
        print("  Fluss", fl["id"], ":", " -> ".join(s["node"].rsplit('.', 1)[-1] for s in fl["steps"]))
