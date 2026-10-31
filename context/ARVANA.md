# Arvana: who we're building for

- **What:** a bootstrapped Berlin agency that bills itself as AI-native and runs go-to-market for B2B tech companies in DACH. Around €5M ARR, 30+ people, 200+ clients (FreeNow, Swisscom, SmapOne, Klett, telli, Ivy, ProAlpha, Trovarit).
- **Founders / MDs:** Arne Unkrig (ex-Enpal venture development) and Mirco Pfefferle.
- **Services:**
  1. **Signal-based outbound:** email + LinkedIn, prospect research, AI-personalized copy, deliverability on separate warmed domains, follow-ups, lead scoring, hot/warm/cold triage, meetings synced into the client's CRM. About 3 weeks from kickoff to launch.
  2. **Paid ads:** Google, LinkedIn, Meta, Bing, Demand Gen ("€10M+ ad spend managed").
- **How they make money:** a fixed **monthly retainer** with no minimum term. The Clay partner page lists **$5k+/month**; Sortlist says email outreach from about €5,000 and ads from about €3,000 per project. We found no pay-per-meeting pricing.
- **Stack:** Clay (they call themselves the "Clay market leader in DACH"), OpenAI, Make, Zapier, HubSpot / Pipedrive / Salesforce, Looker Studio, Smartlead.
- **Their own KPIs:** qualified first calls, pipeline value, sales cycle, closed revenue.
- **Public criticism (Salesforge review):** some reviews call the data **weak or outdated**; there's **no defined "qualified lead" standard**; the review also flags unclear domain ownership and inconsistent self-reported stats.

## Tech side (from Sami's research)

- **Tech lead: Stephan Mundt** (GitHub [@stephanmundtcode](https://github.com/stephanmundtcode)), also a co-host of the hackathon.
- Internal stack: **Claude Code, Supabase, Clay**.
- Public repos: [`claude-gtm-skills`](https://github.com/stephanmundtcode/claude-gtm-skills) (12 Claude Code GTM skills: icp-scorer, buying-signal-detector, company-research-agent, technographic-qualifier, …) and [`kampagnen-cockpit-case-study`](https://github.com/stephanmundtcode/kampagnen-cockpit-case-study) (their case study for software engineers).
- Their ICP scorer grades each lead on its own with fixed weights (tiers A–D). Replies only flow back into lead selection by hand: no lookalike search, no clustering, no closed loop.

## Design principles we follow

From Kleppmann's *Designing Data-Intensive Applications*:
- **System of record vs derived data:** keep raw scrapes immutable, build the clean lead table as a derived view you can always rebuild.
- **Normalization / entity resolution:** one company = one row, with a stable key (German Handelsregister court + HRB number, falling back to domain), so dirty records from many sources merge cleanly.
- **Provenance:** every field records where it came from and when, so SDRs see a confidence level instead of guessing.

## Sources

- https://www.arvana.io/ and https://www.arvana.io/en/outreach
- https://www.clay.com/experts/partner/arvana
- https://www.salesforge.ai/blog/arvana-review
- https://join.com/companies/arvana
- https://de.linkedin.com/company/arvana-io
