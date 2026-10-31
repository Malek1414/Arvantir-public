# For Malek (from Sami's research terminal, 31.10.2026, ~13:00)

Matched against your parts in BUILD_PLAN.md (`darkcheck`, `enrich/*`, `channel`, `ui`). Full source list: `research/SOURCES.md` + `research/sources.json` (filling up until 14:00).

## 1. darkcheck: AI Ark company search, verified in the docs

- `POST https://api.ai-ark.com/api/developer-portal/v1/companies`
- Headers: `X-TOKEN: <key>`, `Content-Type: application/json` (required)
- Body by domain: `{"page":0,"size":1,"account":{"domain":{"any":{"include":["example.de"]}}}}`
  (fallback: `account.name` with `mode: "SMART"`, also `account.linkedin`, `account.url`)
- Response is a Spring page: `content[]` (with `id` UUID), `totalElements`. **Dark = `totalElements == 0`.**
- Cost: 0.1 credit per *returned* result, so a miss costs 0 and a hit 0.1. Use `size: 1`.
- Rate limit 5 req/s, then 429. Throttle to ~4/s.
- Credits balance: `GET /v1/payments/credits` (free).
- Docs: https://docs.ai-ark.com/reference/company-search-1.md

## 2. channel: legal check before the fax demo (important for the pitch)

§ 7 Abs. 2 Nr. 2 UWG: advertising by **email and by fax** needs **prior express consent, also B2B**. "Presumed consent" in B2B only covers phone calls. **Letters are allowed** unless the recipient has objected (§ 7 Abs. 1).
So: present the letter as the default channel for bakeries, butchers and car washes, and call fax/email "only after opt-in" or "warm follow-up". Cold faxes from the faxxing quota would be attackable, and the jury may ask.
Scraping: respect ToS, no substantial parts of a database (§ 87b UrhG), GDPR Art. 6(1)(f) + Art. 14 for owner names. Store the source per field (you already plan this, good pitch point).

## 3. enrich: free sources that worked via curl

- **OMR Festival exhibitors**: an open GraphQL endpoint with no key, 1,714 companies with website + LinkedIn:
  `POST https://api-eu-central-1.hygraph.com/v2/ckttznct701xy01xzb2e68lp1/master`, query `{ partnerCompanies(first:100){ name website linkedin } }`
- **OffeneRegister.de** dump (JSONL/SQLite): officers (managing directors) by company name. Good fallback when the Impressum has no name.
- **Northdata** (northdata.de/<name>): managing director + revenue for the top leads only (rate-limited).
- Partner directories readable without a browser: Shopware agencies (`?page=N`), Webflow Experts sitemap (2,254 profiles), Salesforce AppExchange sitemap (4,567 consultants).

## 4. Numbers for the video

The research suggests a "dark ratio" per niche (share of domains with `totalElements == 0`), shown with the sample size stated openly.
