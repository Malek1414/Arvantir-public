# Samis Teil: discover, harvest, rank (+ Website)

Vision: Arvantir = Palantir für Arvana. Searchify, zugeschnitten auf die Folien: die Dark-TAM-Engine plus eine Website im Searchify-Stil, die die Engine zeigt.

## Aufteilung

- **Sami-Terminal (dieses):** `arvantir/discover.py`, `arvantir/harvest.py`, `arvantir/rank.py` auf Basis von searchify-strukturdaten + tavily-clone (:8000)
- **Searchify-Terminal:** Quellen-Recherche zu allen 6 Nischen → `research/SOURCES.md` + `research/sources.json` (Auftrag: `research/PROMPT_SEARCHIFY.md`)
- **Malek:** normalize, darkcheck, enrich, channel, ui, Video (siehe BUILD_PLAN.md)

## Schnittstelle (damit wir parallel bauen)

- `discover(niche_or_seed) -> list[Source]` mit `{url, type, title, score, reason}`
- `harvest(source) -> list[Candidate]` mit `{name, website, city, raw: {...}, source_url}`
- `rank(candidates, niche_or_seed) -> list[Candidate + {score 0-100, reason, confidence, needs_human}]`
- Score 0 bis 100 wie auf Folie 02 (Company | Decision maker | ICP)

## Zeitplan

| Zeit | Was |
|---|---|
| 13:00–13:30 | discover: LLM-Suchbegriffe + searchify.search + Rerank "Liste vieler Firmen" |
| 13:30–14:15 | harvest: Rohmodus (HTML + Links), LLM schreibt Selector, Code paginiert; IT-Dienstleister aus 1 Partnerverzeichnis |
| 14:15–14:30 | Thin Slice mit Malek zusammenstecken, 1 Nische komplett |
| 14:30–15:30 | Quellen aus SOURCES.md als Seeds, PDF-Pfad, Asset Manager + Portfoliogröße, rank mit Begründung |
| 15:30–16:00 | Website-Seite für das Video, Überraschungs-Nische testen |
| 16:00 | Feature-Stopp |

Push nach jedem lauffähigen Schritt, `git pull --rebase` vorher.
