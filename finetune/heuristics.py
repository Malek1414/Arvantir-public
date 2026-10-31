"""Regeln ohne Modell: schwache Labels (Fallback ohne LLM) und der Fixed-Weights-Baseline-Scorer.

Beide sind bewusst einfach. Schwache Labels sind als labeler="heuristic" markiert; ein Benchmark
auf schwachen Labels bevorzugt den Fixed-Weights-Scorer (gleiche Wörter), das steht in results.md.
"""
from __future__ import annotations

import re
from typing import Dict, Tuple

NICHE_WORDS = {
    "baeckereien_metzgereien": r"bäckerei|baeckerei|backstube|konditorei|brot|brötchen|metzgerei|fleischerei|wurst|schlachter|bäckermeister|fleischermeister|filiale",
    "waschanlagen": r"waschanlage|waschstraße|waschstrasse|autowäsche|autowaesche|portalwasch|sb-wasch|waschpark|car ?wash|fahrzeugpflege",
    "it_dienstleister": r"systemhaus|it-service|it-dienstleist|managed service|netzwerk|rechenzentrum|it-betreuung|it-sicherheit|cloud|microsoft partner|server",
    "aerzte_apotheken": r"praxis|arzt|ärzt|aerzt|apotheke|mvz|medizin|sprechstunde|patient|zahnarzt|allgemeinmedizin",
    "family_offices": r"family office|familienvermögen|vermögensverwaltung|unternehmerfamilie|private equity|venture|beteiligung|investor|limited partner|single family|multi family",
    "immobilien_asset_manager": r"asset management|asset manager|immobilien|kvg|kapitalverwaltung|portfolio|investment management|fondsmanagement|gewerbeimmobilie|bestandshalter",
    "steuerberater": r"steuerberat|kanzlei|buchhaltung|jahresabschluss|lohnbuchhaltung|finanzbuchhaltung|steuererklärung|datev",
    "maschinenbau": r"maschinenbau|sondermaschinen|zerspanung|cnc|fertigung|automatisierung|anlagenbau|präzision|dreh|fräs",
}
LEGAL = re.compile(r"\b(gmbh|ug|e\.k\.|ek|kg|ohg|gbr|ag|mbh|partg|e\.g\.|eg)\b", re.I)
DIRECTORY = re.compile(r"verzeichnis|branchenbuch|vergleichsportal|alle anbieter|liste der|top ?\d+|"
                       r"bewertungen von|gelbe seiten|11880|das örtliche|portal für|finden sie|anbieter in ", re.I)
BIG = re.compile(r"konzern|weltweit|international tätig|über \d{1,3}\.?\d{3} mitarbeiter|börsennotiert|"
                 r"standorten weltweit|in über \d+ ländern|franchise", re.I)
DE_HINT = re.compile(r"\b\d{5}\b|deutschland|berlin|münchen|hamburg|köln|frankfurt|stuttgart|"
                     r"düsseldorf|leipzig|dresden|hannover|nürnberg|bremen|\.de\b", re.I)
LIST_PAGE = re.compile(r"mitglied|aussteller|exhibitor|partner|verzeichnis|liste|innung|verband|register|"
                       r"vergleich|anbieter|datenbank|übersicht|betriebe", re.I)
NOT_LIST = re.compile(r"news|blog|artikel|stellenangebot|jobs?\b|karriere|pressemitteilung|ratgeber|"
                      r"wikipedia|impressum", re.I)


def _hits(key: str, text: str) -> int:
    rx = NICHE_WORDS.get(key)
    return len(set(m.group(0).lower() for m in re.finditer(rx, text, re.I))) if rx else 0


def weak_label(p: Dict) -> Tuple[int, str]:
    """0..3 plus kurzer Grund. Nur Fallback, wenn kein LLM-Lehrer da ist."""
    doc = p["doc"]
    if p["task"] == "source":
        lists, nots = len(LIST_PAGE.findall(doc[:600])), bool(NOT_LIST.search(doc[:300]))
        hits = _hits(p["niche"], doc)
        if lists >= 2 and hits and not nots:
            return 3, "Listenwörter + Nischenwort"
        if lists >= 1 and not nots:
            return 2, "Listenwort"
        if nots:
            return 0, "News/Blog/Jobs"
        return 1, "unklar"
    if p["origin"] == "directory":
        return 0, "Verzeichnisseite statt Firma"
    if p["origin"] == "cross":
        return (1, "fremde Nische, aber Nischenwörter") if _hits(p["niche"], doc) >= 2 else (0, "fremde Nische")
    if len(doc) < 120:
        return 1, "kein Profil"
    if DIRECTORY.search(doc[:400]):
        return 0, "sieht aus wie Verzeichnis"
    hits = _hits(p["niche"], doc)
    if BIG.search(doc):
        return 1, "Konzern/Kette"
    if hits >= 2:
        return 3, f"{hits} Nischenwörter"
    if hits == 1:
        return 2, "1 Nischenwort"
    return 1, "keine Nischenwörter"


def fixed_weights(p: Dict) -> float:
    """Baseline wie ein öffentlicher ICP-Scorer: feste Gewichte, Summe 0..100, Tier A-D."""
    doc = p["doc"]
    s = 0.0
    if p["task"] == "source":
        s += 50 * min(1, len(LIST_PAGE.findall(doc[:600])) / 2)
        s += 30 * min(1, _hits(p["niche"], doc) / 2)
        s += 20 * (not NOT_LIST.search(doc[:300]))
        return s
    s += 40 * min(1, _hits(p["niche"], doc) / 3)   # Branche
    s += 15 * bool(LEGAL.search(doc))               # echte Firma
    s += 15 * bool(DE_HINT.search(doc))             # Region
    s += 20 * (not DIRECTORY.search(doc[:400]))     # kein Verzeichnis
    s += 10 * (len(doc) > 300)                      # Profil vorhanden
    s -= 20 * bool(BIG.search(doc))                 # zu groß
    return max(0.0, s)


def tier(score: float) -> str:
    return "A" if score >= 75 else "B" if score >= 55 else "C" if score >= 35 else "D"
