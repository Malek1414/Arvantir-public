"""Silber-Labels: LLM-Lehrer bewertet jedes Paar 0..3 mit kurzem Grund.

    .venv/bin/python -m finetune.label_teacher                  # OpenAI, Key aus .env
    OPENAI_BASE_URL=http://localhost:8000/v1 TEACHER_MODEL=nvidia/... \
        .venv/bin/python -m finetune.label_teacher              # Nemotron/Qwen per vLLM auf dem Spark
    .venv/bin/python -m finetune.label_teacher --heuristic      # ohne LLM: schwache Labels

Ohne OPENAI_API_KEY (und ohne OPENAI_BASE_URL) fällt es auf schwache Labels zurück,
jede Zeile trägt labeler="heuristic" bzw. "llm:<modell>". Setzt dort fort, wo es aufgehört hat.
Liest data/pairs.jsonl (vorher `python -m finetune.data`), schreibt data/labels_silver.jsonl.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional

from dotenv import load_dotenv

from .data import GOLD_SAMPLE, PAIRS, ROOT, SILVER, read_jsonl
from .heuristics import weak_label

load_dotenv(ROOT / ".env")

SYSTEM = (
    "Du bist Lead-Qualifizierer bei Arvana, einer deutschen Outbound-Agentur. Du bewertest, wie gut ein "
    "Dokument zu einer Anfrage passt, so wie ein erfahrener Arvana-Mitarbeiter von Hand sortiert. "
    "Antworte nur mit JSON."
)
RULES = """Skala:
3 = passt klar (genau die gesuchte Art Firma bzw. eine echte Liste vieler solcher Firmen)
2 = passt wahrscheinlich, kleine Zweifel (Größe, Region oder Schwerpunkt nicht ganz sicher)
1 = eher nicht (Nachbarbranche, zu groß/klein, Kette statt Einzelbetrieb, zu wenig Information)
0 = passt nicht (andere Branche, Verzeichnis-/Portalseite statt Firma, tote oder leere Seite, News/Blog/Jobs)

Regeln für Leads (Anfrage = ICP):
- harte Kriterien aus dem ICP (Land, Größe, Inhaberführung, Ausschlüsse) gehen vor
- eine Verzeichnis-, Vergleichs- oder Verbandsseite ist nie ein Lead (0)
- Konzern-Zentrale oder Kette, wenn der ICP Einzelbetriebe will: höchstens 1
- leeres oder sehr kurzes Profil: höchstens 1
Regeln für Quellen (Anfrage = "Liste vieler ... Firmen"):
- 3/2 nur für Seiten, die viele Firmen der Nische auflisten: Mitgliederliste, Aussteller, Partnerverzeichnis, Register, Vergleichsportal
- einzelne Firmenseite, News, Blog, Jobbörse: 0"""

_usage = {"in": 0, "out": 0, "calls": 0}
_ulock = threading.Lock()


def _client():
    if not (os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_BASE_URL")):
        return None
    from openai import OpenAI
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY") or "local", timeout=60)


def model_name() -> str:
    return os.getenv("TEACHER_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"


def grade(client, query: str, docs: List[str]) -> Optional[List[Dict]]:
    """Ein Aufruf, mehrere Dokumente zur selben Anfrage. None bei Fehler."""
    items = "\n\n".join(f"[{i}] {d[:1500]}" for i, d in enumerate(docs))
    prompt = (f"{RULES}\n\nAnfrage:\n{query}\n\nDokumente:\n{items}\n\n"
              'Gib JSON: {"grades": [{"i": 0, "label": 0-3, "reason": "max 12 Wörter"}, ...]} '
              f"für alle {len(docs)} Dokumente.")
    for attempt in range(3):
        try:
            r = client.chat.completions.create(
                model=model_name(), temperature=0, response_format={"type": "json_object"},
                messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}])
            if r.usage:
                with _ulock:
                    _usage["in"] += r.usage.prompt_tokens
                    _usage["out"] += r.usage.completion_tokens
                    _usage["calls"] += 1
            g = {int(x["i"]): x for x in json.loads(r.choices[0].message.content)["grades"]}
            return [{"label": max(0, min(3, int(g[i]["label"]))), "reason": str(g[i].get("reason", ""))[:120]}
                    for i in range(len(docs))]
        except Exception as e:  # noqa: BLE001 - Netz/JSON-Fehler: nochmal, dann auslassen
            if attempt == 2:
                print(f"[teacher] Batch übersprungen: {type(e).__name__}")
            time.sleep(1.5 * (attempt + 1))
    return None


def usage() -> Dict:
    return dict(_usage)


def main() -> None:
    pairs = read_jsonl(PAIRS)
    if not pairs:
        sys.exit("Keine Paare. Erst: .venv/bin/python -m finetune.data")
    gold_ids = {r["pair_id"] for r in read_jsonl(GOLD_SAMPLE)}  # Gold nie ins Training
    done = {r["pair_id"] for r in read_jsonl(SILVER)}
    todo = [p for p in pairs if p["pair_id"] not in done and p["pair_id"] not in gold_ids]
    limit = next((int(a.split("=")[1]) for a in sys.argv if a.startswith("--limit=")), None)
    todo = todo[:limit] if limit else todo
    client = None if "--heuristic" in sys.argv else _client()
    print(f"{len(todo)} Paare offen ({len(done)} schon gelabelt), Lehrer: "
          f"{'llm:' + model_name() if client else 'heuristic (KEIN LLM, schwache Labels)'}")
    lock = threading.Lock()
    f = SILVER.open("a", encoding="utf-8")

    def emit(p: Dict, label: int, reason: str, who: str) -> None:
        with lock:
            f.write(json.dumps({"pair_id": p["pair_id"], "label": label, "reason": reason,
                                "labeler": who}, ensure_ascii=False) + "\n")

    if not client:
        for p in todo:
            emit(p, *weak_label(p), "heuristic")
        f.close()
        print(f"fertig: {len(todo)} schwache Labels -> {SILVER}")
        return

    groups: Dict[str, List[Dict]] = {}
    for p in todo:
        groups.setdefault(p["query"], []).append(p)
    batches = [g[i:i + 8] for g in groups.values() for i in range(0, len(g), 8)]
    t0, n = time.time(), [0]

    def run(batch: List[Dict]) -> None:
        res = grade(client, batch[0]["query"], [p["doc"] for p in batch])
        if res is None:
            return
        for p, r in zip(batch, res):
            emit(p, r["label"], r["reason"], f"llm:{model_name()}")
        with lock:
            n[0] += len(batch)
            if n[0] % 400 < len(batch):
                f.flush()
                print(f"  {n[0]}/{len(todo)} in {time.time() - t0:.0f} s, Tokens {_usage}")

    with ThreadPoolExecutor(max_workers=int(os.getenv("TEACHER_WORKERS", "12"))) as pool:
        list(pool.map(run, batches))
    f.close()
    print(f"fertig: {n[0]} Labels in {time.time() - t0:.0f} s, Tokens {_usage} -> {SILVER}")


if __name__ == "__main__":
    main()
