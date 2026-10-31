# Research-Auftrag für das Searchify-Terminal (31.10.2026, GTM Hackathon Arvana)

Kontext: Wir bauen "Arvantir", ein Palantir für Arvana. Eine auf Arvanas Folien zugeschnittene Searchify-Engine, die den "Dark TAM" findet: Firmen, die in keiner Lead-Datenbank stehen. Nur Leads, die NICHT in AI Ark sind, zählen. Repo: ~/Desktop/APP/gtm-arvana/Arvantir (context/CHALLENGE.md, context/BUILD_PLAN.md, context/slides/). Abgabe 17:00, wir brauchen die Ergebnisse bis spätestens 14:00, erste Teilergebnisse ab 13:30.

## Ziel

Für jede der 6 Nischen von der Folie konkrete, scrapebare Quellen in Deutschland finden, die die Engine als Startpunkte und als Few-Shot-Beispiele für die Quellensuche nutzt:

1. Bäckereien & Metzgereien
2. Waschanlagen
3. IT-Dienstleister (nischige)
4. Ärzte & Apotheken
5. Family Offices & LPs
6. Asset Manager (vor allem Immobilien) inklusive Portfoliogröße (Anzahl Objekte, m², AuM)

Quellentypen laut Folie: Partnerverzeichnisse, Messe-Ausstellerlisten, Vergleichsportale. Dazu: Verbands- und Innungs-Mitgliederlisten, Handwerkskammer-Verzeichnisse, öffentliche Register (BaFin-Unternehmensdatenbank, KV-Arztsuche, Apothekenfinder), PDF-Mitgliederlisten.

## Pro Nische 3 bis 6 Quellen, je Quelle

- direkte URL zur Liste (nicht die Startseite)
- Quellentyp (Partnerverzeichnis / Aussteller / Vergleichsportal / Verband / Register / PDF)
- ungefähre Anzahl Einträge
- welche Felder pro Eintrag sichtbar sind (Name, Website, Ort, Ansprechpartner, Telefon, E-Mail)
- Format und Technik: statisches HTML / JS-gerendert / PDF / API, Paginierung, Bot-Schutz, Login nötig ja/nein
- Einschätzung "dunkel": wie wahrscheinlich sind diese Firmen NICHT in großen B2B-Datenbanken (hoch/mittel/niedrig, ein Satz Begründung)

## Zusätzlich

- Asset Manager: wo steht die Portfoliogröße öffentlich (Objekte/Portfolio/Referenzen-Seiten, Bundesanzeiger, Pressemitteilungen, Rankings wie "Top 50 Asset Manager"), mit 2 bis 3 Beispielfirmen und Beleg
- AI Ark API: Endpunkt für company search (per Domain oder Name), Auth-Header, Antwortformat, Rate Limits, aus docs.ai-ark.com
- Rechtlich in einem Absatz: Scraping öffentlicher Verzeichnisse für B2B-Recherche in DE, und Briefwerbung vs. Fax/E-Mail (§7 UWG)

## Regeln

- curl / r.jina.ai / Searchify, KEIN sichtbarer Browser ohne Ansage
- Wellen von maximal 5 Agents
- jede URL selbst geprüft (erreichbar, zeigt wirklich eine Liste)
- keine personenbezogenen Daten in großen Mengen abziehen, nur Stichproben zur Formatprüfung

## Ablage

Ergebnis als `research/SOURCES.md` in ~/Desktop/APP/gtm-arvana/Arvantir, eine Tabelle pro Nische, dazu `research/sources.json` (Liste von Objekten mit niche, url, type, entries, fields, format, pagination, bot_protection, darkness, note). Teilstände früh schreiben (nach jeder Nische), committen und pushen auf main mit `git pull --rebase` davor. Nur die Dateien unter research/ anfassen.
