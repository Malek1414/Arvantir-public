"""Benchmark: feste Gewichte vs LLM pointwise vs mMiniLM Basis vs mMiniLM fine-tuned.

    .venv/bin/python -m finetune.bench                         # nimmt Gold, sonst Silber-Fallback
    .venv/bin/python -m finetune.bench --models=models/arvantir-rr-v1 --llm-max=300 --no-llm

Testmenge:
- gold   data/gold.jsonl (Hand-Labels, nie im Training). Fine-tuned = models/arvantir-rr-v1
         (die Gold-Firmen hat train.py ausgeschlossen); gibt es ein LONO-Modell der Nische, läuft
         es zusätzlich als "fine-tuned (Nische ungesehen)".
- silver Fallback ohne Gold: Silber-Labels der Nischen, für die ein LONO-Modell existiert
         (models/arvantir-rr-v1-lono-<nische>); nur das zählt als ehrlich. Steht so in results.md.
Metriken je Anfrage-Gruppe (Task x Nische), dann gemittelt: NDCG@10, MRR, Kendall tau,
Übereinstimmung passt/nein, Anteil "needs a human" bei 95 % Präzision auf dem Rest, ms pro Lead.
Ausgabe: bench/results.md, bench/results.json, bench/chart.png
"""
from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path
from typing import Callable, Dict, List

from scipy.stats import kendalltau

from .data import MAIN_NICHES, PAIRS, ROOT, gold_labels, labels, read_jsonl
from .heuristics import fixed_weights
from .train import BASE, arg

BENCH = ROOT / "bench"
FIT = 2  # Label >= 2 heißt "passt" (Gold: passt=3, vielleicht=1, nein=0)


# ---------- Metriken ----------
def ndcg(scores: List[float], rels: List[float], k: int = 10) -> float:
    order = sorted(range(len(scores)), key=lambda i: -scores[i])[:k]
    dcg = sum((2 ** rels[i] - 1) / math.log2(r + 2) for r, i in enumerate(order))
    ideal = sorted(rels, reverse=True)[:k]
    idcg = sum((2 ** g - 1) / math.log2(r + 2) for r, g in enumerate(ideal))
    return dcg / idcg if idcg else float("nan")


def mrr(scores: List[float], rels: List[float]) -> float:
    order = sorted(range(len(scores)), key=lambda i: -scores[i])
    return next((1 / (r + 1) for r, i in enumerate(order) if rels[i] >= FIT), 0.0)


def human_share(scores: List[float], fits: List[bool], target: float = 0.95) -> float:
    """Anteil, der zum Menschen muss: oben automatisch 'passt' und unten automatisch 'nein',
    jeweils so viele wie möglich bei >= 95 % Präzision. Der Rest dazwischen ist needs_human."""
    n = len(scores)
    if not n:
        return float("nan")
    order = sorted(range(n), key=lambda i: -scores[i])
    acc = hit = 0
    for k, i in enumerate(order, 1):
        hit += fits[i]
        if hit / k >= target:
            acc = k
    rej = neg = 0
    for k, i in enumerate(reversed(order), 1):
        neg += not fits[i]
        if neg / k >= target:
            rej = k
    return max(0.0, 1 - min(n, acc + rej) / n)


def mean(xs: List[float]) -> float:
    xs = [x for x in xs if x == x]
    return sum(xs) / len(xs) if xs else float("nan")


# ---------- Systeme ----------
def ce_scorer(path: str) -> Callable[[List[Dict]], List[float]]:
    from sentence_transformers.cross_encoder import CrossEncoder
    model = CrossEncoder(path, max_length=384)

    def f(ps: List[Dict]) -> List[float]:
        raw = model.predict([(p["query"], p["doc"]) for p in ps], batch_size=32)
        return [1 / (1 + math.exp(-float(x))) if not 0 <= float(x) <= 1 else float(x) for x in raw]
    return f


def llm_scorer():
    from .label_teacher import _client, grade, model_name
    client = _client()
    if not client:
        return None, None

    def f(ps: List[Dict]) -> List[float]:
        from concurrent.futures import ThreadPoolExecutor
        def one(p):  # pointwise: ein Lead pro Aufruf, wie ein LLM-Scorer im Produkt
            r = grade(client, p["query"], [p["doc"]])
            return (r[0]["label"] / 3) if r else 0.5
        with ThreadPoolExecutor(max_workers=12) as pool:
            return list(pool.map(one, ps))
    return f, model_name()


def evaluate(name: str, f, groups: Dict[str, List[Dict]], fit_at: float, parallel_ms: bool = False) -> Dict:
    per, all_s, all_fit, n, secs = [], [], [], 0, 0.0
    for g, ps in groups.items():
        t = time.time()
        s = f(ps)
        secs += time.time() - t
        n += len(ps)
        rels = [p["label"] for p in ps]
        fits = [r >= FIT for r in rels]
        tau = kendalltau(s, rels).statistic if len(set(rels)) > 1 and len(set(s)) > 1 else float("nan")
        per.append({"group": g, "n": len(ps), "ndcg10": ndcg(s, rels), "mrr": mrr(s, rels), "tau": tau,
                    "agree": mean([float((x >= fit_at) == y) for x, y in zip(s, fits)])})
        all_s += s
        all_fit += fits
    return {"system": name, "n": n, "ndcg10": mean([p["ndcg10"] for p in per]),
            "mrr": mean([p["mrr"] for p in per]), "tau": mean([p["tau"] for p in per]),
            "agree": mean([p["agree"] for p in per]), "needs_human": human_share(all_s, all_fit),
            "ms_per_lead": 1000 * secs / max(1, n), "per_group": per}


