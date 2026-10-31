# Pipelines, die Lead-Datenbanken nicht nutzen (31.10.2026, ~13:45)

Hergeleitet aus Arvanas Problemen (context/ARVANA.md, Recherche vom 30.10.) plus zwei Recherche-Agents. [c] = per curl geprüft, [w] = Vorwissen.

## Was Arvana fehlt, und welche Pipeline darauf antwortet

| Problem (belegt) | Pipeline | Kosten | Pitch-Satz |
|---|---|---|---|
| Kunden: Daten veraltet | Live-Quellen statt Datenbank-Snapshot: ATS-Feeds, Startup-RSS, Verzeichnisse beim Lauf frisch gescrapt, jedes Feld mit Zeitstempel | gratis | "Jeder Wert hat Quelle und Datum, nichts ist älter als der Lauf." |
| Kunden: zu wenige Leads | Dark TAM aus Verzeichnissen (SOURCES.md) + Postadressen (Deutsche Post Direkt) für Firmen ohne Web-Footprint | gratis bzw. ab 479 EUR/1.000 | "Wir finden die Firmen, die AI Ark nicht kennt, und messen den Anteil." |
| Kein Standard für "qualifizierter Lead" | Drei objektive Signal-Felder: `hiring_sales` (ATS), `funded_90d` (Startupdetector), `runs_google_ads` (BigQuery) plus `in_ai_ark` | gratis | "Qualifiziert heißt: messbares Kaufsignal, nicht Bauchgefühl." |
| Agent-Sortierung unzuverlässig, Handsortierung | Re-Ranker gegen Seed + Begründung + Quelle, nur unsichere Fälle an Menschen (`needs_human`) | lokal | "Der Mensch sortiert nur noch die 10 % unsicheren Fälle." |
| CTO: bessere Daten für SDRs, Normalisierung | Entity-Key HRB > Domain > Name+PLZ, Provenienz pro Feld (BUILD_PLAN) | gratis | "Ein Unternehmen, eine Zeile, jede Quelle sichtbar." |
| Kanal: E-Mail/LinkedIn greift bei Bäckern/Ärzten nicht, UWG | Brief als Standard, Postadressen-Daten sind dafür lizenziert | Porto | "Rechtssicher und dort, wo die Zielgruppe wirklich liest." |

## Gratis-Signale (heute baubar)

1. **ATS-Hiring** [c]: `boards-api.greenhouse.io/v1/boards/{slug}/jobs`, `api.lever.co/v0/postings/{slug}?mode=json`, `api.ashbyhq.com/posting-api/job-board/{slug}`, ohne Key. Titel-Filter SDR/BDR/Vertrieb/Head of Growth = braucht jetzt Outbound. Slug aus der Domain raten.
2. **Funding** [c]: `https://startupdetector.de/feed/`, `https://www.deutsche-startups.de/feed/` (RSS), Firma und Betrag per LLM aus dem Titel.
3. **Google Ads Transparency** [c Dataset, Login nötig]: BigQuery `bigquery-public-data.google_ads_transparency_center`, Region DE, letzte 30 Tage, Advertiser -> Domain. Wer Ads schaltet, hat Budget, passt zu Arvanas Paid-Ads-Geschäft.
4. **Arbeitsagentur Jobsuche** [w]: `jobsuche.api.bund.dev`, gratis, viele Kleinfirmen als Arbeitgeber.
5. **Technografie** [w]: PublicWWW-Suche nach `js.hs-scripts.com` (HubSpot neu = Sales-Stack im Umbau), Key ab ca. 60 USD/Monat.

## Bezahlt, aber dunkel (für Arvana als Produkt-Pitch)

