"""repograph: Repo -> Website mit Graph (wie es gebaut ist) und Replay eines echten Laufs (wie es arbeitet).

    python -m repograph scan  <repo> [--out docs/graph/graph.json] [--exclude video,pitch]
    python -m repograph trace <repo> [--graph ...] [--out docs/graph/trace.json] -- <python -m paket args | skript.py args>
    python -m repograph build <repo> [--graph ...] [--trace ...] [--out docs/graph/index.html]
"""
import sys


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in ("scan", "trace", "build"):
        print(__doc__)
        sys.exit(1)
    cmd, rest = sys.argv[1], sys.argv[2:]
    if cmd == "scan":
        from .scan import main as run
    elif cmd == "trace":
        from .trace import main as run
    else:
        from .build import main as run
    run(rest)


if __name__ == "__main__":
    main()
