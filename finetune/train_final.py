"""Finales Produkt-Modell: Silber wie train.py PLUS Hand-Gold mit gedeckeltem Einfluss.

    .venv-spark/bin/python -m finetune.train_final              # -> models/arvantir-rr-v1-final
    .venv-spark/bin/python -m finetune.train_final --gold-cap=0.1 --gold-soft=0.8

Warum zwei Modelle:
- models/arvantir-rr-v1 (finetune.train) sieht KEINE Gold-Firmen. Nur dieses Modell wird gegen Gold
  gebenchmarkt, sonst wäre die Zahl im Video geschönt.
- dieses Modell nimmt Gold zusätzlich auf, damit das Wissen nicht verloren geht, aber gedeckelt:
  1. höchstens --gold-cap (Standard 10 %) aller Trainingszeilen sind Gold; mehr wird zufällig gekappt
  2. jede Gold-Zeile genau einmal, nie hochgewichtet oder dupliziert
  3. weiche Labels: passt 3 -> 0.9, vielleicht 1 -> 0.37, nein 0 -> 0.1 (bei --gold-soft=0.8),
     ein einzelner Klick schiebt das Modell also, statt es zu bestimmen
Trainingsbasis bleibt exakt data/pairs.jsonl (= Samis data/spark/pairs.jsonl) mit den Silber-Labels.
"""
from __future__ import annotations

import random
from typing import Dict, List, Optional, Tuple

from . import train as T
from .data import PAIRS, gold_labels, read_jsonl


def dataset_with_gold(holdout: Optional[str], mini: bool, seed: int = 13) -> Tuple[List[Dict], List[Dict], Dict]:
    """ALLE Paare aus data/pairs.jsonl (Samis Daten, auch die der Gold-Firmen) mit Silber-Label,
    die Gold-Paare selbst mit weichem Hand-Label, Gold-Anteil gedeckelt. Dev = 10 % der Firmen, nur Silber."""
    cap, soft = T.arg("gold-cap", 0.1), T.arg("gold-soft", 0.8)
    lab, gold = T.labels(), gold_labels()
    rows, gold_rows, skipped = [], [], {"no_label": 0, "holdout": 0}
    for p in read_jsonl(PAIRS):
        if holdout and (p["niche"] == holdout or p.get("doc_niche") == holdout):
            skipped["holdout"] += 1
            continue
        base = {"query": p["query"], "doc": p["doc"], "company_id": p["company_id"]}
        if p["pair_id"] in gold:
            g = gold[p["pair_id"]]
            gold_rows.append({**base, "label": soft * g["label"] / 3.0 + (1 - soft) / 2,
                              "labeler": f"gold:{g.get('who', '?')}"})
        elif p["pair_id"] in lab:
            rows.append({**base, "label": lab[p["pair_id"]]["label"] / 3.0, "labeler": lab[p["pair_id"]]["labeler"]})
        else:
            skipped["no_label"] += 1
    rng = random.Random(seed)
    if mini:
        rng.shuffle(rows)
        rows = rows[:300]
    companies = sorted({r["company_id"] for r in rows})
    rng.shuffle(companies)
    dev_c = set(companies[: max(1, len(companies) // 10)])
    train = [r for r in rows if r["company_id"] not in dev_c]
    dev = [r for r in rows if r["company_id"] in dev_c]
    max_gold = int(cap / (1 - cap) * len(train))  # Gold-Anteil an allen Trainingszeilen <= cap
    if len(gold_rows) > max_gold:
        gold_rows = rng.sample(gold_rows, max_gold)
    train += gold_rows
    info = {"skipped": skipped, "labelers": sorted({r["labeler"].split(":")[0] for r in train}),
            "companies": len(companies), "gold_rows": len(gold_rows),
            "gold_share": round(len(gold_rows) / max(1, len(train)), 3), "gold_cap": cap, "gold_soft": soft}
    print(f"[train_final] {len(train)} Trainingszeilen, davon {len(gold_rows)} Gold "
          f"({info['gold_share']:.1%}, Deckel {cap:.0%}, weiche Labels {soft}); Dev {len(dev)} (nur Silber)")
    return train, dev, info


def main() -> None:
    T.dataset = dataset_with_gold  # train_one ruft dataset() zur Laufzeit auf
    out = T.arg("out", None)
    if not out:
        import sys
        sys.argv.append("--out=models/arvantir-rr-v1-final")
    T.train_one(T.arg("holdout", None), "--mini" in __import__("sys").argv)


if __name__ == "__main__":
    main()
