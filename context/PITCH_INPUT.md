# Input für /pitch (Stand 31.10.2026, 15:55)

Diese Datei sammelt alles, was beim nächsten `/pitch:pitch`-Lauf rein muss, sobald Sami die Website fertig hat. Das freigegebene Skript liegt in `pitch/arvantir/script.md` (alle Prüfungen bestanden, Nacherzähl-Test bestanden, ca. 1:50).

## 1. Trainingsergebnisse (Quelle: `bench/results.md`, 330 Gold-Paare)

| System | NDCG@10 | Übereinstimmung passt/nein | ms pro Lead |
|---|---|---|---|
| Feste Gewichte (Tier A-D) | 0.608 | 80 % | 0.3 |
| MiniLM untrainiert | 0.456 | 95 % | 15.7 |
| **MiniLM trainiert (arvantir-rr-v1)** | **0.764** | **98 %** | 16.6 |
| Trainiert, Nische ungesehen (70 Paare) | 0.894 | 81 % | 12.2 |

Im Skript als Fakten F6 und F7: "It now agrees with a human in 98 percent of cases. A fixed score reaches 80."
Grenzen, nicht im Video übertreiben: Waschanlagen nur 0.393 NDCG@10; die Zeile "Nische ungesehen" beruht auf 70 Paaren; Gold-Labels zweier Labeler stimmten nur zufällig überein (Kappa 0,05, `bench/DATA_QUALITY.md`).

## 2. Läufe (Quelle: `bench/RUNS.md`)

347 gerankte Leads über 6 Nischen, 134 mit Entscheider aus dem Impressum. Bäcker und Metzger: 40 von 47 bekommen Brief als Kanal.

## 3. Vergleich Arvana heute / Arvantir heute / Potenzial / zusammen

Volle Tabelle: `context/VERGLEICH.md`. Kurz:

| | Arvana heute | Arvantir heute | Potenzial (Schätzung) |
|---|---|---|---|
| Quelle | Datenbanken, Listenkauf, Messe | findet die Listen selbst | mehr Quellen je Nische |
| Firmen je Nische | was die Datenbank kennt | 86 bis 240, 60 gerankt | Tausende |
| Entscheider | Datenbank-Credits | 39 % aus dem Impressum | etwa 60 bis 75 % |
| Sortieren | feste Gewichte, viel per Hand | 0,764 / 98 % | über 0,8 mit Arvanas eigenen Labels |
| Kosten je 1.000 | AI Ark 9,80 USD, Post Direkt 479 EUR (`research/PREISE.md`) | keine Kosten pro Lead | Credits nur für die Spitze |

Ehrlicher Satz: Der Vorteil ist nicht der Preis, sondern die Abdeckung von Firmen, die in keiner Datenbank stehen.

## 4. Architektur als Animation (Website)

Fertig (474fc9d), live unter https://arvantir.5.45.109.195.sslip.io/architecture/?play bzw. lokal /architecture?play: zeigt die Kette Eingabe → discover, harvest, normalize, darkcheck, enrich, signals, rank, channel → Clay, Supabase, Web-Ansicht. Eine Firma läuft sichtbar durch die Kette und wird zur Tabellenzeile; danach blendet die Lernschleife mit 0,764 und 98 % ein. 15 bis 20 Sekunden, ohne Klick abspielbar. Im Video als Bild für Beat B5 oder B6.

## 5. Wer sagt was (2:00)

| Zeit | Beat | Wer | Bild |
|---|---|---|---|
| 0:00 | B1 Arvana sortiert von Hand | Sami | Gesicht |
| 0:08 | B2 Ihr Weg funktioniert, aber Nischen fehlen in Datenbanken | Sami | Gesicht |
| 0:26 | B3 Wir haben Arvantir gebaut | Sami | Gesicht, dann Startseite |
| 0:35 | B4 So funktioniert es (Demo) | Malek | Demo-Video, Vollbild |
| 1:05 | B5 Beweis: 347 Leads, 134 Entscheider, 98 % gegen 80 % | Malek | Funnel, dann Architektur-Animation |
| 1:23 | B6 Was das für Arvanas Vertrieb heißt, Stephans Skills als Grundlage | Sami | Gesicht |
| 1:43 | B7 Bitte: Nische für Montag | Sami | Gesicht |

Wortlaut: `pitch/arvantir/script.md`. Teleprompter: `pitch/arvantir/teleprompter.html` (Server: `python3 ~/editorpro-max/plugins/pitch/skills/pitch/scripts/prompter.py serve arvantir --port 8411` im Ordner `pitch/`).

## 6. Regeln für den Schnitt

- Stephans Skills nur im gesprochenen Video nennen, nicht auf der Website.
- "Nicht in AI Ark" nur mit Zahl, wenn der AI-Ark-Key gesetzt und ein Lauf damit gemacht ist.
- Fürs Video die Nischen IT-Dienstleister oder Asset Manager zeigen (stärkstes Ranking), Bäcker/Metzger für den Brief-Moment.
- Trainiertes Modell im Video nur zeigen, wenn `models/arvantir-rr-v1-final` auf Samis Mac liegt und `RERANKER_MODEL` gesetzt ist.
