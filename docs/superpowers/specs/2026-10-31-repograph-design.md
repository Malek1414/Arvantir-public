# repograph: show how a repo is built and how it runs

**Status:** v1 built and tested on Arvantir, published 31 Oct 2026: https://malek1414.github.io/Arvantir-public/graph/

## Goal
Point it at any repo ("x repo" that builds "x product"). It produces a self-contained website with two views:
1. **How it's built:** layers, modules, dependencies, entry points and the product flow, from static analysis.
2. **How it runs:** a replay of a real, recorded run through the product flow, from OpenTelemetry spans.

Staged roadmap (decided): **showcase first** (pitch/client explainer), then **developer onboarding** (search, file view), then **live monitor** (stream the same spans instead of replaying a file).

## Decisions
| Question | Decision | Why |
|---|---|---|
| How is the repo understood? | Deterministic static analysis (Python AST); LLM only for labels later | Reproducible, nothing invented; research: gitdiagram/DeepWiki let an LLM guess structure and can hallucinate edges |
| Where does runtime data come from? | OpenTelemetry spans | Industry standard; the same spans can later go to Jaeger/Tempo/Langfuse or a live view |
| Code changes in the target repo? | None | Functions are wrapped at runtime; httpx auto-instrumentation records web requests |
| Graph rendering | Cytoscape.js 3.34.4 + ELK 0.12.1 (+ cytoscape-elk 2.3.0) from jsDelivr | MIT, native layer groups, built-in animation, no build step (research of 13 libraries) |
| Output | One HTML file with the data inline | Works offline, on GitHub Pages, in any static host |

Licences checked: GitNexus (PolyForm Noncommercial) and GPL tools (Sourcetrail, pyan) are used for ideas only, nothing copied.

## Components (`repograph/`)
- `scan.py`: repo -> `graph.json`. Layer = top-level folder, module = .py file, edges = internal imports plus "dynamic" (string argument naming a sibling module, e.g. `_optional("normalize", ...)`). Product flow = a function calling >= 4 different internal modules in a row; the order in the source is the order shown. Text = first docstring line.
- `trace.py`: runs the repo's own command under an OpenTelemetry TracerProvider (in-memory exporter). Every function of the scanned modules is wrapped by a span (also where it was imported by name). Attributes: node, function, items_in/items_out (list/dict lengths), error status. httpx CLIENT spans become web requests, credited to the outermost product-flow stage in the parent chain; `ThreadingInstrumentor` carries the span context into worker threads. A stage called inside another stage (enrich -> channel per company) is marked `in: <stage>` and counts for that stage in the replay. Output: per-module/function aggregates plus a timeline of all web requests, flow calls, nested stage calls and spans >= 15 ms (cap 4,000).
- `build.py` + `template.html`: graph + trace -> HTML. Options: `--theme dark|light`, `--accent`, `--back`, `--title` to match a host site.

## Data contracts
- `graph.json`: `repo{name,commit,remote,generated_at}`, `layers[]`, `nodes[]{id,label,layer,path,loc,doc,entry,functions[],classes[]}`, `edges[]{source,target,kind:import|dynamic,names[]}`, `flows[]{id,steps[]{node,call,line}}`
- `trace.json`: `run{command,repo,commit,started_at,duration_ms,exit}`, `nodes{id:{calls,ms,errors,items_in,items_out,functions{}}}`, `http{requests,errors,ms,hosts{},status{},fail_hosts{},by_node{}}`, `spans[]{kind,node,fn,start_ms,dur_ms,items_in,items_out,status,flow|code,by}`

## Error handling
- Modules that can't be imported are skipped in the trace (and listed in the log), never fatal.
- A failed run is still written (`run.exit = "error: ..."`) and shown in the site.
- Inline JSON escapes `</` so repo text can't break out of the script tag; the page escapes all repo text in the HTML.

## Testing
`tests/test_repograph.py`: scan on a mini repo (imports, `from . import x`, dynamic loading, flow order, docstrings, entry point), span wrapper (items in/out, error status), nested stage calls, build (escaping, theme/accent). Plus a manual check in Chrome: both views, replay, side panel, phone width (390 px, no sideways scroll).

## Known limits (v1)
- Python only (tree-sitter for more languages is the next step).
- Cached work is fast and makes no requests (e.g. signals answered from its cache), so the replay shows each run as it happened, not a typical run.
- The replay shows one recorded run; the live monitor needs an OTLP exporter and a streaming view.
