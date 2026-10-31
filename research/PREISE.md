# Was kostet ein Lead bei den anderen?

Stand: 31.10.2026, 15:30. Alle Preise stammen von der öffentlichen Preisseite, die in der Spalte Quelle verlinkt ist. Bei Jahrespreisen ist der Monatswert angegeben. Die Werte pro 1.000 sind umgerechnet: Planpreis geteilt durch Credits, mal Credits pro Lead. Sie gelten nur, wenn das volle Kontingent verbraucht wird. "unklar" bedeutet, dass die Preisseite die Zahl nicht nennt.

| Anbieter | Kleinster bezahlter Plan | Pro Credit | Pro 1.000 Firmen | Pro 1.000 Kontakte mit Entscheider und E-Mail | Quelle | Stand |
|---|---|---|---|---|---|---|
| AI Ark | 49 USD/Monat, 5.000 Credits | 0,0098 USD (über 30k Credits nur 0,002 bis 0,004 USD) | 0,98 USD (0,1 Credit je Firma) | 9,80 USD (1 Credit: 0,5 Profil + 0,5 E-Mail; ohne gültige E-Mail nur 0,5) | ai-ark.com/pricing | 31.10.2026 |
| Lusha | 37,45 USD/Monat bei Jahreszahlung, 4.800 Credits/Jahr | 0,094 USD | unklar | 94 USD (1 Credit je E-Mail; eine Telefonnummer kostet 5 Credits) | lusha.com/pricing | 31.10.2026 |
| BlitzAPI | 99 USD/Monat Flatrate, Fair Use 200.000 Records | kein Credit, 1 Record = 0,0005 USD bei voller Nutzung | 0,50 USD | 0,99 USD (Person + E-Mail = 2 Records); Mindestbetrag 99 USD | blitz-api.ai/pricing | 31.10.2026 |
| Clay | Launch ab 185 USD/Monat (167 USD bei Jahreszahlung), 3.000 Data Credits/Monat | ca. 0,06 USD | unklar, die Credits pro Lead hängen vom gewählten Datenanbieter ab | unklar, wie bei Firmen | clay.com/pricing | 31.10.2026 |
| Apollo.io | Basic 49 USD pro Nutzer/Monat, 30.000 Credits/Jahr | 0,0196 USD | unklar | ca. 19,60 USD, falls 1 Credit je E-Mail; die Preisseite nennt die Credits pro E-Mail nicht | apollo.io/pricing | 31.10.2026 |
| Cognism | nur auf Anfrage | unklar (1 Credit je aufgedecktem Kontakt) | unklar | unklar | cognism.com/pricing | 31.10.2026 |
| Dealfront (Leadfeeder/Echobot) | Lite 79 EUR/Monat bei Jahreszahlung; E-Mails erst ab Activate 599 EUR/Monat | unklar | unklar; Firmenexport erst ab Activate ohne Credits | unklar | dealfront.com/pricing | 31.10.2026 |
| North Data | Premium Basic 49 EUR/Monat, 10 CSV-Exporte pro Tag mit je 500 Treffern | kein Credit | ca. 0,01 EUR bei voller Nutzung (49 EUR für bis zu 150.000 Zeilen) | keine Kontakte, nur Registerdaten und Geschäftsführer ohne E-Mail | northdata.com/_premium | 31.10.2026 |
| Deutsche Post Direkt Firmenadressen | Paket S mit 1.000 Adressen für 479 EUR, einmalig | – | 479 EUR (bei 10.000 Adressen 199 EUR pro 1.000) | Entscheider gegen Aufpreis, ohne E-Mail, nur Postadresse | deutschepost.de, PDF "B2B-Adresspakete" | aus PIPELINES.md |
| Google Places über serper.dev | 50 USD für 50.000 Credits, 6 Monate gültig, kein Abo | 0,001 USD (ab 2,5 Mio Credits 0,0005 USD) | unklar, abhängig davon, wie viele Credits ein Places-Call kostet und wie viele Treffer er liefert | keine Kontakte, nur Firma, Adresse, Telefon und Website | serper.dev | 31.10.2026 |

Zum Vergleich auf einen Blick:
- Kontakte mit E-Mail kosten zwischen 1 USD (BlitzAPI bei voller Flatrate) und 94 USD (Lusha) pro 1.000.
- Firmen kosten zwischen 0,50 USD (BlitzAPI) und 479 EUR (Post-Adressen) pro 1.000.

## Was Arvantir kostet

Im aktuellen Lauf fallen keine Lizenz- oder API-Kosten pro Lead an. Arvantir findet die Firmen über DuckDuckGo, die eigene lokale Suche, Gelbe Seiten, 11880 und das Impressum der Firmen-Websites. Kosten entstehen nur hier:

1. Rechenzeit auf dem eigenen Rechner.
2. Optional Serper oder Exa für LinkedIn-Signale in signals.py. Bei Serper sind das ca. 1 USD pro 1.000 Abfragen. Ohne diese Dienste greifen Google News RSS und die lokale Suche.
3. AI Ark nur für den Dark-Check. Kennt AI Ark eine Firma, kostet das 0,1 Credit. Kennt AI Ark sie nicht, kostet es nichts, und genau das sind die dunklen Firmen, auf die es ankommt.
4. Porto für Briefe. Briefe sind der rechtlich saubere Kanal nach UWG § 7. E-Mail und Fax brauchen vorher eine ausdrückliche Einwilligung, auch zwischen Firmen.

Die Firmen, die Arvantir findet, stehen in keiner der Datenbanken oben. Deshalb lässt sich der Preis nicht 1:1 vergleichen: Kein Anbieter verkauft sie zu irgendeinem Preis.
