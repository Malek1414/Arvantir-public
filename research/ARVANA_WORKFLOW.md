# Wie Arvana arbeitet (aus den öffentlichen Repos ihrer Leute)

Stand 31.10.2026, 13:30. Terminal 4d. Jede Aussage hat eine Quelle in eckigen Klammern, Liste unten.
**Belegt** heißt: steht so im Repo. **Abgeleitet** heißt: unser Schluss daraus, als solcher markiert.

## Kurzfassung

1. Arvanas komplette GTM-Logik ist öffentlich: 12 Claude-Code-Skills in drei Stufen (Research, Qualifizierung, Copy), "gebaut aus der Analyse von hunderten Clay-Tables", gesteuert aus Claude Code, Daten in Clay-Tables über das Clay Agent Plugin [S1].
2. **Alle 12 Skills setzen eine fertige Liste oder Domain voraus. Keiner findet Accounts.** Die Stufe "woher kommen die Firmen" fehlt komplett [S1, S2–S13]. Genau dort dockt Arvantir an.
3. Ihre echte Lead-Liste kommt aus Messe, LinkedIn-Export, Listenkauf, Webinar und Altbestand, "gewachsen, mehrfach zusammenkopiert, in wechselnder Qualität" [S14, S15].
4. Ihre Qualitätsregeln sind hart und gut: Muss-Filter vor Scoring, Tier A–D, "unbekannt ist nicht nicht erfüllt", jeder Befund mit Quelle, Datum, Konfidenz [S6, S7, S8]. Arvantir muss genau in diesen Begriffen liefern, sonst passt es nicht in ihre Kette.

## 1. Pipeline Schritt für Schritt

| # | Schritt | Wie Arvana es macht | Werkzeug | Quelle |
|---|---|---|---|---|
| 1 | Auftrag | "Ein Kunde sagt uns, wen er erreichen will" | Kickoff, ~3 Wochen bis Launch | [S14], [ARVANA.md] |
| 2 | ICP festlegen | Kriterien-Tabelle: Kriterium, Gewicht (Summe 100), "Messbar-Machung" (woran erkennt man es, aus welcher Quelle), MUSS-Kriterien ohne Gewicht | `icp-scorer` | [S6] |
| 3 | Lead-Quelle | Liste aus einem "Listen-Tool"; Spalte `quelle` mit Werten `messe-2025`, `linkedin-export`, `listenkauf`, `webinar`, `altbestand` | Clay, Listenanbieter (AI Ark/Lusha/Blitz sind Hackathon-Sponsoren) | [S15], [CHALLENGE.md] |
| 4 | Anreicherung | Clay-Enrichment-Spalten, dazu Research pro Account | `company-research-agent`, `technographic-qualifier`, `linkedin-profile-analyzer`, `job-posting-analyzer`, `news-signal-synthesizer` | [S1], [S2], [S8] |
| 5 | Scoring (passt der Account?) | Muss-Filter zuerst, verfehlt = Tier D. Dann je Kriterium: erfüllt = volle Punkte, teilweise = halbe, nicht = 0, unbekannt = 0 **plus Datenlücke** | `icp-scorer` | [S6] |
| 6 | Timing (jetzt?) | Signal-Score: hoch 3, mittel 2, niedrig 1, Kombi-Bonus +2; nur Signale jünger als 6 Monate | `buying-signal-detector` | [S7] |
| 7 | Copy | Erstzeile aus genau einer Beobachtung, Sequenz 3–5 Steps (Hook, Value, Proof, Breakup), Sie-Form, DACH | `personalization-writer`, `email-sequence-writer` | [S10], [S11] |
| 8 | Versand | E-Mail + LinkedIn, getrennte aufgewärmte Domains | Smartlead (laut Website) | [ARVANA.md] |
| 9 | Replies einordnen | Heiß, Warm, Kalt, Referral, Absage, Abmeldung. "Genau die sind das Produkt, für das der Kunde bezahlt" | `objection-handler` für Antworten | [S14], [S12] |
| 10 | CRM + Report | Meetings ins Kunden-CRM (HubSpot/Pipedrive/Salesforce); Report pro Kampagne: angeschrieben, geantwortet, heiß/warm/kalt | Case-Study-Cockpit, Looker Studio | [S14], [ARVANA.md] |

