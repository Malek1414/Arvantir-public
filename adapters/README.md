# So steckt Stephan das Montag ein

Arvantir ist der 13. Skill vor euren 12: er baut die Liste, mit der
company-research-agent, icp-scorer und der Rest heute anfangen. Ausgabe
in euren Spalten, euren Tiers und euren Begriffen.

## 1. Skill installieren (2 Minuten)

```
git clone https://github.com/Malek1414/Arvantir.git ~/arvantir
cd ~/arvantir && uv venv .venv && uv pip install -p .venv/bin/python -r requirements.txt
cp .env.example .env            # Keys eintragen, siehe unten
cp -r skills/arvantir ~/.claude/skills/dark-tam-finder
echo 'export ARVANTIR_HOME=~/arvantir' >> ~/.zshrc
```

Claude Code neu starten, dann `/dark-tam-finder` oder einfach
"finde mir Bäckereien mit eigener Backstube, die nicht in AI Ark sind".

## 2. Lauf + Export

```
skills/arvantir/scripts/run.sh "Bäckereien" "Inhabergeführte Bäckereien mit eigener Backstube und mindestens drei Filialen" \
    --sperrliste sperrliste.txt --bekannt leads_export.csv --min-tier B
```

Ergebnis: `data/run_<zeit>_arvana.csv`. Die ersten 8 Spalten sind exakt
eure `leads_export.csv` (`vorname, nachname, email, position, firma,
domain, quelle, erfasst_am`), dahinter:

| Spalte | Bedeutung |
|---|---|
| `quelle_url` | Eintrag im Verzeichnis, aus dem die Firma kommt |
| `firmen_key` | stabiler Schlüssel, siehe unten |
| `icp_score`, `tier` | Re-Ranker 0-100, Tier wie euer icp-scorer (A ≥ 80, B ≥ 60, C ≥ 40, sonst D) |
| `datenluecken` | `entscheider; email; telefon; plz; hrb; ai_ark` |
| `konfidenz` | belegt / wahrscheinlich / unbekannt (Sicherheit der Website- bzw. Entscheider-Zuordnung) |
| `begruendung`, `begruendung_quelle` | bester ICP-Satz von der Firmenseite, mit URL |
| `mensch_prueft` | Score nah an der Schwelle, SDR entscheidet |
| `in_ai_ark` | `nein` = Dark TAM |
| `gesperrt`, `bekannt` | Sperrliste (normalisiert: Groß/klein, `www.`, Leerzeichen egal) und bestehende Liste |
| `kanal` | Mail / LinkedIn / Brief / Telefon / Fax |

Andere Spaltennamen: `--format clay` gibt Clays Standard-Eingaben aus
(`Company Name`, `Company Domain`, `Full Name`, `Work Email`, `ICP Tier`,
`Data Gaps` ...), damit Clays eigene Enrichments ohne Mapping greifen.

## 3. In Clay

- **CSV:** neue Table → Import CSV. Fertig.
- **Webhook:** Table mit Quelle "Webhook" anlegen, URL und Auth-Token in
  `.env` (`CLAY_WEBHOOK_URL`, `CLAY_WEBHOOK_TOKEN`), dann
  `python -m adapters.clay --latest --min-tier B --webhook`. Gesperrte Zeilen
  gehen nie raus.
- **Clay Agent Plugin:** Claude die CSV geben und in die Table schreiben
  lassen. `datenluecken` als Filter für die Waterfall-Spalten nutzen:

| Lücke | günstigster Weg |
|---|---|
| `entscheider` | Impressum (Pflichtangabe, kostenlos) → Blitz / AI Ark People → Lusha nur Tier A |
| `email` | Impressum → Muster aus einer echten Mail der Domain + Validierung → `info@` als niedrig |
| `telefon`, `plz`, `hrb` | Impressum, sonst Handelsregister |
| `ai_ark` | AI-Ark-Company-Search nach Domain |

## 4. In Supabase

Einmal: Supabase → SQL Editor → `adapters/supabase.sql` ausführen.
Danach pro Lauf:

```
python -m adapters.supabase --latest --dry-run   # zeigt Zahlen
python -m adapters.supabase --latest             # schreibt
```

`.env`: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (nur Server, nie
Frontend; RLS ist an und ohne Policies, der anon-Key sieht nichts).

Aufbau, Kleppmann Kap. 11/12 (System of Record vs. abgeleitete Daten):

| Tabelle | Rolle |
|---|---|
| `raw_pages` | System of Record. Was wir gesehen haben, mit sha256. Nur INSERT, ein Trigger blockt UPDATE und DELETE |
| `companies` | eine Firma = eine Zeile, Schlüssel `entity_key` |
| `company_sources` | auf welchen Listen die Firma steht (`source_count` = Legitimitätssignal) |
| `people` | Entscheider je Firma |
| `field_values` | jeder Feldwert mit `source_url`, `raw_page_id`, `method`, `confidence` 0-1, `ts`; mehrere Werte pro Feld erlaubt |
| `lead_scores` | Score + Tier pro Lauf, `tier` als generierte Spalte |
| `company_fields_current` (View) | bester Wert pro Feld: höchste Konfidenz, dann jüngster |
| `sdr_leads` (View) | eine Zeile pro Lead für die SDRs |
| `rebuild_derived()` | leert alles Abgeleitete, `raw_pages` bleibt; danach neu ableiten (neues Modell, besserer Normalisierer) |

**Schlüssel** (`entity_key`), gleich in Clay-Export und Supabase:
`reg:<gericht>|<HRB>` > `dom:<registrierbare domain>` >
`name:<gefalteter name ohne Rechtsform>|<PLZ>`. "Hafenblick Group GmbH",
"Hafenblick Group" und "hafenblick group" mit derselben Domain sind eine
Zeile. Bekommt eine Firma später ihre HRB, zeigt `entity_aliases` vom
alten auf den neuen Schlüssel.

Getestet: Schema zweimal hintereinander auf Postgres 16 eingespielt
(idempotent), echter Lauf (60 Firmen, 107 Rohseiten) zweimal geladen,
zweiter Durchgang ändert keine Rohseiten und keine Feldwerte.

## Keys

Nichts davon steht im Repo. Alles in `.env` (steht in `.gitignore`):
`CLAY_WEBHOOK_URL`, `CLAY_WEBHOOK_TOKEN`, `SUPABASE_URL`,
`SUPABASE_SERVICE_ROLE_KEY` plus die Pipeline-Keys aus `.env.example`.
