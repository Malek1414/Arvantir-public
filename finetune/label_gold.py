"""Gold-Labels von Hand: 50 Paare je Nische, passt / vielleicht / nein. Nur Test, nie Training.

    .venv/bin/python -m finetune.label_gold --who=sami          # öffnet http://127.0.0.1:8765
    .venv/bin/python -m finetune.label_gold --who=malek --niche=waschanlagen,family_offices

Tasten: 1 passt, 2 vielleicht, 3 nein, z zurück. Jeder Klick wird sofort in data/gold.jsonl
gespeichert, Neustart macht beim nächsten offenen Paar weiter. Die Stichprobe liegt fest in
data/gold_sample.jsonl (gleich für alle), damit train.py diese Firmen aus dem Training nimmt.
"""
from __future__ import annotations

import json
import random
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .data import GOLD, GOLD_SAMPLE, PAIRS, read_jsonl, write_jsonl

PER_NICHE, OWN_SHARE = 50, 40  # 40 eigene Leads über die ganze Score-Spanne + 10 harte Negative


def make_sample(seed: int = 11) -> list:
    rng = random.Random(seed)
    pairs = [p for p in read_jsonl(PAIRS) if p["task"] == "lead"]
    out = []
    for key in sorted({p["niche"] for p in pairs}):
        own = sorted([p for p in pairs if p["niche"] == key and p["origin"] == "own"],
                     key=lambda p: -(p.get("base_score") or 0))
        step = max(1, len(own) / OWN_SHARE)
        pick = [own[int(i * step)] for i in range(min(OWN_SHARE, len(own)))]
        neg = [p for p in pairs if p["niche"] == key and p["origin"] in ("cross", "directory")]
        pick += rng.sample(neg, min(PER_NICHE - len(pick), len(neg)))
        rng.shuffle(pick)
        out += pick
    return out


PAGE = """<!doctype html><html lang="de"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Gold-Labels</title><style>
:root{--bg:#f6f6f4;--fg:#1c1f24;--mut:#6b6f76;--card:#fff;--line:#e2e2de;--ok:#1f8a4c;--mid:#b07d10;--no:#b3261e}
@media (prefers-color-scheme:dark){:root{--bg:#141517;--fg:#ececea;--mut:#9a9da3;--card:#1d1f22;--line:#2c2f33}}
body{background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,sans-serif;margin:0;padding:16px}
main{max-width:860px;margin:0 auto}.bar{display:flex;justify-content:space-between;color:var(--mut);font-size:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;margin:12px 0}
.icp{font-size:14px;color:var(--mut)}.doc{white-space:pre-wrap;max-height:50vh;overflow:auto}
a{color:inherit}.btns{display:flex;gap:8px;flex-wrap:wrap}button{flex:1;min-width:120px;font:inherit;padding:14px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--fg);cursor:pointer}
button.ok{border-color:var(--ok)}button.mid{border-color:var(--mid)}button.no{border-color:var(--no)}
</style><main><div class="bar"><span id="who"></span><span id="pos"></span></div>
<div class="card"><div class="icp"><b id="niche"></b><div id="icp"></div></div></div>
<div class="card"><b id="name"></b> <a id="url" target="_blank" rel="noopener noreferrer"></a><div class="doc" id="doc"></div></div>
<div class="btns"><button class="ok" data-l="passt">1 passt</button><button class="mid" data-l="vielleicht">2 vielleicht</button>
<button class="no" data-l="nein">3 nein</button><button data-l="undo">z zurück</button></div></main>
<script>
let items=[],i=0;const $=id=>document.getElementById(id);
function show(){while(i<items.length&&items[i].gold)i++;const done=items.filter(x=>x.gold).length;
$('pos').textContent=done+' / '+items.length+' gelabelt';if(i>=items.length){$('doc').textContent='Fertig, danke.';return}
const p=items[i];$('niche').textContent=p.niche;$('icp').textContent=p.query;$('name').textContent=p.name||'';
$('url').textContent=p.url||'';$('url').href=/^https?:\\/\\//.test(p.url||'')?p.url:'#';$('doc').textContent=p.doc}
async function label(l){if(l==='undo'){let j=i-1;while(j>=0&&!items[j].gold)j--;if(j<0)return;
await fetch('/label',{method:'POST',body:JSON.stringify({pair_id:items[j].pair_id,gold:null})});items[j].gold=null;i=j;return show()}
if(i>=items.length)return;const p=items[i];await fetch('/label',{method:'POST',body:JSON.stringify({pair_id:p.pair_id,gold:l})});p.gold=l;i++;show()}
document.querySelectorAll('button').forEach(b=>b.onclick=()=>label(b.dataset.l));
addEventListener('keydown',e=>{const m={'1':'passt','2':'vielleicht','3':'nein','z':'undo'}[e.key];if(m)label(m)});
fetch('/items').then(r=>r.json()).then(d=>{items=d.items;$('who').textContent='Labeler: '+d.who;show()});
</script>"""


def main() -> None:
    args = dict(a[2:].split("=", 1) for a in sys.argv[1:] if a.startswith("--") and "=" in a)
    who = args.get("who", "sami")
    if not GOLD_SAMPLE.exists() or "--resample" in sys.argv:
        n = write_jsonl(GOLD_SAMPLE, make_sample())
        print(f"Stichprobe: {n} Paare -> {GOLD_SAMPLE}")
    sample = read_jsonl(GOLD_SAMPLE)
    if args.get("niche"):
        keep = set(args["niche"].split(","))
        sample = [p for p in sample if p["niche"] in keep]
    lock = threading.Lock()

    def current() -> dict:
        state = {}
        for r in read_jsonl(GOLD):
            if r.get("who") == who:
                state[r["pair_id"]] = r.get("gold")
        return state

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):  # ruhig bleiben
            pass

        def _send(self, body: bytes, ctype: str) -> None:
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/items":
                st = current()
                items = [{k: p.get(k) for k in ("pair_id", "niche", "query", "doc", "name", "url")}
                         | {"gold": st.get(p["pair_id"])} for p in sample]
                return self._send(json.dumps({"who": who, "items": items}, ensure_ascii=False).encode(),
                                  "application/json")
            return self._send(PAGE.encode(), "text/html; charset=utf-8")

        def do_POST(self):
            if self.path != "/label":
                return self.send_error(404)
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)) or 0) or b"{}")
            ok_ids = {p["pair_id"] for p in sample}
            if body.get("pair_id") not in ok_ids or body.get("gold") not in ("passt", "vielleicht", "nein", None):
                return self.send_error(400)
            with lock, GOLD.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"pair_id": body["pair_id"], "gold": body["gold"], "who": who,
                                    "ts": time.time()}) + "\n")
            return self._send(b"{}", "application/json")

    port = int(args.get("port", 8765))
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    url = f"http://127.0.0.1:{port}"
    print(f"{len(sample)} Paare für {who}: {url}  (Strg+C beendet)")
    if "--no-open" not in sys.argv:
        webbrowser.open(url)
    srv.serve_forever()


if __name__ == "__main__":
    main()
