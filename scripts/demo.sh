#!/usr/bin/env bash
# Arvantir-Demo fürs Video: 1) Offline-Tests  2) echter Lauf  3) Clay-Export im Arvana-Format
#   scripts/demo.sh ["<Nische>"] ["<ICP-Sätze>"]     Standard: Waschanlagen, ICP aus research/icps.json
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
PY=.venv/bin/python; [ -x "$PY" ] || PY=python3
NICHE="${1:-Waschanlagen}"; ICP="${2:-}"
B=$'\033[1m'; G=$'\033[32m'; D=$'\033[2m'; N=$'\033[0m'

echo "${B}1/3 Offline-Tests${N} ${D}(harvest, SSRF, discover, rank, pipeline, adapters, web)${N}"
"$PY" -m pytest -q 2>&1 | tail -1

echo; echo "${B}2/3 Live-Lauf: ${NICHE}${N}"
LOG="$(mktemp)"; trap 'rm -f "$LOG"' EXIT
"$PY" -m arvantir run "$NICHE" "$ICP" > "$LOG" 2>&1 || { tail -20 "$LOG"; exit 1; }
RUN="$(grep -o -- '-> .*run_[0-9_]*\.json' "$LOG" | tail -1 | sed 's/^-> //' || true)"
[ -n "$RUN" ] || { tail -20 "$LOG"; echo "kein Lauf-Pfad gefunden" >&2; exit 1; }

echo; echo "${B}3/3 Export für Clay${N} ${D}(Spalten wie Arvanas leads_export.csv)${N}"
SPERR=(); [ -f sperrliste.txt ] && SPERR=(--sperrliste sperrliste.txt)
"$PY" -m adapters.clay "$RUN" ${SPERR[@]+"${SPERR[@]}"} | head -1

echo; "$PY" - "$RUN" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
B, G, D, N = "\033[1m", "\033[32m", "\033[2m", "\033[0m"
print(f"{B}Funnel{N} {D}({d['niche']}, {d['seconds']} s){N}")
top = max(s["n"] for s in d["funnel"]) or 1
for s in d["funnel"]:
    print(f"  {s['step']:<22} {s['n']:>5}  {G}{'█' * max(1, round(28 * s['n'] / top))}{N}")
leads = d["leads"]
tiers = {t: sum(l.get("tier") == t for l in leads) for t in "ABCD"}
print(f"\n{B}Tiers{N}  A {tiers['A']} · B {tiers['B']} · C {tiers['C']} · D {tiers['D']}"
      f"  ·  Mensch prüft: {sum(bool(l.get('needs_human')) for l in leads)}")
print(f"\n{B}Top 5{N}")
for l in leads[:5]:
    print(f"  {l['score']:>3} {l.get('tier', ''):<2} {l['name'][:38]:<38} {D}{(l.get('website') or '')[:34]}{N}")
    print(f"      {D}{(l.get('reason') or '')[:90]}{N}")
print(f"\n{D}Quellen: " + ", ".join(s["url"] for s in d["sources"]) + N)
PYEOF
