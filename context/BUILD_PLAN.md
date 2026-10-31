# Build plan (12:45 → 17:00)

The goal is a **2-minute video** of an engine that works from start to finish. Judging is 25% each: Business Impact · Tech · **Works end-to-end** · Pitch.

**Rules:** get one thin slice working end to end by 14:30. Stop adding features at **16:00**. Record at 16:15.

## Architecture

Python, built on Sami's **Searchify** (`search` → `extract` → `rerank`, plus the HTTP service and the local `tavily-clone` on :8000).

```
arvantir/
  run.py            python -m arvantir "<niche or seed URL>" --region DE --limit 200
  discover.py       niche/seed → ranked list of SOURCES (directories, member lists, exhibitor lists, PDFs)
  harvest.py        source → raw company CANDIDATES (selectors written by the LLM, pagination, PDF, Maps fallback)
  normalize.py      clean names/domains/addresses, entity key, dedupe + merge with provenance
  darkcheck.py      AI Ark company-search → in_ai_ark: true / false / unknown
  enrich/
    site.py         crawl own website: Impressum, Kontakt, Team/Über uns, Karriere, Standorte
    impressum.py    managing director / owner, email, phone, fax, address, HRB + court, VAT ID (regex first, LLM fallback)
    niche.py        niche-specific fields via LLM on site text (e.g. portfolio size)
    people.py       paid decision-maker waterfall (top-ranked leads only)
  rank.py           cross-encoder re-ranker (mMiniLM, fine-tuned on Arvana) vs seed/ICP → score 0-100, reason, confidence
  channel.py        best channel + personalized letter/fax/email draft
  store.py          SQLite: runs, sources, raw_pages, companies, people, field_values (value, source, confidence, ts)
  ui.py             Streamlit: input → live funnel → table → lead card
```

**Data model idea (for the CTO):** `raw_pages` is the immutable system of record. `companies`, `people` and `field_values` are derived and can be rebuilt any time. Every field value stores **where it came from and how sure we are**.

## Part 1: adapting the scrape side

Searchify is built to answer questions: it removes boilerplate and ranks passages. Dark TAM needs **lists of companies**, so four changes:

1. **Discovery queries instead of questions.** The LLM expands the niche or seed into German directory vocabulary, then runs it through `searchify.search`:
   - `"{niche} Mitgliederverzeichnis"`, `"{Verband} Mitgliedsbetriebe"`, `"{niche} Innung Mitglieder {Bundesland}"`
   - `"Ausstellerverzeichnis {Messe} 2026"`, `"Partnerverzeichnis {Software}"`, `"{niche} Verzeichnis {Stadt}"`
   - `filetype:pdf Mitgliederliste {niche}`. Association PDFs are among the darkest sources.
   - Then **rerank** the results against *"a directory or list of many {niche} companies"* so list pages come first and single-company pages drop out.
2. **Keep the structure.** Add a raw mode to `extract` that reuses Searchify's fetch → browser → stealth ladder but **keeps the HTML and links** instead of cleaning to article text.
3. **The LLM writes the scraper, code runs it.** On the first page of each source, the LLM returns the CSS selector for one entry, its fields and the "next page" link. Plain code then runs that across all pages: fast, cheap, deterministic. Fallbacks: spot repeated DOM blocks automatically; for PDFs, `pdftotext` then LLM extraction.
4. **Resolve websites.** Directory entries often have no URL. Search `"{name} {city}"`, take the top result that isn't a directory, and **verify** it by checking that the site's Impressum mentions the company name.

**Fallback for local small businesses** (bakeries, car washes): Google Maps via serper.dev Places or Apify. Label it "less dark", because everyone does this.

## Part 2: normalize + dark check

