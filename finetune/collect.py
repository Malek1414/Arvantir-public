"""Daten sammeln: pipeline.run für alle Nischen, jeder Lauf nach data/runs/<key>.json.

    .venv/bin/python -m finetune.collect              # alle Nischen, 3 parallel
    .venv/bin/python -m finetune.collect it_dienstleister waschanlagen
    .venv/bin/python -m finetune.collect --variants  # Zusatz-Seeds aus niches.json, mehr Firmen

Jedes bewertete Paar landet über rank.log_pairs in data/rank_pairs.jsonl.
ICP-Texte: research/icps.json (d2) wenn passend, sonst finetune/niches.json.
"""
from __future__ import annotations

import json
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "data" / "runs"


def load_niches() -> list:
    """niches.json; ICP-Text von d2 (research/icps.json) über pipeline.icp_for, sonst der eigene."""
    from arvantir.pipeline import icp_for
    niches = json.loads((ROOT / "finetune" / "niches.json").read_text(encoding="utf-8"))["niches"]
    for n in niches:
        d2 = icp_for(n["seed"])
        if d2:
            n["icp"], n["icp_source"] = d2, "research/icps.json"
    return niches


def one(n: dict, top: int, per_source: int, sources: int) -> dict:
    from arvantir.pipeline import run
    t = time.time()
    try:
        res = run(n.get("run_seed", n["seed"]), n["icp"], sources=sources, per_source=per_source, top=top)
    except Exception:  # noqa: BLE001 - eine Nische darf die anderen nicht stoppen
        traceback.print_exc()
        return {"key": n["key"], "error": True}
    res["key"], res["test_niche"], res["variant"] = n["key"], bool(n.get("test")), n.get("run_seed")
    out = RUNS / f"{n['key']}_{time.strftime('%H%M%S')}.json"
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[collect] {n['key']}: {len(res['leads'])} Leads, {time.time() - t:.0f} s -> {out.name}")
    return {"key": n["key"], "leads": len(res["leads"])}


def main() -> None:
    RUNS.mkdir(parents=True, exist_ok=True)
    want = [a for a in sys.argv[1:] if not a.startswith("--")]
    niches = [n for n in load_niches() if not want or n["key"] in want]
    if "--variants" in sys.argv:  # Zusatz-Seeds je Nische, gleicher ICP, mehr Firmen
        niches = [{**n, "run_seed": v} for n in niches for v in n.get("variants", [])]
    top = 150
    with ThreadPoolExecutor(max_workers=4) as pool:  # threads: log_pairs sperrt nur pro Prozess
        done = list(pool.map(lambda n: one(n, top, 120, 4), niches))
    print(json.dumps(done, ensure_ascii=False))


if __name__ == "__main__":
    main()
