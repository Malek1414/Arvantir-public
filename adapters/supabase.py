"""Arvantir-Lauf -> Supabase (Schema: adapters/supabase.sql).

    python -m adapters.supabase data/run_130450.json --dry-run   # nur zeigen, was geschrieben würde
    python -m adapters.supabase --latest                          # neuesten Lauf einspielen

Schreibt über die PostgREST-API von Supabase. Braucht in .env:
    SUPABASE_URL=https://<projekt>.supabase.co
    SUPABASE_SERVICE_ROLE_KEY=...      # nur serverseitig, nie ins Frontend

Reihenfolge wie im Buch: erst raw_pages (System of Record, nur INSERT),
dann die abgeleiteten Tabellen per Upsert. Alles idempotent: derselbe Lauf
zweimal eingespielt ergibt denselben Stand.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

from .clay import domain, entity_key, latest_run, run_id, split_legal

CONF = {"hoch": 0.9, "mittel": 0.6, "niedrig": 0.3}

# Firmenfelder, die als field_values mit Provenienz landen (Schlüssel im Lead -> Feldname)
COMPANY_FIELDS = {"website": "website", "phone": "phone", "email": "email", "fax": "fax",
                  "vat_id": "vat_id", "street": "street", "postcode": "postcode", "city": "city",
                  "employees": "employees", "locations": "locations", "founded": "founded"}


def _conf(v, default: float = 0.5) -> float:
    if isinstance(v, (int, float)):
        return max(0.0, min(1.0, float(v)))
    return CONF.get(str(v or "").lower(), default)


def _prov(c: Dict, field: str) -> Dict:
    """Provenienz eines Felds: aus c['provenance'][field] (enrich), sonst Herkunft des Leads."""
    p = (c.get("provenance") or {}).get(field) or {}
    default_src = c.get("profile_source") if field == "website" else c.get("detail_url") or c.get("source_url")
    return {"source_url": p.get("source") or p.get("source_url") or default_src,
            "method": p.get("method") or ("harvest" if field in ("postcode", "city") else "resolve"
                                          if field == "website" else "unknown"),
            "confidence": _conf(p.get("confidence"), _conf(c.get(f"{field}_confidence"), 0.5)),
            "evidence": p.get("evidence")}


def build(run: Dict, run_id: str) -> Dict[str, List[Dict]]:
    out: Dict[str, List[Dict]] = {k: [] for k in
                                  ("runs", "raw_pages", "companies", "company_sources",
                                   "people", "field_values", "lead_scores")}
    out["runs"].append({"id": run_id, "seed": run.get("seed", ""), "niche": run.get("niche"),
                        "icp": run.get("icp"), "funnel": run.get("funnel", []),
                        "seconds": run.get("seconds"), "model": os.getenv("RERANKER_MODEL")})
    seen: Dict[str, Dict] = {}
    now = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    for c in run.get("leads", []):
        key, kind = entity_key(c)
        srcs = list(dict.fromkeys(c.get("sources") or ([c["source_url"]] if c.get("source_url") else [])))
        if key in seen:  # Duplikat: nur seine Fundstellen übernehmen (Signal "mehrere Listen")
            first = seen[key]
            for s in srcs:
                if s not in first["_srcs"]:
                    first["_srcs"].append(s)
                    out["company_sources"].append({"entity_key": key, "source_url": s,
                                                   "source_type": c.get("source_type"), "run_id": run_id})
            first["row"]["source_count"] = max(first["row"]["source_count"], len(first["_srcs"]))
            continue
        base, lf = split_legal(c.get("name", ""))
        out["companies"].append({
            "entity_key": key, "key_kind": kind, "name": c.get("name", ""),
            "legal_form": c.get("legal_form") or lf or None,
            "domain": c.get("domain") or domain(c.get("website", "")) or None,
            "postcode": c.get("postcode") or None, "city": c.get("city") or None,
            "country": c.get("country") or None,
            "register_court": c.get("register_court") or None,
            "register_number": c.get("register_number") or None,
            "in_ai_ark": c.get("in_ai_ark") if isinstance(c.get("in_ai_ark"), bool) else None,
            "source_count": c.get("source_count") or max(1, len(srcs)), "last_seen": now})
        seen[key] = {"row": out["companies"][-1], "_srcs": srcs}
        for s in srcs:
            out["company_sources"].append({"entity_key": key, "source_url": s,
                                           "source_type": c.get("source_type"), "run_id": run_id})
        # Rohbeobachtungen: der Listeneintrag und der Profiltext, so wie geholt
        if c.get("raw_text"):
            out["raw_pages"].append({"url": c.get("detail_url") or c.get("source_url", ""),
                                     "kind": "list_entry", "body": c["raw_text"], "run_id": run_id})
        if c.get("profile"):
            out["raw_pages"].append({"url": c.get("profile_source") or c.get("website", ""),
                                     "kind": "profile", "body": c["profile"], "run_id": run_id})
        for src_key, field in COMPANY_FIELDS.items():
            v = c.get(src_key)
            if v in (None, "", [], {}):
                continue
            out["field_values"].append({"entity_key": key, "person_id": None, "field": field,
                                        "value": str(v), **_prov(c, src_key)})
        dm = c.get("decision_maker")
        if dm:
            dm = dm if isinstance(dm, dict) else {"name": dm}
            name = dm.get("name") or dm.get("full_name")
            if name:
                out["people"].append({"entity_key": key, "full_name": name,
                                      "role": dm.get("role") or dm.get("title"),
                                      "linkedin": dm.get("linkedin"),
                                      "_email": dm.get("email"),
                                      "_email_prov": {"source_url": dm.get("source") or c.get("profile_source"),
                                                      "method": dm.get("method") or "unknown",
                                                      "confidence": _conf(dm.get("email_confidence"), 0.5)}})
        if c.get("score") not in (None, ""):
            out["lead_scores"].append({
                "run_id": run_id, "entity_key": key, "score": int(float(c["score"])),
                "confidence": c.get("confidence"),
                "needs_human": str(c.get("needs_human")).lower() == "true",
                "reason": c.get("reason"), "reason_source": c.get("reason_source"),
                "channel": c.get("channel"), "draft": c.get("draft")})
    return out


class Rest:
    def __init__(self, url: str, key: str):
        if urlparse(url).scheme != "https" and not url.startswith("http://localhost"):
            raise SystemExit("SUPABASE_URL muss https sein")
        self.base, self.key = url.rstrip("/") + "/rest/v1/", key

    def _post(self, path: str, body, prefer: str = ""):
        headers = {"apikey": self.key, "Authorization": f"Bearer {self.key}",
                   "Content-Type": "application/json"}
        if prefer:
            headers["Prefer"] = prefer
        req = urllib.request.Request(self.base + path, method="POST", headers=headers,
                                     data=json.dumps(body, ensure_ascii=False).encode())
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:  # Fehlertext von PostgREST zeigen, nie den Key
            raise SystemExit(f"{path}: HTTP {e.code} {e.read()[:300].decode(errors='ignore')}")

    def upsert(self, table: str, rows: List[Dict], on_conflict: str, ignore: bool = False) -> List[Dict]:
        if not rows:
            return []
        pref = "resolution=ignore-duplicates" if ignore else "resolution=merge-duplicates"
        return self._post(f"{table}?on_conflict={on_conflict}", rows,
                          f"{pref},return=representation") or []

    def rpc(self, fn: str, args: Dict) -> int:
        return int(self._post(f"rpc/{fn}", args) or 0)


def push(data: Dict[str, List[Dict]], rest: Rest) -> Dict[str, int]:
    n: Dict[str, int] = {}
    n["runs"] = len(rest.upsert("runs", data["runs"], "id"))
    n["raw_pages"] = len(rest.upsert("raw_pages", data["raw_pages"], "url,content_sha256", ignore=True))
    n["companies"] = rest.rpc("upsert_companies", {"rows": data["companies"]})
    n["company_sources"] = len(rest.upsert("company_sources", data["company_sources"],
                                           "entity_key,source_url"))
    people = [{k: v for k, v in p.items() if not k.startswith("_")} for p in data["people"]]
    saved = rest.upsert("people", people, "entity_key,full_name")
    ids = {(p["entity_key"], p["full_name"]): p["id"] for p in saved}
    fv = list(data["field_values"])
    for p in data["people"]:
        pid = ids.get((p["entity_key"], p["full_name"]))
        if pid and p.get("_email"):
            fv.append({"entity_key": p["entity_key"], "person_id": pid, "field": "email",
                       "value": p["_email"], "evidence": None, **p["_email_prov"]})
    n["people"] = len(saved)
    n["field_values"] = len(rest.upsert("field_values", fv,
                                        "entity_key,person_id,field,value,source_url", ignore=True))
    n["lead_scores"] = len(rest.upsert("lead_scores", data["lead_scores"], "run_id,entity_key"))
    return n


def main(argv: Optional[List[str]] = None) -> None:
    ap = argparse.ArgumentParser(description="Arvantir-Lauf nach Supabase")
    ap.add_argument("run", nargs="?")
    ap.add_argument("--latest", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="nichts senden, Zahlen + Beispiel zeigen")
    a = ap.parse_args(argv)
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    path = Path(a.run) if a.run else latest_run() if a.latest else None
    if not path:
        ap.error("Lauf-Datei angeben oder --latest")
    data = build(json.loads(path.read_text(encoding="utf-8")), run_id(path))
    print(" · ".join(f"{k}: {len(v)}" for k, v in data.items()))
    if a.dry_run:
        print(json.dumps({k: v[:1] for k, v in data.items()}, ensure_ascii=False, indent=1)[:2500])
        return
    url, key = os.getenv("SUPABASE_URL", ""), os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        sys.exit("SUPABASE_URL und SUPABASE_SERVICE_ROLE_KEY in .env setzen (siehe adapters/README.md)")
    print("geschrieben:", push(data, Rest(url, key)))


if __name__ == "__main__":
    main()
