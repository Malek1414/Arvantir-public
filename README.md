# Arvantir

> Public snapshot of our private dev repo from the GTM Hackathon Berlin (31 Oct 2026). Internal notes, the kickoff recording, the pitch workspace and the scraped training data are left out.

**GTM Hackathon Berlin, Halloween Edition** (hosted by Arvana × GTMengineer.dev), 31 Oct 2026.

Arvantir (a Palantir for Arvana) is a **Dark TAM engine** built on Sami's Searchify. Give it any niche and it finds the companies that no lead database has, normalizes them, proves they're not in AI Ark, finds the decision maker from public sources, and suggests how to reach them.

> Arvana's rule for the jury: *"Don't show us the leads. Show the engine that produces it."*

## Repo graph

How this repo is built and how a real run moves through it, as an interactive page: **https://malek1414.github.io/Arvantir-public/graph/**

- **How it's built:** layers, modules, imports and the 9-step product flow, from static analysis (Python AST, no LLM, nothing guessed).
- **How it runs:** replay of a recorded `python -m arvantir run "Waschanlagen"` from OpenTelemetry spans: items in and out, time and web requests per stage.

Rebuild it (`repograph/` works on any Python repo; output goes to `docs/graph/`):

```
.venv/bin/python -m repograph scan  . --exclude video,pitch,site
ARVANTIR_REAL_BROWSER=0 .venv/bin/python -m repograph trace . -- -m arvantir run "Waschanlagen"
.venv/bin/python -m repograph build . --theme dark --accent "#e3a43b" --back "../"
```

Design and limits: [docs/superpowers/specs/2026-10-31-repograph-design.md](docs/superpowers/specs/2026-10-31-repograph-design.md)

## Deadlines

- **12:30**: team + track locked via https://tally.so/r/perokb
- **17:00**: submit a **2-minute video walkthrough**; jury review 17:00–17:30
- Judging, 25% each: Business Impact · Tech · Works end-to-end · Pitch

## Repo layout

```
context/
  CHALLENGE.md        all of Arvana's challenges, from the slides + kickoff talk
  DARK_TAM_PLAN.md    our engine design, build order, pitch outline
  FINETUNE_PLAN.md    fine-tuning the mMiniLM re-ranker on Arvana (DGX Spark) + benchmark
  BUILD_PLAN.md       module-by-module build plan: adapting the scrape side, getting the most from enrichment, timeline
  ARVANA.md           who Arvana is, how they make money, what their CTO wants
  EVENT.md            schedule, links, credits
  slides/             photos of the kickoff slides
```

## Tests

`.venv/bin/python -m pytest` runs the offline suite in about 10 seconds, with no network, no LLM and no writes to `data/`. It uses real list pages saved in `tests/fixtures/` (eco members, Shopware partners, waschanlagen-deutschland hub/state/city pages, BaFin table) and covers harvest (block detection, hubs, pagination, navigation noise, SSRF), discover, rank (tiers A-D, needs_human band, confidence, data gaps), the pipeline funnel, CSV formula escaping, the Clay/Supabase adapters and the web server's host check. The `model` test uses the real mMiniLM from the local cache and is skipped without it. `python -m pytest -m live` does a real "Waschanlagen" run (≥ 50 leads, tiers spread, < 120 s). `scripts/demo.sh ["<niche>"]` runs tests, a live run and the Clay export, then prints the funnel and the top 5 for the video. Tests marked `xfail` are known bugs; each one turns red as soon as it is fixed, so the marker can be removed.

## Team

- Malek Hassan ([@Malek1414](https://github.com/Malek1414))
- Sami ([@sami-mag07](https://github.com/sami-mag07))
