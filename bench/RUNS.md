# Arvantir runs on 31 Oct 2026

Generated from `data/run_*.json` (not committed: they hold names from company legal notices). One full pipeline run per niche: discover, harvest, normalize, darkcheck, enrich, signals, rank, channel.

| Niche | Run | Companies read | One row per company | Ranked leads | With decision maker | With fresh signal | Letter as channel | Seconds |
|---|---|---|---|---|---|---|---|---|
| Asset Manager Immobilien | run_145130 | 240 | 223 | 60 | 33 | 14 | 38 | 143.4 |
| IT-Dienstleister | run_145335 | 135 | 134 | 60 | 20 | 12 | 25 | 124.2 |
| Ärzte & Apotheken | run_144623 | 143 | 139 | 60 | 32 | 2 | 54 | 185.0 |
| Bäckereien & Metzgereien | run_143435 | 86 | 47 | 47 | 16 | 10 | 40 | 141.4 |
| Family Offices & LPs | run_143910 | 104 | 94 | 60 | 32 | 16 | 49 | 274.1 |
| Waschanlagen | run_142923 | 97 | 94 | 60 | 1 | 10 | 58 | 53.9 |

Total: 347 ranked leads across 6 niches, 134 with a named decision maker from the company's own legal notice.

Not yet measured: whether these companies are in AI Ark (darkcheck runs without an AI Ark key, so in_ai_ark is unknown).

## Offline dark check against a 17M-company database (knowncheck)

Stand-in for the AI Ark check while there is no AI Ark key. Index: BigPicture companies 2023 Q4 from Hugging Face (17,154,017 companies, 685,799 in DACH, ODC-BY), built with `python -m arvantir.knowncheck build`. Leads with a website are matched by domain. Leads without one are matched by name + city, which is weaker evidence. Source: `data/ext/bench_bigpicture.json`.

| Niche | Not in DB, by domain | Not in DB, by name + city | Not checkable |
|---|---|---|---|
| Ärzte & Apotheken | 38 of 44 (86 %) | 15 of 16 | 0 |
| Bäckereien & Metzgereien | 17 of 27 (63 %) | 20 of 20 | 0 |
| Waschanlagen | 2 of 4 | 53 of 53 | 3 |
| Asset Manager Immobilien | 11 of 57 (19 %) | 0 of 0 | 3 |
| Family Offices & LPs | 8 of 45 (18 %) | 14 of 14 | 1 |
| IT-Dienstleister | 8 of 58 (14 %) | 1 of 1 | 1 |
| **Total** | **84 of 235 (36 %)** | **103 of 104** | **8** |

Reading: local trades (doctors, bakeries, car washes) are almost entirely missing from a LinkedIn-style database, so that is where the dark TAM is. Classic B2B niches (IT services, asset managers, family offices) are mostly known already, and Arvantir's value there is the enrichment (decision maker, portfolio size, signal). Limit: this is not AI Ark. The claim is "not in a 17M public company database", not "not in AI Ark". The database is from 2023.
