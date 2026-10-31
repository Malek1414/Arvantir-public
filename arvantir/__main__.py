"""python -m arvantir discover "IT-Dienstleister"  (weitere Schritte folgen)"""
import json
import sys
import time

from .discover import discover
from .harvest import harvest, resolve_websites
from .pipeline import run


def main() -> None:
    if len(sys.argv) >= 3 and sys.argv[1] == "run":
        icp = sys.argv[3] if len(sys.argv) > 3 and not sys.argv[3].startswith("--") else ""
        res = run(sys.argv[2], icp)
        print(f"\n{res['niche']}: {len(res['leads'])} Leads in {res['seconds']} s -> {res['file']}")
        for x in res["leads"][:15]:
            print(f"{x['score']:>3} {x['confidence']:<8} {x['name'][:40]:<40} {x.get('website', '')[:40]}")
        return
    if len(sys.argv) < 3 or sys.argv[1] not in ("discover", "harvest"):
        print('Aufruf: python -m arvantir discover "<Nische oder Beispiel-URL>"\n'
              '        python -m arvantir harvest "<Listen-URL>"')
        sys.exit(1)
    if sys.argv[1] == "harvest":
        t = time.time()
        r = harvest(sys.argv[2])
        c = resolve_websites(r["candidates"], limit=30)
        print(f"{len(c)} Kandidaten | Block {r['block']} | {r['pages']} Seiten | {time.time() - t:.1f} s")
        for e in c[:30]:
            print(f"  {e['name'][:45]:<45} {e.get('website', '')[:45]:<45} {e['postcode']} {e['city']}")
        if "--json" in sys.argv:
            print(json.dumps(c, ensure_ascii=False, indent=1))
        return
    t = time.time()
    res = discover(sys.argv[2])
    print(f"Nische: {res['niche']} | {len(res['queries'])} Suchanfragen | "
          f"{res['candidates_total']} Treffer | {time.time() - t:.1f} s")
    for s in res["sources"]:
        print(f"{s['score']:>3}  {s['type']:<18} {s['url']}")
    if "--json" in sys.argv:
        print(json.dumps(res, ensure_ascii=False, indent=1))


main()
