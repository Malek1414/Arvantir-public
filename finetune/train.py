"""Re-Ranker fine-tunen: mMiniLM Cross-Encoder auf Silber-Labels, Task A (Leads) + B (Quellen) gemischt.

    .venv/bin/python -m finetune.train                       # alle Nischen -> models/arvantir-rr-v1
    .venv/bin/python -m finetune.train --holdout=family_offices   # ohne diese Nische -> ...-lono-family_offices
    .venv/bin/python -m finetune.train --lono                # Leave-one-niche-out über alle 6 Hauptnischen
    .venv/bin/python -m finetune.train --mini                # Rauchtest auf dem Mac (300 Paare, wenige Schritte)

Optionen: --lr=2e-5 --epochs=2 --batch=32 --max-len=384 --out=models/NAME
Regeln aus FINETUNE_PLAN.md: Gold-Firmen nie im Training, Split nach Firma, Labels 0..3 -> 0..1 (BCE),
Eval alle 200 Schritte auf Silber-Dev, bestes Checkpoint wird gespeichert.
"""
from __future__ import annotations

import json
import random
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .data import GOLD_SAMPLE, MAIN_NICHES, PAIRS, ROOT, labels, read_jsonl

BASE = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
MODELS = ROOT / "models"


def arg(name: str, default):
    for a in sys.argv[1:]:
        if a.startswith(f"--{name}="):
            return type(default)(a.split("=", 1)[1]) if default is not None else a.split("=", 1)[1]
    return default


def dataset(holdout: Optional[str], mini: bool, seed: int = 13) -> Tuple[List[Dict], List[Dict], Dict]:
    pairs = read_jsonl(PAIRS)
    lab = labels()
    gold_companies = {p["company_id"] for p in read_jsonl(GOLD_SAMPLE)}
    rows, skipped = [], {"no_label": 0, "gold_company": 0, "holdout": 0}
    for p in pairs:
        if p["pair_id"] not in lab:
            skipped["no_label"] += 1
            continue
        if p["company_id"] in gold_companies:
            skipped["gold_company"] += 1
            continue
        # Holdout: weder Anfragen dieser Nische noch Firmen aus dieser Nische sehen
        if holdout and (p["niche"] == holdout or p.get("doc_niche") == holdout):
            skipped["holdout"] += 1
            continue
        rows.append({"query": p["query"], "doc": p["doc"], "label": lab[p["pair_id"]]["label"] / 3.0,
                     "company_id": p["company_id"], "labeler": lab[p["pair_id"]]["labeler"]})
    rng = random.Random(seed)
    if mini:
        rng.shuffle(rows)
        rows = rows[:300]
    companies = sorted({r["company_id"] for r in rows})
    rng.shuffle(companies)
    dev_c = set(companies[: max(1, len(companies) // 10)])
    train = [r for r in rows if r["company_id"] not in dev_c]
    dev = [r for r in rows if r["company_id"] in dev_c]
    labelers = sorted({r["labeler"] for r in rows})
    return train, dev, {"skipped": skipped, "labelers": labelers, "companies": len(companies)}


def train_one(holdout: Optional[str], mini: bool) -> Path:
    import torch
    from datasets import Dataset
    from sentence_transformers.cross_encoder import (CrossEncoder, CrossEncoderTrainer,
                                                     CrossEncoderTrainingArguments)
    from sentence_transformers.cross_encoder.losses import BinaryCrossEntropyLoss

    name = arg("out", None) or ("models/arvantir-rr-mini" if mini else
                                f"models/arvantir-rr-v1{'-lono-' + holdout if holdout else ''}")
    out = (ROOT / name) if not Path(name).is_absolute() else Path(name)
    train, dev, info = dataset(holdout, mini)
    if len(train) < 20:
        sys.exit(f"Zu wenig Trainingspaare ({len(train)}). Erst finetune.data und finetune.label_teacher laufen lassen.")
    if any(l.startswith("heuristic") for l in info["labelers"]):
        print("ACHTUNG: Training enthält schwache Heuristik-Labels (kein LLM-Lehrer).")
    cuda = torch.cuda.is_available()
    bf16 = cuda and torch.cuda.is_bf16_supported()
    epochs, lr, bs = arg("epochs", 1 if mini else 2), arg("lr", 2e-5), arg("batch", 8 if mini else 32)
    print(f"[train] {out.name}: {len(train)} train / {len(dev)} dev, holdout={holdout}, "
          f"device={'cuda' if cuda else 'mps' if torch.backends.mps.is_available() else 'cpu'}, bf16={bf16}")

    model = CrossEncoder(BASE, num_labels=1, max_length=arg("max-len", 128 if mini else 384))
    cols = lambda rs: Dataset.from_dict({"query": [r["query"] for r in rs],  # noqa: E731
                                         "doc": [r["doc"] for r in rs],
                                         "label": [float(r["label"]) for r in rs]})
    steps = 10 if mini else 200
    args = CrossEncoderTrainingArguments(
        output_dir=str(MODELS / "_ckpt" / out.name), num_train_epochs=epochs,
        per_device_train_batch_size=bs, per_device_eval_batch_size=bs * 2, learning_rate=lr,
        warmup_ratio=0.1, bf16=bf16, eval_strategy="steps", eval_steps=steps, save_strategy="steps",
        save_steps=steps, save_total_limit=2, load_best_model_at_end=True,
        metric_for_best_model="eval_loss", greater_is_better=False, logging_steps=max(5, steps // 4),
        max_steps=30 if mini else -1, report_to="none", seed=13,
        dataloader_num_workers=0 if not cuda else 4)
    trainer = CrossEncoderTrainer(model=model, args=args, train_dataset=cols(train),
                                  eval_dataset=cols(dev), loss=BinaryCrossEntropyLoss(model))
    t0 = time.time()
    trainer.train()
    model.save_pretrained(str(out))
    meta = {"base": BASE, "holdout": holdout, "train_pairs": len(train), "dev_pairs": len(dev),
            "epochs": epochs, "lr": lr, "batch": bs, "bf16": bf16, "seconds": round(time.time() - t0, 1),
            "eval_loss": trainer.evaluate().get("eval_loss"), **info,
            "trained_at": time.strftime("%Y-%m-%d %H:%M")}
    (out / "arvantir_train.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False))
    print(f"[train] fertig in {meta['seconds']} s, eval_loss {meta['eval_loss']:.4f} -> {out}")
    return out


def main() -> None:
    mini = "--mini" in sys.argv
    if "--lono" in sys.argv:
        for key in arg("niches", ",".join(MAIN_NICHES)).split(","):
            train_one(key, mini)
        return
    train_one(arg("holdout", None), mini)


if __name__ == "__main__":
    main()
