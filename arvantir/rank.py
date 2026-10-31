"""rank: Kandidaten gegen ICP / Beispiel-Lead re-ranken (Cross-Encoder, mMiniLM).

Pro Lead:
- score 0-100: Cross-Encoder auf (ICP-Text, Firmenprofil)
- reason + reason_source: der Profilsatz mit dem höchsten Score und seine Quelle
- confidence: Abstand zur Schwelle; nah an der Schwelle -> needs_human
Harte ICP-Filter (Region, Rechtsform, Größe) laufen vorher, nie als Gewicht im Modell.
Modell wechseln (z. B. das auf dem Spark trainierte) per RERANKER_MODEL.
"""
from __future__ import annotations

import os
import re
from typing import Dict, List

from searchify import score as rr_score

from .common import log_pairs, tier, to_100

THRESHOLD = 50     # ab hier "passt"
HUMAN_BAND = 12    # +-12 Punkte um die Schwelle -> Mensch entscheidet


def profile_text(c: Dict) -> str:
    """Firmenprofil aus allem, was harvest und enrich geliefert haben."""
    parts = [c.get("name", "")]
    for k in ("profile", "about", "raw_text"):
        if c.get(k):
            parts.append(str(c[k]))
    for k in ("city", "website"):
        if c.get(k):
            parts.append(f"{k}: {c[k]}")
    for k, v in (c.get("niche_fields") or {}).items():
        parts.append(f"{k}: {v}")
    return " | ".join(p for p in parts if p)[:2000]


def _sentences(c: Dict) -> List[Dict]:
    out = []
    for k in ("profile", "about", "raw_text"):
        for s in re.split(r"(?<=[.!?|])\s+", str(c.get(k) or "")):
            if 25 <= len(s) <= 300:
                out.append({"text": s, "source": c.get("profile_source") or c.get("source_url", "")})
    return out[:40]


def rank(cands: List[Dict], icp: str, niche: str = "") -> List[Dict]:
    if not cands:
        return []
    docs = [profile_text(c) for c in cands]
    scores = rr_score(icp, docs)
    # Basis-mMiniLM ist nicht absolut kalibriert: Score = Hälfte absolut (Logit-Kalibrierung),
    # Hälfte relativ (Rang im Lauf). Nach dem Fine-Tuning RR_MIX=1.0 setzen (nur absolut).
    mix = float(os.getenv("RR_MIX", "0.5"))
    order = sorted(range(len(scores)), key=lambda i: scores[i])
    pct = {i: (r / (len(scores) - 1) if len(scores) > 1 else 0.5) for r, i in enumerate(order)}
    out = []
    for idx, (c, d, s) in enumerate(zip(cands, docs, scores)):
        sc = round(mix * to_100(s) + (1 - mix) * 100 * pct[idx])
        sents = _sentences(c)
        if sents:
            best_i = max(range(len(sents)), key=lambda i: s_scores[i]) if (
                s_scores := rr_score(icp, [x["text"] for x in sents])) else 0
            reason, src = sents[best_i]["text"], sents[best_i]["source"]
        else:
            reason, src = d[:200], c.get("source_url", "")
        margin = abs(sc - THRESHOLD)
        gaps = [k for k, ok in (("website", c.get("website")), ("profil", c.get("profile")),
                                ("plz", c.get("postcode")), ("entscheider", c.get("decision_maker")),
                                ("email", c.get("email"))) if not ok]
        # Arvanas drei Stufen: belegt (Beleg aus der Firmenseite), wahrscheinlich, unbekannt (Datenlücke)
        konf = "belegt" if c.get("profile") and margin > HUMAN_BAND else \
               "wahrscheinlich" if c.get("profile") or c.get("raw_text") else "unbekannt"
        out.append({**c, "doc": d, "score": sc, "tier": tier(sc), "reason": reason, "reason_source": src,
                    "confidence": "hoch" if margin > 30 else "mittel" if margin > HUMAN_BAND else "niedrig",
                    "konfidenz": konf, "datenluecken": ", ".join(gaps),
                    "needs_human": margin <= HUMAN_BAND})
    out.sort(key=lambda x: -x["score"])
    log_pairs("lead", niche or icp[:60], icp, out, "doc")
    return out


def fetch_profiles(cands: List[Dict], limit: int = 60, workers: int = 8) -> List[Dict]:
    """Kurzprofil von der Startseite, falls enrich noch keins geliefert hat.

    Holt über harvest.fetch (prüft jede Weiterleitung auf öffentliche Hosts),
    Haupttext per Searchify extract_main_text.
    """
    from concurrent.futures import ThreadPoolExecutor

    from searchify import extract_main_text

    from .harvest import fetch

    def one(c: Dict) -> Dict:
        if not c.get("website") or c.get("profile"):
            return c
        html, final = fetch(c["website"], timeout=15)
        txt = re.sub(r"\s+", " ", (extract_main_text(html, final) or "") if html else "")[:1500]
        if txt:
            c["profile"], c["profile_source"] = txt, final
        return c

    head, tail = cands[:limit], cands[limit:]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        head = list(pool.map(one, head))
    return head + tail
