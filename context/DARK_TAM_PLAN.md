# Plan: the Arvantir Dark TAM engine

**Name:** Arvantir is a Palantir for Arvana that searches the open web (Sami's vision). It's a version of **Searchify** (Sami's search + extract + rerank package, plus the local `tavily-clone` search service) tailored to Challenge 1.

**One line:** give it an example lead or a niche. It finds lookalike companies that no lead database has, cleans them, proves they aren't in AI Ark, finds the decision maker without a database, re-ranks them with a reason and a source for each, and says how to reach them.

The jury said: *show the engine, not the leads.* They will hand the system an example we haven't seen. So everything below has to work for **any niche**.

## How we beat Arvana's current setup (from Sami's research)

- **Re-ranker, not a fixed-weight score:** Arvana's ICP scorer (Stephan Mundt's public `icp-scorer` skill) grades every lead on its own with fixed weights (tiers A–D). We re-rank candidates by **similarity to the example lead**.
- **Trustworthy agent sorting:** Every lead carries **a reason plus a source**, we measure **agreement with their manual sorting**, and **only uncertain cases go to a human**.
- **Where customers complain:** only about outreach, namely outdated data sources and too few leads. That's exactly what Dark TAM fixes.
- **Next step (pitch as roadmap):** a closed loop. Hot and warm replies become seeds, Searchify researches them deeply, explainable clusters form, the next leads get re-ranked, and reply rate per cluster feeds back in. Learning has to pool across clients: a single client has too few replies (to see 2% → 4% you need about 1,141 sends per arm).

## The pipeline

```
example lead (company URL) or niche in plain words ("real-estate asset managers in Germany")
   │
0. UNDERSTAND SEED   if it's an example lead, profile it (what they do, size, region) → niche + similarity target
   │
1. SOURCE DISCOVERY  LLM + web search propose where this niche is listed:
   │                 association member lists (Innungen, Verbände), partner directories,
   │                 trade-fair exhibitor lists, comparison portals, public registers
   │                 (BaFin, KV doctor search, pharmacy finder), Google Maps categories
2. SCRAPE + EXTRACT  fetch each source, LLM-extract entries into one fixed schema
   │                 (name, website, city, raw fields). Keep raw pages immutable (system of record)
3. NORMALIZE         clean legal names (GmbH / UG / e.K. / AG), canonical domain,
   │                 address, dedupe with key = Handelsregister court+HRB > domain > name+postcode
4. DARK CHECK        look up every company in AI Ark (30K credits, HACKATHON_BERLIN)
   │                 → keep only "not in AI Ark". This is the score that counts.
5. ENRICH, NO DB     read the company's own Impressum (§5 DDG requires one): managing director
   │                 or owner, email, phone, fax, HRB number. Plus niche fields, e.g.
   │                 portfolio size (number of properties) for real-estate asset managers
6. RE-RANK           rank by similarity to the seed (Searchify rerank), with a reason + source per lead;
   │                 low-confidence cases flagged for a human
7. CHANNEL           best way in per lead: email / LinkedIn / phone / letter / fax,
                     with a ready-to-send draft (Arvana asked for this add-on)
```

**What the demo screen shows:** a live funnel. Sources found → companies scraped → after dedupe → **not in AI Ark** → with decision maker → with a reachable channel. Then the table: `Company | Decision maker | ICP score | Channel | Source`.

## Why this beats "scrape Google Maps"

- **The Impressum trick:** German law requires nearly every business website to name the managing director or owner and give contact details. That's the decision maker without Lusha or AI Ark.
- **Normalization (what the CTO asked for):** one company, one row, with a stable German key (HRB number). Many dirty sources merge into one clean table, and every field keeps its provenance. Kleppmann's idea of derived data: rebuild the clean table any time from raw.
- **Source discovery is the real moat:** each niche has its own hidden lists (bakers' guilds, car-wash associations, the BaFin register, trade-fair exhibitors). The engine finds the lists itself, which is why it works on the jury's surprise niche.

## Outreach add-on (be careful with the law)

- **Physical letter:** legally the cleanest cold B2B channel in Germany, and Arvana is already considering it. Generate the letter as a PDF; a letter API (e.g. Pingen, LetterXpress) can send it.
- **Fax:** the sponsor *faxxing* gives 100 free faxes tonight, and German doctors and pharmacies still run on fax. **But cold advertising by fax (and email) needs prior consent under §7 UWG.** Demo the fax on ourselves or on Arvana with their OK, e.g. by **faxing the jury their own lead report**. Don't fax strangers.
- **No cold email today:** new Zapmail domains aren't warmed up, and the same consent rule applies.

## Niche playbook (starting points for source discovery)

| Niche | Where they hide |
|---|---|
| Bakeries & butchers | Bäckerinnung / Fleischerinnung member lists, Handwerkskammer directories, Google Maps |
| Car washes | Car-wash association member lists, operator directories, Google Maps; UNITI expo exhibitors are *suppliers*, not operators |
| IT service providers | Partner directories: Microsoft, HubSpot, DATEV, Shopware, SAP; it-sa exhibitor list |
| Doctors & pharmacies | KV doctor search, pharmacy finders, Doctolib / jameda listings |
| Family offices & LPs | Family-office association lists, fund documents, Handelsregister (Vermögensverwaltungs-GmbH) |
| Asset managers (+ portfolio size) | BaFin company database (KVGs, portfolio managers), ZIA / Expo Real exhibitors, "Portfolio/Objekte" pages on their sites, Bundesanzeiger filings |

## Build order (12:30 → 17:00)

| Time | Who | What |
|---|---|---|
| 12:30–13:30 | all | Schema + one niche end-to-end, ugly but working (suggest IT service providers via one partner directory) |
| 13:30–14:30 | A | Source discovery for any niche (LLM + search) |
|  | B | Normalize + dedupe + AI Ark check |
| 14:30–15:30 | A | Second niche (real-estate asset managers + portfolio size) |
|  | B | Impressum enrichment + ICP score |
|  | C | Funnel UI |
| 15:30–16:15 | C | Channel add-on: letter PDF + one demo fax |
| 16:15–17:00 | all | Run it on an unseen niche, **record the 2-minute video** (that IS the submission), submit before 17:00 |

**Judging is 25% each: Business Impact · Tech · Works end-to-end · Pitch.** "Works end-to-end" is a quarter of the score, so get one niche going all the way from input to channel before adding anything else.

## 2-minute video outline (the submission)

1. **Hook:** "AI Ark knows hundreds of millions of contacts. The bakery round the corner isn't one of them, and neither are its 40,000 cousins."
2. **Live:** the jury names a niche → the engine runs → the funnel counts up.
3. **The number:** "X companies, Y% not in AI Ark, Z with a named decision maker."
4. **How:** the Impressum trick + normalization with the HRB key (nod to the CTO).
5. **How to reach them:** letter, or fax with consent. Fax the jury their report.
6. **Close:** "Plugs into your Clay tables on Monday."
