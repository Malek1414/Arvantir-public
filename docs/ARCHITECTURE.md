# Arvantir: Architektur

Arvantir ist Searchify, zugeschnitten auf Arvana. Searchify (`searchify-l`: search, extract, rerank) bleibt unverändert. Arvantir ist die GTM-Schicht darüber: Es findet aus öffentlichen Quellen den Dark TAM, also Firmen, die keine Lead-Datenbank kennt, und liefert sie im Format von Arvanas eigenen Skills.

Arvanas 12 claude-gtm-skills fangen alle bei einer fertigen Liste an (`research/ARVANA_WORKFLOW.md`). Arvantir ist der Skill davor.

## Gesamtbild

```mermaid
flowchart LR
  IN["Eingabe<br/>Nische oder Beispiel-Lead<br/>+ ICP (icps.json)"] --> D

  subgraph ENGINE["Arvantir-Engine (arvantir/)"]
    D["discover<br/>Suchanfragen in Verzeichnis-Sprache<br/>DACH-Filter, kuratierte Quellen"]
    H["harvest<br/>Listenblöcke ohne Vorwissen<br/>Hubs, Paginierung, PDF"]
    N["normalize<br/>Rechtsform, Domain, Schlüssel<br/>HRB > Domain > Name+PLZ"]
    DC["darkcheck<br/>AI Ark: nur Treffer = 0 zählen"]
    E["enrich<br/>Impressum: Entscheider, Kontakt<br/>Nischenfelder (Portfoliogröße)"]
    S["signals<br/>LinkedIn, News, Hiring, Funding<br/>nur jünger als 6 Monate"]
    R["rank<br/>Cross-Encoder mMiniLM<br/>Score 0-100, Tier A-D, Begründung"]
    C["channel<br/>Brief / Mail / LinkedIn / Fax<br/>§7 UWG beachtet"]
    D --> H --> N --> DC --> E --> S --> R --> C
  end

  subgraph SF["Searchify (unverändert)"]
    SS["search"]
    SX["extract"]
    SR["rerank / score"]
  end

  D -. nutzt .-> SS
  D -. nutzt .-> SR
  R -. nutzt .-> SR
  R -. Profile .-> SX

  C --> OUT1["Clay-CSV / Webhook<br/>Spalten wie leads_export.csv"]
  C --> OUT2["Supabase<br/>raw_pages unveränderlich<br/>companies, field_values abgeleitet"]
  C --> OUT3["Website :8400<br/>Funnel live, Tabelle, Lead-Karte"]
  OUT1 --> AR["Arvanas 12 Skills<br/>icp-scorer, buying-signal-detector, ..."]
```

## Lernschleife: Re-Ranker auf Arvana trainieren

```mermaid
flowchart LR
  RUN["jeder Lauf<br/>(pipeline.run)"] --> P["data/rank_pairs.jsonl<br/>(ICP, Firmenprofil)"]
  P --> DATA["finetune/data.py<br/>Negative aus anderen Nischen<br/>Split nach Firma"]
  DATA --> T1["Lehrer-Labels<br/>LLM / vLLM auf dem Spark"]
  DATA --> T2["Gold-Labels<br/>Arvana / Team per Hand"]
  T1 --> TR["finetune/train.py<br/>DGX Spark, Leave-one-niche-out"]
  TR --> M["models/arvantir-rr-v1"]
  M -->|RERANKER_MODEL| R2["rank.py"]
  T2 --> B["finetune/bench.py<br/>feste Gewichte vs LLM vs Basis vs fine-tuned"]
  M --> B
  B --> RES["bench/results.md<br/>NDCG@10, Übereinstimmung, ms/Lead"]
```

## Module und Zuständigkeit

| Modul | Was | Datei |
|---|---|---|
| discover | Nische -> Quellen, Re-Ranker sortiert Listen nach oben | `arvantir/discover.py` |
| harvest | Quelle -> Firmen, ohne Vorwissen über die Seite, SSRF-geschützt | `arvantir/harvest.py` |
| normalize, darkcheck, enrich, channel | Bereinigen, AI-Ark-Abgleich, Impressum, Kanal | Malek (`arvantir/…`) |
| signals | frische Kaufsignale je Lead | `arvantir/signals.py` |
| rank | Cross-Encoder, Tier A-D nach Arvanas icp-scorer, Konfidenz, Datenlücken | `arvantir/rank.py` |
| pipeline | alles verbinden, Funnel-Zahlen, JSON + CSV | `arvantir/pipeline.py` |
| Skill | `dark-tam-finder` im Stil von claude-gtm-skills | `skills/arvantir/` |
| Adapter | Clay, Supabase | `adapters/` |
| Website | Live-Demo, SSE-Funnel | `web/` |
| Fine-Tuning | Daten, Labels, Training, Benchmark | `finetune/`, `bench/` |

## Datenmodell (für Arvanas CTO)

- **System of Record:** `raw_pages` speichert jede abgerufene Seite unverändert, nur INSERT.
- **Abgeleitet:** `companies`, `people`, `field_values` sind jederzeit aus `raw_pages` neu baubar (`rebuild_derived()`).
- **Provenienz:** jedes Feld hat `source_url`, `method`, `confidence`, `ts`.
- **Schlüssel:** `reg:Gericht|HRB` > `dom:domain` > `name|PLZ`, gleich in Clay und Supabase.

## Sicherheit

- Abrufe fremder Seiten nur über `harvest.fetch`: http(s), öffentliche IPs, jede Weiterleitung geprüft
- CSV-Zellen gegen Formel-Injection escapt
- Website bindet nur an 127.0.0.1, Host-Prüfung gegen DNS-Rebinding, HTML escapt
- Keys nur in `.env`, Trainingsdaten im Repo ohne E-Mails und Telefonnummern

## Starten

```bash
uv pip install -p .venv/bin/python -r requirements.txt
.venv/bin/python -m arvantir run "Waschanlagen"                 # ganzer Lauf, JSON + CSV in data/
.venv/bin/uvicorn web.server:app --host 127.0.0.1 --port 8400   # Website
.venv/bin/python -m pytest tests -q                             # Tests
```