# Datenwege (Stand 31.10.2026). [c]=heute auf Anbieterseite geprüft, [w]=Vorwissen/ungeprüft
| Anbieter | URL | Inhalt | Zugang | Preis | Kleinstfirmen | in großen DBs? | Beleg |
|---|---|---|---|---|---|---|---|
| North Data Quartalsexport | northdata.de/_data | Handelsregister, Historie, Insolvenzen, Vertreter (L), Finanzen/Mitarbeiter/Patente/Marken (XL), Anteilseigner (XXL) | JSON/CSV Quartals-Abo, 12 Mon. Mindestlaufzeit, kein Weiterverkauf | M 2.250 EUR, L 3.750 EUR pro Quartal+Land; XXL 7.950 EUR (XL-Preis nicht abgelesen); zzgl. MwSt | nur Registerfirmen (GmbH/UG/KG..), kein Einzelunternehmen; Mitarbeiter nur aus Abschlüssen | Nein (Register-Rohdaten) | [c] |
| North Data Data API | northdata.de/_data | wie oben, pro Firma | JSON/XML API | 500 EUR/Monat inkl. 5.000 Abrufe, danach Staffel pro Abruf; Startup-Paket 500 EUR/Monat auf 1.000 Abrufe inkl. Premium-Lizenz | wie oben | Nein | [c] |
| North Data Premium | northdata.de/_premium | Suche + CSV-Export | Web, 10-200 CSV-Exporte/Tag | 49 EUR, 490 EUR, 1.250 EUR, 2.250 EUR, 3.950 EUR /Monat (Tarifstufen; Zuordnung nicht verifiziert) | wie oben | Nein | [c] |
| Deutsche Post Direkt Firmenadressen | deutschepost.de/en/d/deutsche-post-direkt/firmenadressen.html, PDF dp-ddp-si-b2b-adresspakete | ca. 3 Mio Geschäftsadressen, Branche + Dachmarkt; Zusatz: Mitarbeiter, Umsatz, Entscheider, Gründung, Eigenkapital, Rechtsform | Online-Download, Miete einmalig; Jahresnutzung = 1,5x | S 1.000 = 479 EUR, M 3.000 = 889 EUR, L 5.000 = 1.249 EUR, XL 10.000 = 1.989 EUR; je Merkmal +0,25 Einheit/Adresse; Selektion Handlingpauschale | Basis ja (Gewerbe, auch klein), Merkmale lückenhaft [w] | Nein, Postadresse ist deren Kern; Apollo/ZoomInfo haben kaum DE-Postadressen | [c] |
| CompanyData | companydata.com/de/adressen-kaufen | angeblich 6,75 Mio DE-Firmen, Filter Branche/Region/Größe | Plattform-Export CSV | ab 34 EUR/Monat; 5.000 Adressen 386 EUR einmalig (ca. 9 ct); Staffel bis 2 ct | Ja (laut Eigenwerbung, Qualität ungeprüft) | Nein | [c] Preis, Qualität ungeprüft |
| IHK-Firmenadressen | z.B. ihk.de/lippe-detmold Adressverkauf, IHK Lübeck | Kammermitglieder, Selektion nach Branche/Ort | Antrag, Liste | 15 EUR Grund inkl. 50 Adressen, danach 0,15-0,20 EUR/Adresse; Ansprechpartner oft nicht | Ja, alle Gewerbetreibenden der Kammer | Nein | [c] Suchsnippet |
| BuiltWith | builtwith.com/plans | Technografie, Listen nach Tech + Land (.de) | Web, CSV/Excel, API, MCP | 295 / 495 / 995 USD pro Monat (Plan-Zuordnung nicht verifiziert) | Nur Firmen mit Website | Teils (ZoomInfo/Apollo haben eigene Tech-Tags, aber nicht Rohdomain-Listen) | [c] |
| Vainu | vainu.com/pricing | Länder-DB (Nordics, DE), Trigger | App/CRM | ab 250 EUR/Monat (Jahresvertrag, je Land/Paket) | mittel [w] | Nein [w] | [c] Preis |
| Implisense | implisense.com/de | ca. 2,3 Mio Firmen, Register, Finanzen, Management, Signale | Web-App, API, Managed Service | nicht öffentlich | mittel | Nein [w] | [c] Inhalt |
| Arbeitsagentur Jobsuche API | jobsuche.api.bund.dev | Stellenanzeigen + Arbeitgeber | REST, X-API-Key (öffentlicher Client-Key) | kostenlos | Ja, viele Kleinfirmen | Nein | [c] |
| Bundesanzeiger/Unternehmensregister Abruf | unternehmensregister.de | Jahresabschlüsse (Mitarbeiter, Umsatz) | Einzelabruf; Bulk nur via Reseller wie North Data | Abruf pro Dokument [w], Seiten nicht lesbar | Nur bilanzpflichtige | Nein | [w] |
| DTAD, Vergabe24, Tender Impulse, Dealfront/Echobot, Creditreform, Bürgel, D&B DE, Index Research, Textkernel, HG Insights, Wappalyzer | - | Seiten per Jina leer oder nicht öffentlich | - | Preise nur auf Anfrage [w] | - | Creditreform/D&B/HG: ja teils; Ausschreibungs-Zuschlagsdaten: nein [w] | NICHT geprüft |
Hinweis Lizenz: Post-Adressen sind für Briefwerbung gebaut (Miete). North Data: nur Datenverwendung vertraglich eingeschränkt, Werbenutzung vorher schriftlich klären. Keine Rechtsberatung.

