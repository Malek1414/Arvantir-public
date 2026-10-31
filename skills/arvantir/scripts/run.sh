#!/usr/bin/env bash
# Dark TAM Finder: Arvantir-Lauf + Export im Arvana-Format.
#   run.sh "<Nische>" "<ICP-Sätze>" [--sperrliste datei] [--bekannt datei] [--min-tier B] [--webhook]
# ARVANTIR_HOME zeigt auf das Repo (Standard: drei Ebenen über diesem Skript).
set -euo pipefail

if [ $# -lt 1 ]; then
  echo 'Aufruf: run.sh "<Nische>" "<ICP-Sätze>" [--sperrliste datei] [--bekannt datei] [--min-tier B] [--webhook]' >&2
  exit 1
fi

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOME_DIR="${ARVANTIR_HOME:-$(cd "$HERE/../../.." && pwd)}"
NICHE="$1"; shift
ICP="${1:-}"; [ $# -gt 0 ] && shift

# Relative Pfade (Sperrliste, Export) vom Aufrufort aus auflösen, bevor wir wechseln
ARGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --sperrliste|--bekannt) ARGS+=("$1" "$(cd "$(dirname "$2")" && pwd)/$(basename "$2")"); shift 2 ;;
    *) ARGS+=("$1"); shift ;;
  esac
done

PY="$HOME_DIR/.venv/bin/python"
[ -x "$PY" ] || PY="python3"

cd "$HOME_DIR"
LOG="$(mktemp)"; trap 'rm -f "$LOG"' EXIT
"$PY" -m arvantir run "$NICHE" "$ICP" | tee "$LOG"
# genau diesen Lauf exportieren, nicht den neuesten (andere Läufe können parallel schreiben)
RUN="$(grep -o -- '-> .*run_[0-9_]*\.json' "$LOG" | tail -1 | sed 's/^-> //' || true)"
[ -n "$RUN" ] || { echo "kein Lauf-Pfad in der Ausgabe gefunden" >&2; exit 1; }
"$PY" -m adapters.clay "$RUN" ${ARGS[@]+"${ARGS[@]}"}