Abgeleitet: Schritt 3 ist der einzige Schritt ohne eigenen Skill. Alles danach ist bei ihnen strukturiert, alles davor ist Listenkauf und Altbestand.

## 2. Tiers, Gewichte und Regeln (wörtlich aus icp-scorer)

- **A** 80–100: sofort ansprechen · **B** 60–79: nach A · **C** 40–59: nur mit starkem Signal · **D** < 40 oder Muss verfehlt: raus [S6]
- Beispiel-Gewichte (B2B-Tech-ICP): 20–500 MA = 30, laufende Paid Ads = 25, Marketing-Rolle im Haus = 25, Wachstum sichtbar = 20; MUSS: DACH-Sitz "laut Register / LinkedIn", B2B-Modell [S6]
- Verteilungs-Check: 80 % in A = Definition zu weich, 80 % in D = "Listenquelle falsch" [S6]
- Grenzfall (18 statt 20 MA): Tier D, aber als Grenzfall markieren [S6]
- Zwei Quellen widersprechen sich: konservativer Wert, Widerspruch als Datenlücke [S6]
- ICP-Score und Signal getrennt halten: "Ob JETZT der richtige Zeitpunkt ist, sagt buying-signal-detector" [S6]
- Signal-Scores aus verschiedenen Läufen nicht vergleichen, "die Basis verschiebt sich" [S7]
- Technographics: Konfidenz **belegt / wahrscheinlich / unbekannt**; älter als 6 Monate eine Stufe runter; Ausschluss nur bei "belegt"; "Feststellbarkeits-Quote" pro Kriterium, ab 80 % unbekannt taugt die Spalte nicht als Filter [S8]
- Sehr kleine Firmen: "wenig Fußabdruck … dann ist Datenlücke das normale Ergebnis" [S8]. Abgeleitet: genau das sind Bäckereien, Waschanlagen, Praxen. Ihre Skills sind auf B2B-Tech gebaut und brechen bei den Hackathon-Nischen.

## 3. Datenmodell und Spaltennamen

**Lead-Liste** (`leads_export.csv`, 215 Zeilen) [S15]:
`vorname, nachname, email, position, firma, domain, quelle, erfasst_am`

**Postfach-Export** (`inbox_*.json`) [S16]:
`postfach, export_erstellt_am, nachrichten[]: message_id, von_name, von_email, an, betreff, empfangen_am, text`

**Sperrliste** (`sperrliste.txt`): Domains von "Bestandskunden, Wettbewerbern, Beschwerden" [S17]

**Kampagne**: gehört zu einem Kunden, hat einen Namen [S14]

**Clay-Spalten, die die Skills zurückschreiben** (Namen aus dem Skill-Text, keine festen Spalten-IDs) [S2–S13]:
Score, Tier, Datenlücken (steuert "welche Enrichments nachgekauft werden"), Signal-Score, frischestes Signal, Befund + Konfidenz, Größe, Stack, Top-Signal, Angle, Zeitfenster (wann der Angle verfällt), Top-Ereignis, Hooks, Beobachtung, Einwand-Typ, Ergebnis

**Sequenz-Variablen**: `{{firstname}}`, `{{company}}`, `{{signal}}` [S11]

**Supabase**: kein öffentliches Schema gefunden. Abgeleitet: die Cockpit-Case-Study (Kampagne, Empfänger, Antworten an einem Ort) ist sehr wahrscheinlich das, was intern in Supabase liegt.

## 4. Ihre Begriffe (so in Arvantir-Output und Pitch verwenden)