# ---------- Ablauf ----------
def test_set() -> tuple:
    pairs = {p["pair_id"]: p for p in read_jsonl(PAIRS)}
    gold = gold_labels()
    if len(gold) >= 30 and "--silver" not in sys.argv:
        rows = [{**pairs[k], "label": v["label"]} for k, v in gold.items() if k in pairs]
        return "gold", rows
    lab = labels()
    lono = [k for k in MAIN_NICHES if (ROOT / f"models/arvantir-rr-v1-lono-{k}").exists()]
    keep = set(arg("test-niches", ",".join(lono or MAIN_NICHES)).split(","))
    cap = arg("per-group", 150)
    rows, count = [], {}
    for k, p in pairs.items():
        if k in lab and p["niche"] in keep:
            g = f"{p['task']}:{p['niche']}"
            if count.get(g, 0) < cap:
                count[g] = count.get(g, 0) + 1
                rows.append({**p, "label": lab[k]["label"], "labeler": lab[k]["labeler"]})
    return "silver", rows


def main() -> None:
    BENCH.mkdir(exist_ok=True)
    mode, rows = test_set()
    if not rows:
        sys.exit("Keine Testpaare (weder data/gold.jsonl noch Silber-Labels).")
    groups: Dict[str, List[Dict]] = {}
    for p in rows:
        groups.setdefault(f"{p['task']}:{p['niche']}", []).append(p)
    labelers = sorted({p.get("labeler", "gold") for p in rows})
    print(f"[bench] Test: {mode}, {len(rows)} Paare, {len(groups)} Gruppen, Labels von {labelers}")

    results = [evaluate("Feste Gewichte (Tier A-D)", lambda ps: [fixed_weights(p) for p in ps], groups, 55)]
    llm_note = "nicht gelaufen (kein OPENAI_API_KEY / OPENAI_BASE_URL)"
    if "--no-llm" not in sys.argv:
        f, mname = llm_scorer()
        if f:
            cap = arg("llm-max", 300)
            sub, left = {}, cap
            for g, ps in groups.items():  # gleichmäßig über Gruppen kappen, Kosten begrenzen
                take = ps[: max(5, cap // max(1, len(groups)))]
                if left <= 0:
                    break
                sub[g], left = take[:left], left - len(take[:left])
            from .label_teacher import usage
            u0 = usage()
            r = evaluate(f"LLM pointwise ({mname})", f, sub, 2 / 3)
            u = usage()
            tin, tout = u["in"] - u0["in"], u["out"] - u0["out"]
            r["cost_per_1000"] = round((tin * 0.15 + tout * 0.6) / 1e6 / max(1, r["n"]) * 1000, 3)
            r["note"] = f"auf {r['n']} Paaren (gekappt), Preis gpt-4o-mini angenommen"
            llm_note = r["note"]
            if any(str(l).startswith(f"llm:{mname}") for l in labelers):
                r["note"] += "; ZIRKULÄR: dasselbe LLM hat die Silber-Testlabels vergeben"
            results.append(r)
    results.append(evaluate("mMiniLM Basis", ce_scorer(BASE), groups, 0.5))

    ft_models = [m for m in arg("models", "models/arvantir-rr-v1").split(",") if (ROOT / m).exists()]
    for m in ft_models:
        r = evaluate(f"mMiniLM fine-tuned ({Path(m).name})", ce_scorer(str(ROOT / m)), groups, 0.5)
        meta = ROOT / m / "arvantir_train.json"
        if mode == "silver" and meta.exists() and not json.loads(meta.read_text()).get("holdout"):
            r["note"] = "hat diese Nischen im Training gesehen (nur Silber-Fallback)"
        results.append(r)
    lono = {g: ps for g, ps in groups.items()
            if (ROOT / f"models/arvantir-rr-v1-lono-{g.split(':', 1)[1]}").exists()}
    if lono:  # jede Nische mit dem Modell, das sie nie gesehen hat
        cache: Dict[str, Callable] = {ps[0]["niche"]: ce_scorer(str(ROOT / f"models/arvantir-rr-v1-lono-{ps[0]['niche']}"))
                                      for ps in lono.values()}  # vorab laden, Ladezeit nicht in ms/Lead

        def per_niche(ps: List[Dict]) -> List[float]:
            k = ps[0]["niche"]
            if k not in cache:
                cache[k] = ce_scorer(str(ROOT / f"models/arvantir-rr-v1-lono-{k}"))
            return cache[k](ps)
        r = evaluate("mMiniLM fine-tuned, Nische ungesehen (LONO)", per_niche, lono, 0.5)
        r["note"] = f"{len(lono)} Gruppen, je Nische das Modell ohne diese Nische"
        results.append(r)
    for r in results:
        r.setdefault("cost_per_1000", 0.0)

    write(mode, rows, labelers, results, llm_note)


def write(mode: str, rows: List[Dict], labelers: List[str], results: List[Dict], llm_note: str) -> None:
    (BENCH / "results.json").write_text(json.dumps({"mode": mode, "pairs": len(rows), "labelers": labelers,
                                                    "results": results}, indent=1, ensure_ascii=False))
    f = lambda x, d=3: "–" if x != x else f"{x:.{d}f}"  # noqa: E731
    lines = [f"# Re-Ranker-Benchmark ({time.strftime('%d.%m.%Y %H:%M')})", "",
             f"Testmenge: **{mode}**, {len(rows)} Paare, Labels von {', '.join(labelers)}.", ""]
    if mode == "silver":
        lines += ["> Silber-Fallback: keine Hand-Labels. Ehrlich ist nur die LONO-Zeile (Nische nie im Training). "
                  "Sind die Labels `heuristic`, bevorzugt das die festen Gewichte (gleiche Wortlisten).", ""]
    lines += ["| System | NDCG@10 | MRR | Kendall tau | Übereinstimmung passt/nein | needs a human (95 % Präz.) "
              "| ms pro Lead | Kosten / 1.000 Leads | Paare |", "|---|---|---|---|---|---|---|---|---|"]
    for r in results:
        lines.append(f"| {r['system']} | {f(r['ndcg10'])} | {f(r['mrr'])} | {f(r['tau'])} | {f(r['agree'] * 100, 0)} % "
                     f"| {f(r['needs_human'] * 100, 0)} % | {f(r['ms_per_lead'], 1)} | {r['cost_per_1000']:.2f} $ | {r['n']} |")
    notes = [f"- {r['system']}: {r['note']}" for r in results if r.get("note")]
    if not any("LLM" in r["system"] for r in results):
        notes.append(f"- LLM pointwise: {llm_note}")
    lines += ["", *notes, "", "## Je Gruppe (NDCG@10)", "",
              "| Gruppe | " + " | ".join(r["system"] for r in results) + " |",
              "|---|" + "---|" * len(results)]
    groups = sorted({g["group"] for r in results for g in r["per_group"]})
    for g in groups:
        cells = [next((f(x["ndcg10"]) for x in r["per_group"] if x["group"] == g), "–") for r in results]
        lines.append(f"| {g} | " + " | ".join(cells) + " |")
    lines += ["", "![Benchmark](chart.png)", ""]
    (BENCH / "results.md").write_text("\n".join(lines), encoding="utf-8")
    chart(results)
    print("\n".join(lines[:8 + len(results)]))
    print(f"-> {BENCH / 'results.md'}")


def chart(results: List[Dict]) -> None:
    """Drei kleine Panels, je eine Achse: NDCG@10, Übereinstimmung, ms pro Lead (log)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    names = [r["system"].replace(" (", "\n(") for r in results]
    hi = ["fine-tuned" in r["system"] for r in results]
    col = ["#2a78d6" if h else "#b9b8b2" for h in hi]  # Akzent nur für unser Modell
    panels = [("NDCG@10", [r["ndcg10"] for r in results], "{:.2f}", False),
              ("Übereinstimmung passt/nein", [r["agree"] * 100 for r in results], "{:.0f} %", False),
              ("ms pro Lead (log)", [max(0.01, r["ms_per_lead"]) for r in results], "{:.1f}", True)]
    fig, axes = plt.subplots(1, 3, figsize=(15, 0.9 * len(results) + 1.6), sharey=True)
    for ax, (title, vals, fmt, log) in zip(axes, panels):
        ys = range(len(vals))
        ax.barh(ys, [0 if v != v else v for v in vals], color=col, height=0.6)
        for y, v in zip(ys, vals):
            ax.text(v if v == v else 0, y, "  " + ("–" if v != v else fmt.format(v)), va="center",
                    fontsize=10, color="#0b0b0b")
        ax.set_title(title, loc="left", fontsize=12, color="#0b0b0b")
        if log:
            ax.set_xscale("log")
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
        ax.spines["bottom"].set_color("#d6d5d0")
        ax.tick_params(colors="#52514e", labelsize=9)
        ax.grid(axis="x", color="#ecebe7", linewidth=0.8)
        ax.set_axisbelow(True)
        if not log:
            ax.set_xlim(0, 1.15 if title.startswith("NDCG") else 115)
    axes[0].set_yticks(range(len(names)), names, fontsize=10, color="#0b0b0b")
    axes[0].invert_yaxis()
    fig.patch.set_facecolor("#fcfcfb")
    for ax in axes:
        ax.set_facecolor("#fcfcfb")
    fig.tight_layout()
    fig.savefig(BENCH / "chart.png", dpi=160)
    plt.close(fig)


if __name__ == "__main__":
    main()
