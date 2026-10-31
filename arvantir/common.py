"""Gemeinsame Helfer: Score-Skala, Paar-Log fürs Fine-Tuning, optionales LLM."""
from __future__ import annotations

import json
import math
import os
import threading
import time
from pathlib import Path
from typing import List, Optional

DATA = Path(__file__).resolve().parent.parent / "data"
DATA.mkdir(exist_ok=True)
_PAIRS = DATA / "rank_pairs.jsonl"
_lock = threading.Lock()


CAL_CENTER = float(os.getenv("RR_CAL_CENTER", "-1.5"))  # Logit, der Score 50 ergibt
CAL_SCALE = float(os.getenv("RR_CAL_SCALE", "1.0"))


def to_100(raw: float) -> int:
    """Cross-Encoder-Logit auf 0 bis 100, kalibriert (mMiniLM-Logits liegen grob bei -8 bis +1).

    Nach dem Fine-Tuning werden RR_CAL_CENTER/RR_CAL_SCALE aus dem Dev-Set neu gesetzt.
    """
    return round(100 / (1 + math.exp(-(raw - CAL_CENTER) / CAL_SCALE)))


def tier(score: int) -> str:
    """Arvanas Tier-Grenzen aus dem icp-scorer: A 80-100, B 60-79, C 40-59, D < 40."""
    return "A" if score >= 80 else "B" if score >= 60 else "C" if score >= 40 else "D"


def log_pairs(task: str, niche: str, query: str, rows: List[dict], doc_key: str) -> None:
    """Jedes bewertete Paar für FINETUNE_PLAN.md mitschreiben."""
    ts = time.time()
    with _lock, _PAIRS.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps({
                "task": task, "niche": niche, "query": query,
                "doc": r.get(doc_key, ""), "url": r.get("url", ""),
                "score": r.get("score"), "ts": ts,
            }, ensure_ascii=False) + "\n")


def llm_json(prompt: str, system: str = "", timeout: float = 40) -> Optional[dict]:
    """JSON vom LLM, oder None wenn kein Key gesetzt ist oder der Aufruf scheitert."""
    if not os.getenv("OPENAI_API_KEY"):
        return None
    try:
        from openai import OpenAI
        client = OpenAI(timeout=timeout)
        r = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": system or "Antworte nur mit JSON."},
                      {"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return json.loads(r.choices[0].message.content)
    except Exception as e:  # noqa: BLE001 - LLM ist optional, Engine läuft ohne weiter
        print(f"[llm] übersprungen: {type(e).__name__}")
        return None
