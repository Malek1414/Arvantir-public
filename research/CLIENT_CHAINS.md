# Client chains: Arvana → its clients → their clients (the dark TAM)

As of 31 Oct 2026, around 13:30 (Malek's terminal: three research agents plus arvana.io). This file **adds evidence** to `ARVANA_ICPS.md`; it doesn't replace it. Which client actually sits behind each slide niche is still **not publicly confirmed**, so ask Arne or Stephan on site.

## Strongest client → niche links (with evidence)

| Niche (slide) | Best-evidenced Arvana client | Why (evidence) | Confidence |
|---|---|---|---|
| **Bakeries & butchers** | **Greenflash** (PV + battery storage + AI energy management) | Arvana's case study: the lead form **asks for electricity use to pre-qualify**. Ovens and cold rooms make these businesses energy-hungry. [case](https://www.arvana.io/success-stories/greenflash) · alternatives: fiskaly (cloud TSE for tills), Banxware (loans via POS platforms), Swisscom (Swiss SMB connectivity) | medium |
| **Car washes** | **Greenflash** | Water heating and pumps mean high power use, and they have roof or land space. No car-wash association with a public member list exists, so scrape directory sites instead | medium |
| **IT service providers** | **Trovarit**, **Ninox**, neue fische, wbs training | Trovarit's IT-Matchmaker lists about 590 ERP vendors and resellers; Ninox sells through small implementation partners; neue fische sells upskilling to 50–500-person firms. **Also Arvana's own ICP** ("200+ campaigns with B2B IT service providers and SaaS") | **high** |
| **Doctors & pharmacies** | **telli** (AI phone agents), Placetel / Talkdesk (cloud phone), wbs training (MFA/care training), FreeNow for Business (home visits) | High call volume in practices; telli has energy and real-estate solution pages; WBS Schulen covers care and healthcare | low–medium |
| **Family offices & LPs** | **Startup Insider** (VC media + investor network) | Their audience and angel network are LPs, family offices and business angels | medium |
| **Asset managers (+ portfolio size)** | **telli** and **smapOne** | telli's case studies are real-estate firms (Homeday, McMakler) with a real-estate solutions page; smapOne serves Vonovia-style property firms with inspection apps. **Number of units drives both deals** (more units = more tenant calls and inspections). That explains "portfolio size" on the slide | medium |
| *(7th niche, not on the slide)* | **koppla** | Mid-size construction firms and subcontractors (ZDB, Bauindustrie, bauma exhibitors) | high |

Sources: [telli Homeday](https://telli.com/customers/homeday) · [telli McMakler](https://telli.com/customers/mcmakler) · [telli real estate](https://www.telli.com/solutions/real-estate) · [smapOne references](https://en.smapone.com/references/details/sakret-the-building-materials-specialist-is-digitalising-field-service/) · [Trovarit case](https://www.arvana.io/success-stories/trovarit) · [ivy case](https://www.arvana.io/success-stories/ivy) · [neue fische case](https://www.arvana.io/success-stories/neue-fische) · [infomotion case](https://www.arvana.io/success-stories/infomotion) · [Gemma case](https://www.arvana.io/success-stories/gemma-analytics) · [wbs Firmenseminare](https://www.wbstraining.de/firmenseminare/) · [koppla funding](https://www.startbase.de/news/koppla-sammelt-sechs-millionen-euro-fuer-bau-termindigitalisierung-ein/)

## Client-by-client (who they sell to → which ICP attribute matters)

| Arvana client | Sells | Their customers | Attribute that drives the deal |
|---|---|---|---|
| Greenflash | PV, commercial storage, EV charging, AI load management | Energy-heavy commercial and industrial sites (Boll Logistik, Kettelhack 24,000 m² roof) | **kWh per year**, roof area, number of sites |
| telli | AI voice agents | Real estate (Homeday, McMakler), energy, utilities, insurance, high-call B2C | **number of units / doors**, call volume, branches |
| smapOne | No-code field-process apps | Mittelstand field operations (Vonovia, Dachser, Rhenus, TÜV Austria) | units / objects, field staff, paper processes |
| koppla | Construction scheduling | General contractors (Implenia, Max Bögl, 18 of the top-100 DACH builders) | concurrent projects, build volume |
| ivy | Pay-by-bank API | E-commerce, marketplaces, crypto platforms; Head of Payments / CTO | transaction volume, internationalization |
| Banxware | Embedded SME lending | Platforms: Qonto, SumUp, Lieferando, Payone | platform volume, long-tail SME base |
| Startup Insider | VC media + investor network | Founders, VCs, angels, **LPs, family offices** | LP type, AuM / ticket focus |
| Ninox | Low-code database | SMBs without IT staff, through **implementation partners** | Excel/Access-replacement pain |
| Trovarit | ERP selection + IT-Matchmaker | Mittelstand with 50–5,000 FTE; ERP vendors and resellers | FTE band, ERP-replacement trigger |
| infomotion | Data / cloud / AI consulting (550+ staff) | Enterprise + public sector, CDO/IT leads | (enterprise, not dark TAM) |
| Gemma Analytics | Data / BI consulting | Funded startups and scale-ups | (startups, weak fit) |
| neue fische | Bootcamps + B2B upskilling (QCG-funded) | Companies with 50–500 employees, HR/L&D | headcount, tech roles |
| wbs training | Funded retraining + company seminars | SMBs (100% funding at 1–49 employees), care/health | headcount band |
| FreeNow for Business | Corporate mobility budgets | Firms with travelling staff | field staff, travel volume |
| Swisscom | SMB telecom / IT bundles (Switzerland) | Any Swiss SMB including local trades (KMU Office: 10,000+ customers) | locations, Swiss register (Zefix) |

## Where the clients' customers are listed (dark sources)

- **Bakeries / butchers:** guild (Innung) member lists, Zentralverband des Deutschen Bäckerhandwerks, Deutscher Fleischer-Verband, Handwerkskammer registers; CH: Zefix + Bäcker-Confiseurmeister-Verband
- **Car washes:** directory sites (no association roster), Google Maps / Places (Sami's harvester: 500 entries)
- **IT service providers:** IT-Matchmaker vendor directory, Ninox partner directory, Shopware / Webflow / Salesforce partner lists, it-sa exhibitors, Bitkom / BITMi members
- **Doctors & pharmacies:** KBV Arztsuche, ABDA Apothekenfinder, Bundesärztekammer
- **Family offices & LPs:** BVK members, Family Office Tag / Deutscher Family Office Report, Handelsregister holding companies
- **Real-estate asset / property managers:** BaFin KVG register (Sami: 201 institutions), BVI Immobilienverwalter, IVD, GdW members, EXPO REAL exhibitors
- **Construction:** ZDB, Hauptverband Bauindustrie, bauma exhibitor directory (3,500+)

## How each partner fits the engine

| Step | Tool (hackathon partner or Arvana stack) |
|---|---|
| Find | Searchify (Sami) + directories above; **Needle** (LinkedIn data, recommended by the sponsor for Dark TAM) |
| Check | **AI Ark** company search: a miss costs 0 credits, a hit 0.1, so dark = `totalElements == 0` (see `FOR_MALEK.md`) |
| Enrich | Impressum (free) → OffeneRegister / North Data → **Blitz** (domain→LinkedIn→people→email; 5M credits on 31 Oct) → **Lusha** (top leads only) → **OpenAI** for extraction |
| Score | Arvana's own `icp-scorer` format: must-have filters, tiers A–D, data gaps, confidence (confirmed / likely / unknown), blocklist |
| Deliver | CSV in their `leads_export` columns → **Clay** table (Clay Agent Plugin) → their 12 skills unchanged → **Smartlead** (email after opt-in) / **Needle** (LinkedIn) / **letter** (default for local SMBs) / **faxxing** (demo only, consent) → HubSpot / Pipedrive / Salesforce |
| Not used for Dark TAM | Zapmail (sending infra, no warm-up today), Scaile (GEO challenge) |

## Pitch use

Name the chain in the video. For example: *"Greenflash wants energy-hungry bakeries. AI Ark knows almost none of them. Arvantir found X in the guild lists, with the owner from the Impressum and the number of branches as a proxy for energy use."*