## Signal-Details (Agent-Notizen)

# Kaufsignal-Pipelines (31.10.2026) [c]=per curl geprüft, [w]=Vorwissen
1. Hiring-Signal Vertrieb/Growth via ATS-Public-APIs [c] Greenhouse boards-api.greenhouse.io/v1/boards/{slug}/jobs (200, ohne Key), Lever api.lever.co/v0/postings/{slug}?mode=json (200), Ashby api.ashbyhq.com/posting-api/job-board/{slug} (200). Kostenlos. Filter title ~ SDR|BDR|Head of Growth|Demand Gen. Slug-Liste aus Clay/Domain raten. SmartRecruiters v1 postings [c] 200 (leer bei bosch, API lebt). Arbeitsagentur-Jobsuche-API [c] 403 ohne X-API-Key (Key öffentlich in der jobsuche-App, [w]).
2. Meta Ad Library [c] Web-Endpunkt hinter JS-Challenge (403 curl). API graph.facebook.com/ads_archive braucht Token + ID-Verifizierung, in EU nur Ads mit politischem/EU-Targeting vollständig [w]. Signal: Budget + Paid-Ads-Reife. Fallback: Apify-Actor.
3. Google Ads Transparency BigQuery bigquery-public-data.google_ads_transparency_center [c] API antwortet 401 (Dataset existiert, braucht Google-Login/GCP-Projekt; 1 TB/Monat frei [w]). Tabellen creative_stats, advertiser_stats [w]. Abfrage: advertiser_location/region DE, letzte 30 Tage, advertiser_disclosed_name -> Domain. Signal: schaltet jetzt Google Ads.
4. Startupdetector RSS [c] startupdetector.de/feed/ 200, Deutsche Startups /feed/ 200 (Funding-Tag-Feed 403). Signal: frisch finanziert/gegründet DACH, kein Key. Per Claude Titel -> Firma/Betrag extrahieren.
5. Technografie-Wechsel: PublicWWW [c] erreichbar, API-Key bezahlt (~ab 60 $/Monat [w]); Abfrage "js.hs-scripts.com" + .de -> HubSpot-Nutzer; Diff Woche zu Woche = Wechsel. Alternative: eigener Snapshot von Kundenliste (Wappalyzer-OSS-Fingerprints, billiger).
6. Handelsregister-Bekanntmachungen: handelsregisterbekanntmachungen.de [c] nicht abrufbar (Redirect/000), North Data [c] Seite 200 aber API kostenpflichtig [w]; offenerregister.de Timeout. Schwach, nicht priorisieren.
Nicht erreichbar: OMR Reviews (301, Pfad geändert), LinkedIn Ad Library (kein API, [w]).
