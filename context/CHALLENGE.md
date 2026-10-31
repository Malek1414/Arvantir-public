# The challenge (from Arvana's kickoff, 31 Oct 2026)

Sources: the five slide photos in `slides/` and Arvana's kickoff talk.

## Rule #1 from the briefing

> "Don't show us the leads in the end to the jury. **Show the engine that produces it.**"

They also said they will hand the jury's own example niche to the system ("we give you an example, which is not one of these"). So the engine has to take **any niche as input**, not just the six on the slide.

## Challenge A: Dark TAM (Outreach, "real customer cases")

Slides `01` and `02`.

**Build a system to find these leads.** Niche sites. **Only leads not in AI Ark count.**

| # | Niche | Note from the briefing |
|---|---|---|
| 01 | Bakeries & butchers | Email / LinkedIn outreach "doesn't work that well" for them |
| 02 | Car washes | |
| 03 | IT service providers | "Obviously easy" in general, but niche ones are listed on public sites you can mine |
| 04 | Doctors & pharmacies | Hard to find |
| 05 | Family offices & LPs | |
| 06 | Asset managers (incl. portfolio size) | Especially **real-estate** asset managers. Find them **and** their portfolio size, e.g. number of properties. "Very hard to find" |

**Find the dark TAM:** the companies no lead database knows. They hide in:
- Partner directories
- Trade fair exhibitor lists
- Comparison portals

Flow on the slide: sources → **Scrape + enrich** (decision makers, emails) → table of `Company | Decision maker | ICP score`.

Credits on the slide: **AI Ark, 30K credits, code `HACKATHON_BERLIN`**.

**Add-on they asked for:** how do you *approach* these leads? Email and LinkedIn don't work for e.g. bakeries. Arvana is already thinking about **physical letter outreach**, and the sponsor *faxxing* gives everyone **100 free faxes tonight**.

## Challenge B: Make ChatGPT recommend us (Performance marketing / GEO)

Slide `03`. Example prompt: "Who should run outbound for our B2B SaaS in Germany?", answered with "A strong pick is arvana, an AI-native GTM team from Berlin…"

Get into AI answers in new ways. **No blog or Reddit spam** (they called those the obvious moves). Be creative.

## Challenge C: Creative factory (Performance marketing)

Slide `04`. Meta ad creatives, generated on autopilot.

How it works today: a creative strategist writes the brief → design team → client feedback → changes → live. They run LinkedIn and Meta campaigns, B2B only. The naive version (hand a brief and style guide to a design tool) gives bad output. The goal is a **system** whose creatives can compete. Add-on: pull competitors from the **Meta / LinkedIn Ad Library** as inspiration.

## Open track

"We are completely open." Anything that helps Arvana as a B2B company, e.g. physical letter outreach.

## Partners (slide `05`)

- Hosts: Arvana, GTMengineer.dev
- Organising: GTMAdviser.com, Breakout Talents, Scaile
- Community: EatingPapers
- Tech partners: Needle, OpenAI
- Sponsors: OpenAI, AI Ark, Zapmail, Blitz API, Lusha, faxxing