Signal-Based Outbound · ICP · Muss-/Kann-Kriterium · Messbar-Machung · Tier A–D · Datenlücke · Konfidenz belegt/wahrscheinlich/unbekannt · Feststellbarkeits-Quote · Kaufsignal · Play · Aufhänger · "Nicht anfassen" · Angle · Hook · Breakup · Sperrliste · Altbestand · Listenkauf · Heiß/Warm/Kalt/Referral/Absage/Abmeldung · Clay-Table · Clay Agent Plugin [S1–S17]

## 5. Wo es hakt (mit Beleg)

1. **Keine Account-Discovery.** Jeder Skill-Input ist "Account (Domain) oder Liste, z. B. aus einer Clay-Table" [S2–S8]. Neue Firmen kommen nur über Kauf, Messe, Webinar, Altbestand [S15].
2. **Alte Daten.** 147 von 215 Leads wurden 2025 erfasst, 68 im Jahr 2026; 57 stammen aus dem Altbestand [S15, eigene Auszählung]. Passt zur öffentlichen Kritik "weak or outdated data" [ARVANA.md].
3. **Schmutzige Listen.** 33 von 215 Leads ohne E-Mail; dieselbe Firma als "Hafenblick Group GmbH", "Hafenblick Group", "hafenblick group"; Sperrliste mit Großbuchstaben, `www.` und Leerzeichen [S15, S17, eigene Auszählung]. Abgeleitet: das ist Stephans "Normalisierung"-Thema und der Grund für sein Kleppmann-Buch.
4. **Sperrliste greift nicht.** Reply im Export: "Wir sind seit zwei Jahren Kunde bei Ihnen. Warum bekomme ich so eine Mail?" [S16]
5. **Replies ohne Zuordnung.** Je 4 Absender pro Export sind nicht in der Lead-Liste (Weiterleitungen, "ich übernehme das Thema von …"), dazu Bounces, Abwesenheitsnotizen und 11 doppelte `message_id` zwischen beiden Exporten [S16, eigene Auszählung].
6. **Kein Lernen aus Replies.** Kein Skill nutzt Heiß/Warm-Ergebnisse, um neue ähnliche Accounts zu finden; `objection-handler` schreibt nur den Einwand-Typ zurück [S12].

## 6. Genau hier dockt Arvantir an

Abgeleitet aus 1–5. Die Umsetzung (Skill, Adapter, Schema) macht Terminal e5 in `adapters/` und `skills/arvantir/`; hier steht nur der Vertrag.

**Position in der Kette:** als 13. Skill **vor** Schritt 3. Arvantir ersetzt den Listenkauf für Nischen, die AI Ark und Co. nicht kennen, und füttert danach unverändert ihre Kette (`technographic-qualifier` → `icp-scorer` → `buying-signal-detector` → Copy).

**Eingabe** (so wie Stephan es heute schon hat):
1. ICP als Kriterien-Tabelle im `icp-scorer`-Format: `kriterium, gewicht, messbar_machung, muss (ja/nein)` [S6]
2. Nische als Freitext (die Jury gibt eine eigene vor) [CHALLENGE.md]
3. Sperrliste als Domain-Liste, gleiches Format wie `sperrliste.txt` [S17]
4. Optional: bestehende Clay-Table oder `leads_export.csv` zum Abgleich (nur neue Firmen zählen, "Only leads not in AI Ark count") [S15], [CHALLENGE.md]

**Ausgabe** (CSV, Spalten 1–8 identisch mit ihrem Export, damit der Upload ohne Mapping geht):