- **Name:** split off the legal form (GmbH, UG (haftungsbeschränkt), e.K., GbR, AG, KG, GmbH & Co. KG) into its own field, then case- and umlaut-fold for matching.
- **Domain:** registrable domain (`tldextract`), no `www`. **Address:** postcode + city.
- **Entity key:** `court+HRB` > `domain` > `(folded name, postcode)`. On merge, keep every source. `source_count` (how many lists name the company) is a legitimacy signal.
- **AI Ark check:** `company-search` by domain, falling back to name + city; header `X-TOKEN`; cache everything. **Only `in_ai_ark = false` counts.** Show the darkness ratio per niche. Verify the endpoint in the first 10 minutes ([docs](https://docs.ai-ark.com)).

## Part 3: getting the most out of enrichment

**Principle:** a waterfall for each field. Free sources first, paid only for leads that already rank high. Every value carries `source + confidence`. Pitch it as "credits are only spent on leads worth calling."

### Company level, free (the company's own website is often its only footprint)

| Page | Fields |
|---|---|
| **Impressum** (required by §5 DDG) | managing director / owner / board names, email, phone, **fax**, postal address, **HRB + court**, VAT ID |
| Kontakt | generic + personal emails, contact form |
| Team / Über uns | more people + roles, founding year ("seit 1987"), **"in dritter Generation"** (a succession signal) |
| Karriere / Jobs | hiring = growth signal, which roles = pain signal |
| Filialen / Standorte | number of locations (bakery chain size, car-wash sites) |
| HTML fingerprint | tech: WordPress / Shopify / booking widgets (Doctolib for doctors), online shop → fit + personalization hooks |
| Google Places (serper) | rating + number of reviews as a size proxy |

**Niche fields** (`niche.py`): the LLM fills a schema per niche from the site text, with the quote as evidence:
- **Real-estate asset managers:** number of properties, m², AuM, asset classes, regions. Sources: "Portfolio/Objekte/Referenzen" pages, then Bundesanzeiger filings.
- **IT service providers:** partner badges (Microsoft Solutions Partner, DATEV, HubSpot tier), ISO 27001, headcount.
- **Doctors / pharmacies:** specialty, number of physicians, private vs statutory insurance, online booking.
- **Bakeries / butchers / car washes:** number of locations, own production / café / wash type.

Optional: Handelsregister / northdata for share capital, officers and founding date.

### Decision maker (people waterfall, top-N only)

1. **Impressum name** (free, legally required, high confidence for small firms).
2. **LinkedIn:** Needle (sponsor; LinkedIn lead data) or Blitz: `domain-to-linkedin` → `search/people` → `enrichment/email` ([Blitz docs](https://docs.blitz-api.ai); Blitz finds emails via LinkedIn profiles, not by guessing).
3. **AI Ark** `people-search` / email finder. The person can be in AI Ark even when the company isn't.
4. **Lusha** (150 credits) only for the top-ranked leads.
5. **Email last resort:** a personal email from the Impressum > a pattern learned from any personal email on the site, plus validation (tryKitt / ZeroBounce) > generic `info@`, flagged as low confidence.

## Part 4: rank + channel

- **Rank = a real re-ranker model, not an LLM score and not fixed weights.** Model: the cross-encoder `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` (multilingual MiniLM, 118M params, the default in Searchify, ~20 ms per sort call, won Sami's reranker comparison on 17.10. against bge-reranker-v2-m3, gte-multilingual and jeff). It scores the pair *(ICP text, company profile text)* jointly, so it sees "Bäckerei mit 12 Filialen, eigene Backstube" against "regionale Bäckereiketten mit Produktion" directly.
  - **Query** = the ICP: seed lead profile or niche description (+ region, size).
  - **Document** = the company profile built from harvest + enrich: name, what they do (Impressum / Über uns snippet), city, niche fields (locations, portfolio size, partner badges).
  - **Score 0–100** = sigmoid of the cross-encoder logit, calibrated, shown as the ICP column (like slide 02).
  - **Reason + source:** the profile sentence that scored highest (passage-level rerank, Searchify already does this) plus its URL.
  - **Confidence:** margin between the score and the decision threshold. Close to the threshold → "needs a human" queue (Arvana's distrust of agent sorting).
  - ICP hard filters (region, legal form, size bounds) run *before* the re-ranker, never as weights inside it.
  - The same model also ranks sources in `discover` (query: "a directory listing many {niche} companies").
  - **Fine-tuned on Arvana** on the DGX Sparks: see `context/FINETUNE_PLAN.md`. Base vs fine-tuned is our benchmark.
- **Channel rules:**
  - Personal email + LinkedIn → email/LinkedIn.
  - Healthcare → letter, or fax **with consent only** (§7 UWG).
  - Local small business → letter or phone.
- Each lead gets a draft personalized with the enrichment facts. **Fax demo:** send to ourselves or to Arvana with their OK (100 team faxes, API key requested from hi@gtmengineer.dev).

## Output

- Streamlit funnel: `sources → pages → candidates → unique → NOT in AI Ark → with decision maker → with verified contact → with channel`.
- A table with provenance per field, and a lead card.
- CSV export ready for Clay. Stretch goal: Clay webhook / Supabase (Arvana's stack).

## Who does what

| | Sami | Malek |
|---|---|---|
| Owns | `discover`, `harvest`, `rank` (his Searchify) | `normalize`, `darkcheck`, `enrich/*`, `channel`, `ui`, video |

## Timeline

| Time | Milestone |
|---|---|
| 12:45–13:15 | Repo skeleton, `.env` keys (AI Ark, Blitz, Lusha, OpenAI $30), SQLite schema, AI Ark endpoint tested with one domain |
| 13:15–14:30 | **Thin slice:** 1 niche, 1 source → ~30 companies → normalized → AI Ark check → Impressum → table |
| 14:30–15:30 | Generalize: discovery for any niche, LLM-written selectors + pagination + PDF; paid waterfall on top-N; niche fields |
| 15:30–16:00 | Streamlit funnel, channel drafts, fax demo; run 2–3 niches incl. one surprise niche; write down the numbers |
| **16:00** | **Feature freeze** |
| 16:15–16:45 | Record and cut the 2-minute video |
| 16:45–17:00 | Submit (video link + repo) |

## Numbers to show (Business Impact)

- Leads **not in AI Ark** per niche, and per minute of runtime.
- % with a named decision maker; % with a verified contact.
- Cost per lead: credits spent ÷ leads (free Impressum layer vs paid waterfall).

## Risks

- **Bot protection:** Searchify's browser/stealth ladder, plus a per-source cap.
- **API surprises:** test AI Ark and Blitz with one call each in the first 15 minutes.
- **LLM cost and speed:** a small, cheap OpenAI model for extraction; cache every page.
- **Running out of time:** if discovery isn't solid by 15:30, hard-code 2 sources per niche and keep the rest of the engine live.
