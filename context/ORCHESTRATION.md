# Orchestrierung 31.10. ab 13:15

**Ziel:** Arvantir = Searchify, zugeschnitten auf Arvana. Searchify selbst (searchify-l: search, extract, rerank) bleibt unverändert so gut wie es ist. Arvantir ist eine GTM-Schicht darüber: aus öffentlichen Daten den Dark TAM finden und Arvanas Probleme lösen (veraltete Daten, zu wenige Leads, kein Standard für "qualifiziert", Handsortierung). Re-Ranker (mMiniLM, später auf Arvana fine-tuned) ist der Kern des Rankings. Die Architektur passt sich an Arvanas Arbeitsweise an (Claude Code Skills, Clay, Supabase).

## Wer macht was (nur die eigenen Dateien anfassen)

| Terminal | Auftrag | Dateien |
|---|---|---|
| aa (Sami, Join) | discover, harvest, rank, pipeline; führt alles zusammen, testet, pusht | `arvantir/discover.py harvest.py rank.py pipeline.py common.py __main__.py` |
| Malek | normalize, darkcheck, enrich, channel, ui, Video | `arvantir/normalize.py darkcheck.py enrich/ channel.py ui.py` |
| 4d | Arvanas Arbeitsweise aus den Repos ihrer Leute reverse-engineeren | `research/ARVANA_WORKFLOW.md` |
| e5 | Arvantir in Arvanas Format: Claude-Code-Skill im Stil von claude-gtm-skills, Clay-Spalten, Supabase-Schema | `adapters/`, `skills/arvantir/` |
| 55 | Fine-Tuning + Benchmark vorbereiten, Daten über alle 6 Nischen sammeln | `finetune/`, `bench/`, `data/runs/` |
| d2 | Arvanas Kunden und ICPs je Nische als Re-Ranker-Queries | `research/ARVANA_ICPS.md`, `research/icps.json` |

## Regeln

- Vor jedem Push: `git fetch origin && git merge --no-edit origin/main` (pull --rebase scheitert, weil andere Terminals im selben Ordner ungespeicherte Änderungen haben), dann `git push origin main`. Oft pushen (alle 15 bis 20 Min)
- keine Secrets im Repo, Keys nur in `.env` (steht in .gitignore)
- curl / r.jina.ai / Searchify, kein sichtbarer Browser ohne Ansage
- Abgabe 17:00, Feature-Stopp 16:00, Video ab 16:15
- Python-Umgebung: `.venv` im Repo (`uv pip install -p .venv/bin/python -r requirements.txt`)
- **Alle Terminals teilen denselben Ordner.** Nur eigene Dateien per Pfad committen (`git add web/` statt `git add -A` oder `git add .`), sonst landen halbfertige Dateien anderer im Commit.
- Website-Abrufe von Firmenseiten immer über `arvantir.harvest.fetch` (SSRF-Schutz: prüft jede Weiterleitung, lehnt private IPs ab)
