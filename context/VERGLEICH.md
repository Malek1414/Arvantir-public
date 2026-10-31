# Arvana heute, Arvantir heute, Potenzial, zusammen

Stand 31.10.2026, 15:40. Gemessen = aus `bench/RUNS.md` und `bench/results.md`. Potenzial = Schätzung, nicht gemessen. Preise aus `research/PREISE.md` (Preisseiten, Stand 15:32).

| | Arvana heute | Arvantir heute (gemessen) | Arvantir Potenzial (Schätzung) | Arvana + Arvantir zusammen |
|---|---|---|---|---|
| Woher die Firmen kommen | Datenbanken, Listenkauf, Messe, LinkedIn-Export, Altbestand | Findet die Listen selbst: Branchenbücher, Verbände, Register, Partnerverzeichnisse | Mehr Quellen je Nische, Verbands-PDFs, Messelisten | Datenbank für die bekannten Firmen, Arvantir für den Rest |
| Nischen wie Metzger, Apotheken, Waschanlagen | kaum in Datenbanken | 6 Nischen laufen komplett durch | jede Nische, die irgendwo öffentlich gelistet ist | keine Nische fällt mehr raus |
| Firmen je Nische | so viele wie die Datenbank kennt | 86 bis 240 ausgelesen, 60 gerankt (unser Tageslimit) | Tausende, z. B. 9.874 Anlagen auf waschanlagen-deutschland.de | volle Liste statt dünner Liste |
| Entscheider | aus Datenbank, kostet Credits | 134 von 347 Leads (39 %) aus dem Impressum, gratis | etwa 60 bis 75 % mit Handelsregister und bezahlter Quelle nur für die Spitze | Impressum zuerst, Credits nur für Top-Leads |
| Sortieren | ICP-Score mit festen Gewichten, viel per Hand | trainierter Re-Ranker: NDCG@10 0,764 (feste Gewichte 0,608), 98 % passt/nein-Übereinstimmung mit Hand-Labels | über 0,8 mit Arvanas eigener Handsortierung als Training | Re-Ranker sortiert vor, Menschen prüfen nur die unsicheren Fälle |
| Begründung je Lead | Tier ohne Satz | Satz plus Quell-Link, Datenlücken, Konfidenz | gleich, mit besseren Quellen | SDR sieht, warum ein Lead oben steht |
| Aktualität | Datenbank-Stand, Kritik an veralteten Daten | heute abgerufen, Signale jünger als 6 Monate (News, Hiring, Funding) | plus LinkedIn-Posts von heute (braucht Serper- oder Exa-Guthaben) | jeder Lead mit Datum der Quelle |
| Kanal | Mail und LinkedIn | Brief, Telefon oder LinkedIn je Lead, §7 UWG beachtet (bei Bäckern und Metzgern 40 von 47 Brief) | Brief-Versand per API | Mail, wo erlaubt, Brief für lokale Betriebe |
| Kosten pro 1.000 | AI Ark 9,80 USD je 1.000 Kontakte mit E-Mail, Lusha 94 USD, Deutsche Post Direkt 479 EUR je 1.000 Firmenadressen (`research/PREISE.md`) | keine Lizenz- oder API-Kosten pro Lead; AI-Ark-Abgleich 0 Credits für dunkle Firmen, 0,1 für bekannte | Credits nur für Top-Leads | Datenbank bleibt günstig für bekannte Firmen, Arvantir kostet nichts für den Rest |
| Ins System | Clay-Tabelle | CSV im Clay-Format, Supabase-Schema, Webhook | direkt als Clay-Quelle | Arvantir füllt die Clay-Tabelle, alles danach bleibt wie es ist |

## Ein Satz

Arvana bleibt bei Clay und seinem Ablauf. Arvantir kommt davor und liefert die Firmen, die keine Datenbank kennt: mit Entscheider, Begründung und Kanal, ohne Kosten pro Lead.

## Ehrlich zu den Kosten

Datenbanken sind pro Kontakt schon billig (AI Ark 9,80 USD je 1.000). Der Vorteil von Arvantir ist nicht der Preis, sondern dass es die Firmen findet, die dort gar nicht drin sind. Der faire Preisvergleich für lokale Betriebe ist die Deutsche Post Direkt mit 479 EUR je 1.000 Adressen, ohne Entscheider und ohne Sortierung.
