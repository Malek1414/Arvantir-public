"""Datenqualität: Müll-Paare in den Silber-Labels auf 0 setzen, nachvollziehbar und gegen Gold geprüft.

    .venv/bin/python -m finetune.clean            # liest data/labels_silver.orig.jsonl (sonst .jsonl), schreibt .jsonl

Befund vom 31.10. (Gold-Labels von Malek + Claude): in den Nischen Bäckereien, Maschinenbau und Steuerberater
ist keiner der eigenen Leads eine echte Firma der Nische (Kurzlinks, Erotik-/Wettseiten, Portale wie Thomasnet,
Wohnungsanzeigen, österreichische Kanzleien bei einem Deutschland-ICP), die Heuristik gab ihnen trotzdem 1 bis 3.

Regeln (nur herabstufen auf 0, nie heraufstufen; jede Änderung trägt ihre Regel):
- host:     bekannte Nicht-Firmen-Hosts (Kurzlinks, Wörterbücher, Social, Portale, Spam)
- adult:    Erotik/Glücksspiel in URL oder Textanfang
- boiler:   leere Seite, JavaScript-/Bot-Wand, Default-/Fehlerseite, Text < 60 Zeichen, überwiegend CJK-Zeichen
- listing:  Wohnungsanzeige statt Firma (nur Leads)
- portal:   Portal/Behörde/Kartendienst-Rahmenseite als Lead (116117, BaFin, OSM-Copyright); als Quelle bleiben sie
- region:   Länderdomain außerhalb des ICP-Gebiets (ICP "Deutschland" -> nur .de; "DACH" -> .de/.at/.ch/.li)
- osm_only: Lead ist nur ein OpenStreetMap-Eintrag (Betreiber, Standortzahl, Kontakt unbekannt) -> höchstens 1
            ("vielleicht"), gleiche Regel wie beim Gold-Labeln (unbekannt ist nicht erfüllt, aber auch nicht "passt")
Prüfung: Übereinstimmung Silber vs Gold vorher/nachher und jede Gold-"passt"/"vielleicht"-Zeile, die eine Regel trifft.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from urllib.parse import urlparse

from .data import DATA, PAIRS, gold_labels, read_jsonl

SILVER = DATA / "labels_silver.jsonl"
ORIG = DATA / "labels_silver.orig.jsonl"
REPORT = DATA / "clean_report.json"

JUNK_HOSTS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "example.com", "freethesaurus.com", "thefreedictionary.com",
    "trustpilot.com", "tiktok.com", "x.ai", "twitter.com", "x.com", "facebook.com", "instagram.com",
    "youtube.com", "pinterest.com", "roadtrippers.com", "mapbox.com", "prepscholar.com", "kaskus.co.id",
    "zline0.com", "avtub.wiki", "myavlive.com", "xnxx.com", "pornhub.com", "fanduel.com", "mahjongspelen.nl",
    "stackoverflow.com", "speedtest.net", "mdpi.com", "sec.gov", "shareowneronline.com", "equiniti.com",
    "webinar.net", "thomasnet.com", "xometry.com", "cinfin.com", "kleinreparatur.de", "wikipedia.org",
}
PORTAL_HOSTS = {"116117.de", "bafin.de"}
ADULT = re.compile(r"\b(porn\w*|xxx|xnxx|sex|jav|hentai|nude|nsfw|escort|camgirl|onlyfans|casino|sportsbook|betting)\b", re.I)
BOILER = re.compile(r"enable javascript|javascript (is )?required|javascript erforderlich|apache2? .{0,30}default page|"
                    r"403 forbidden|access denied|seite nicht gefunden|page not found|are you human", re.I)
LISTING = re.compile(r"\b\d+([,.]\d+)?-Zimmer|Zimmer-(Erdgeschoss)?[Ww]ohnung|\bzur Miete\b")
CJK = re.compile(r"[぀-ヿ㐀-鿿가-힯]")
# Länderregel nur für echte 2-Buchstaben-Länderdomains; generisch genutzte ccTLDs (.ac .io .ai .co .me ...) und
# alle neuen gTLDs (.ventures .vanguard ...) zählen nie als "Ausland"
GENERIC_CC = {"ac", "ai", "io", "co", "me", "tv", "vc", "ly", "gg", "to", "fm", "sh", "so", "cc", "ws", "eu"}
DE_OK = {"de"}
DACH_OK = {"de", "at", "ch", "li"}
AT_CITY = {"tirol", "wien", "swiss"}  # gTLDs mit eindeutigem Nicht-DE-Ort


def host(url: str) -> str:
    h = (urlparse(url or "").hostname or "").lower()
    return h[4:] if h.startswith("www.") else h


def _hit(h: str, hosts: set) -> bool:
    return any(h == x or h.endswith("." + x) for x in hosts)


def rule_for(p: dict) -> str:
    """Name der ersten greifenden Regel, sonst ''."""
    h, doc, lead = host(p.get("url", "")), (p.get("doc") or "").strip(), p["task"] == "lead"
    head = f"{p.get('url', '')} {doc[:400]}"
    if _hit(h, JUNK_HOSTS):
        return "host"
    if ADULT.search(head):
        return "adult"
    if len(doc) < 60 or BOILER.search(doc[:600]) or (doc and len(CJK.findall(doc)) / len(doc) > 0.3):
        return "boiler"
    if not lead:
        return ""
    if LISTING.search(doc[:400]):
        return "listing"
    if _hit(h, PORTAL_HOSTS) or (h.endswith("openstreetmap.org") and doc.startswith("© OpenStreetMap")):
        return "portal"
    if h.endswith("openstreetmap.org"):
        return "osm_only"  # Kartendatensatz statt Firmen-Website: höchstens "vielleicht"
    tld = h.rsplit(".", 1)[-1] if "." in h else ""
    q = p.get("query", "")
    foreign_cc = len(tld) == 2 and tld not in GENERIC_CC
    if "DACH" in q or "DE, AT" in q:
        if foreign_cc and tld not in DACH_OK:
            return "region"
    elif "Deutschland" in q or "deutsch" in q.lower():
        if (foreign_cc and tld not in DE_OK) or tld in AT_CITY:
            return "region"
    return ""


def agreement(lab: dict, gold: dict) -> dict:
    """Silber vs Gold auf denselben Paaren: passt (>=2) gegen nicht passt, und mittlerer Abstand auf 0..3."""
    keys = [k for k in gold if k in lab]
    if not keys:
        return {"n": 0}
    hit = sum((lab[k]["label"] >= 2) == (gold[k]["label"] >= 2) for k in keys)
    mae = sum(abs(lab[k]["label"] - gold[k]["label"]) for k in keys) / len(keys)
    return {"n": len(keys), "fit_agreement": round(hit / len(keys), 3), "mean_abs_error_0_3": round(mae, 3)}


def main() -> None:
    src = ORIG if ORIG.exists() else SILVER
    rows = read_jsonl(src)
    if not ORIG.exists():
        ORIG.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    before = {r["pair_id"]: r for r in rows if "label" in r}
    pairs = {p["pair_id"]: p for p in read_jsonl(PAIRS)}
    after, changed = {}, Counter()
    per_niche = Counter()
    for pid, r in before.items():
        p = pairs.get(pid)
        rule = rule_for(p) if p else ""
        cap = 1 if rule == "osm_only" else 0
        if rule and r["label"] > cap:
            after[pid] = {**r, "label": cap, "labeler": f"{r['labeler']}+clean:{rule}",
                          "reason": f"clean:{rule} (vorher {r['label']})"}
            changed[rule] += 1
            per_niche[f"{p['task']}:{p['niche']}"] += 1
        else:
            after[pid] = r
    gold = gold_labels()
    false_flags = [{"pair_id": k, "gold": gold[k]["gold"], "who": gold[k].get("who"), "rule": rule_for(pairs[k]),
                    "url": pairs[k].get("url", ""), "name": pairs[k].get("name", "")}
                   for k in gold if k in pairs and rule_for(pairs[k])
                   and gold[k]["label"] > (1 if rule_for(pairs[k]) == "osm_only" else 0)]
    report = {"source": src.name, "pairs_labeled": len(before), "changed_total": sum(changed.values()),
              "changed_by_rule": dict(changed), "changed_by_group": dict(per_niche.most_common()),
              "gold_agreement_before": agreement(before, gold), "gold_agreement_after": agreement(after, gold),
              "gold_fit_or_maybe_flagged": false_flags}
    SILVER.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in after.values()), encoding="utf-8")
    REPORT.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "gold_fit_or_maybe_flagged"}, indent=1, ensure_ascii=False))
    print(f"Gold passt/vielleicht von einer Regel getroffen: {len(false_flags)}")
    for f in false_flags:
        print("  ", f)


if __name__ == "__main__":
    main()