| Spalte | Inhalt | Warum |
|---|---|---|
| `vorname, nachname, email, position, firma, domain` | wie [S15] | ihr Format |
| `quelle` | konkrete Fundstelle, z. B. `messe:<name>`, `verzeichnis:<name>` statt `listenkauf` | gleiche Spalte, ehrlicherer Wert [S15] |
| `erfasst_am` | Scrape-Datum (heute) | löst "alte Daten" |
| `quelle_url` | Link zur Fundstelle | "Jeder Befund hat eine Quelle" [S6] |
| `firmen_key` | Handelsregister (Gericht + HRB), sonst normalisierte Domain | eine Firma = eine Zeile, löst Punkt 5.3 |
| `icp_score`, `tier` | 0–100, A–D nach ihren Grenzen | direkt in ihre Tier-Logik [S6] |
| `datenluecken` | was fehlt, nach Häufigkeit | ihre Lücken-Spalte steuert Nachkauf [S6] |
| `konfidenz` | belegt / wahrscheinlich / unbekannt je Feld | ihre drei Stufen [S8] |
| `in_ai_ark` | ja/nein | Dark-TAM-Beweis [CHALLENGE.md] |
| `gesperrt` | ja/nein nach normalisierter Sperrliste | löst Punkt 5.4 |
| `kanal` | Mail / LinkedIn / Brief / Fax | Bäckereien sind nicht per Mail erreichbar [CHALLENGE.md] |

**Montag bei Stephan:** CSV in die Clay-Table laden oder per Clay Agent Plugin schreiben lassen, danach laufen seine 12 Skills ohne Änderung weiter [S1]. Für Supabase: dieselben Spalten als Tabelle `leads`, Rohfunde unverändert in einer eigenen Tabelle (System of Record), die Lead-Tabelle daraus neu baubar [ARVANA.md].

**Pitch-Satz (abgeleitet):** "Eure 12 Skills fangen bei einer Liste an. Arvantir ist der Skill davor: er baut die Liste aus Quellen, die keine Datenbank kennt, im Format eurer Clay-Table, mit Tier, Datenlücken und Konfidenz nach euren eigenen Regeln."

## Quellen

- [S1] https://github.com/stephanmundtcode/claude-gtm-skills (README, Commit fdd7875 vom 28.07.2026)
- [S2] https://github.com/stephanmundtcode/claude-gtm-skills/blob/master/company-research-agent/SKILL.md
- [S3] https://github.com/stephanmundtcode/claude-gtm-skills/blob/master/account-brief-generator/SKILL.md
- [S4] https://github.com/stephanmundtcode/claude-gtm-skills/blob/master/job-posting-analyzer/SKILL.md
- [S5] https://github.com/stephanmundtcode/claude-gtm-skills/blob/master/news-signal-synthesizer/SKILL.md
- [S6] https://github.com/stephanmundtcode/claude-gtm-skills/blob/master/icp-scorer/SKILL.md
- [S7] https://github.com/stephanmundtcode/claude-gtm-skills/blob/master/buying-signal-detector/SKILL.md
- [S8] https://github.com/stephanmundtcode/claude-gtm-skills/blob/master/technographic-qualifier/SKILL.md
- [S9] https://github.com/stephanmundtcode/claude-gtm-skills/blob/master/linkedin-profile-analyzer/SKILL.md und …/competitor-analyzer/SKILL.md
- [S10] https://github.com/stephanmundtcode/claude-gtm-skills/blob/master/personalization-writer/SKILL.md
- [S11] https://github.com/stephanmundtcode/claude-gtm-skills/blob/master/email-sequence-writer/SKILL.md
- [S12] https://github.com/stephanmundtcode/claude-gtm-skills/blob/master/objection-handler/SKILL.md
- [S14] https://github.com/stephanmundtcode/kampagnen-cockpit-case-study/blob/main/Arvana-Case-Study-Kampagnen-Cockpit.pdf
- [S15] https://github.com/stephanmundtcode/kampagnen-cockpit-case-study/blob/main/data/leads_export.csv (fiktive Namen laut README)
- [S16] https://github.com/stephanmundtcode/kampagnen-cockpit-case-study/tree/main/data (inbox_2026-03-16.json, inbox_2026-03-18.json)
- [S17] https://github.com/stephanmundtcode/kampagnen-cockpit-case-study/blob/main/data/sperrliste.txt
- Interne Dateien: `context/ARVANA.md`, `context/CHALLENGE.md`
