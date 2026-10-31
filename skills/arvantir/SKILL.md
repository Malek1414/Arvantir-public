---
name: dark-tam-finder
description: Findet Firmen einer Nische, die in keiner Lead-Datenbank stehen (Dark TAM), aus Verbands-, Kammer-, Messe- und Partnerverzeichnissen, rankt sie mit einem Re-Ranker gegen das ICP (0-100, Tier A/B/C/D) und liefert eine Clay-fertige Liste mit Quelle, Datenlücken und Konfidenz. Nutzen, wenn für eine Kampagne die Liste fehlt oder AI Ark und Co. eine Nische nicht abdecken.
---

# Dark TAM Finder

Die anderen Skills fangen bei einer Liste an. Dieser baut sie. Er sucht in
öffentlichen Verzeichnissen (Verbandsmitglieder, Innungen, Aussteller,
Partnerverzeichnisse von Software-Herstellern), liest die Firmen aus, findet
ihre Website, prüft gegen AI Ark und sortiert alles mit einem Re-Ranker
gegen euer ICP. Der Wert liegt in den Firmen, die sonst niemand anschreibt:
Gekaufte Listen kennen sie nicht, deshalb ist das Postfach dort leer.

Technisch läuft dahinter Arvantir (`python -m arvantir run`), eine
GTM-Schicht über Searchify. Dieser Skill sagt Claude, wann und wie es
aufgerufen wird und wie das Ergebnis in eure Kette passt.

## Input

- Die Nische als Freitext (z. B. "Bäckereien mit eigener Backstube",
  "IT-Systemhäuser", "Waschanlagen") oder eine Beispiel-URL eines guten
  Kunden. Pflicht.
- Die ICP-Definition als Kriterien-Tabelle im Format von icp-scorer
  (Kriterium, Gewicht, Messbar-Machung, Muss ja/nein). Liegt keine vor:
  erst mit icp-scorer aufstellen. Ohne ICP rankt der Skill nur gegen die
  Nische, das ist für eine erste Marktgröße okay, für eine Kampagne nicht.
- Optional: die Sperrliste (`sperrliste.txt`, eine Domain pro Zeile) und
  die bestehende Lead-Liste (`leads_export.csv` oder Clay-Export), damit
  Bestandskunden gesperrt und schon bekannte Firmen markiert werden.
- Optional: Anzahl Quellen und Leads (Standard: 3 Quellen, Top 60).

## Workflow

1. **ICP übersetzen.** Muss-Kriterien werden harte Filter (Region,
   Rechtsform, Betreiber statt Hersteller) und laufen vor dem Ranking,
   nie als Gewicht. Die Kann-Kriterien als zwei bis vier Sätze
   ausformulieren, so wie man einen perfekten Kunden beschreiben würde:
   das ist die Query für den Re-Ranker. Konkrete Merkmale schlagen
   Adjektive ("mindestens drei Filialen, eigene Backstube" statt "mittelgroß").
2. **Lauf starten** (dauert 1 bis 3 Minuten):

   ```
   skills/arvantir/scripts/run.sh "<Nische>" "<ICP-Sätze>" \
       --sperrliste sperrliste.txt --bekannt leads_export.csv
   ```

   Das ruft die Pipeline und danach den Clay-Export. Der Funnel steht im
   Terminal: Quellen gefunden, Firmen ausgelesen, eindeutige Firmen, mit
   Website, nicht in AI Ark, mit Entscheider, gerankt.
3. **Quellen prüfen.** Für jede genutzte Quelle (Spalte `quelle_url`) kurz
   ansehen, ob sie wirklich eine Firmenliste der Nische ist. Quellen mit
   weniger als 5 Firmen oder unter 30 % echten Firmennamen verwirft die
   Pipeline selbst; eine fachfremde Liste mit vielen Firmen rutscht durch.
4. **Verteilung lesen** (steht unter dem Export): Tiers, Anteil
   "mensch_prueft", Dark-TAM-Anteil, häufigste Datenlücken. Landen 80 % in
   Tier A, ist die ICP-Query zu weich; landen 80 % in D, war die Quelle
   falsch oder die Query zu eng. Beides gehört in den Output.
5. **Grenzfälle an den Menschen.** Leads mit `mensch_prueft = ja` liegen
   nah an der Schwelle. Die gehen als eigene Ansicht an das SDR-Team,
   nicht stillschweigend in die Sequenz.
6. **Übergeben:** CSV in die Clay-Table laden (die ersten 8 Spalten sind
   identisch mit `leads_export.csv`), oder mit `--webhook` direkt in eine
   Clay-Webhook-Table, oder mit `python -m adapters.supabase --latest`
   nach Supabase. Gesperrte Domains gehen nie per Webhook raus.

## Output

Datei `data/run_<zeit>_arvana.csv` (und `.json`), eine Zeile pro Firma:

| Spalte | Inhalt |
|---|---|
| vorname, nachname, email, position, firma, domain | wie euer leads_export.csv, leer wenn noch kein Entscheider gefunden |
| quelle | konkrete Fundstelle, z. B. `verband:eco.de`, `messe:<host>` |
| erfasst_am | Tag des Laufs, also frisch |
| quelle_url | Link zum Eintrag im Verzeichnis |
| firmen_key | `reg:<gericht>\|<HRB>` > `dom:<domain>` > `name:<name>\|<PLZ>` |
| icp_score, tier | Re-Ranker 0-100, Tier nach euren Grenzen (A ab 80, B ab 60, C ab 40) |
| datenluecken | z. B. `entscheider; email; telefon` (steuert den Nachkauf) |
| konfidenz | belegt / wahrscheinlich / unbekannt |
| begruendung, begruendung_quelle | der Satz von der Firmen-Website, der am besten zum ICP passt, mit URL |
| mensch_prueft | ja, wenn der Score nah an der Schwelle liegt |
| in_ai_ark | nein = Dark TAM, unbekannt = nicht geprüft |
| gesperrt, bekannt | Treffer auf Sperrliste bzw. bestehender Liste |
| kanal | Mail, LinkedIn, Brief, Telefon, Fax (Fax nur mit Einwilligung) |

Dazu im Chat:

```
Nische: <n> · Quellen: <k> (mit Link) · Laufzeit: <s>
Funnel: <Quellen> → <Firmen> → <eindeutig> → <mit Website> → <nicht in AI Ark> → <gerankt>
Tiers A/B/C/D: <a>/<b>/<c>/<d> · Mensch prüft: <n> · gesperrt: <n> · schon bekannt: <n>
Top 10: Firma, Score, Tier, Begründung (ein Satz), Quelle
Häufigste Datenlücken: <lücke (anzahl)>, ...
Beobachtung: <Verteilung, auffällige Quellen, Vorschlag zur ICP-Query>
```

## Regeln

- Der Score kommt aus dem Re-Ranker (Cross-Encoder, sieht ICP und
  Firmenprofil zusammen), nicht aus festen Gewichten und nicht aus einem
  LLM-Bauchgefühl. Die Gewichte eurer Kriterien-Tabelle stecken in der
  Query. Wer die Gewichtung exakt nach Tabelle braucht, lässt icp-scorer
  danach über Tier A/B laufen.
- Nur `in_ai_ark = nein` zählt als Dark TAM. Unbekannt ist nicht dunkel.
- Unbekannt ist nicht dasselbe wie nicht erfüllt: fehlende Felder landen
  in `datenluecken`, nicht als Abzug im Score.
- Jede Firma hat eine Fundstelle mit URL. Eine Zeile ohne `quelle_url`
  gehört nicht in die Liste.
- Bezahlte Credits (Blitz, AI Ark People, Lusha) erst für Tier A und B.
  Das Impressum ist kostenlos und kommt immer zuerst.
- Gesperrte Domains nie anschreiben, auch nicht wenn sie Tier A sind.
- Keine Keys in Dateien oder Chat. Alles kommt aus `.env`.

## Sonderfälle

- **Sehr kleine Firmen** (Bäckerei, Waschanlage, Praxis): kein
  LinkedIn, oft keine persönliche Mail. Der Entscheider kommt aus dem
  Impressum (Pflichtangabe), der Kanal ist Brief oder Telefon. Datenlücke
  `email` ist hier das normale Ergebnis, kein Fehler.
- **Konzerne in Verbandslisten** (z. B. ABB, Akamai in einer
  Provider-Liste): ranken meist niedrig, weil das Profil nicht passt.
  Stehen sie trotzdem oben, ist die ICP-Query zu allgemein.
- **Auslandsfirmen in deutschen Listen:** der Muss-Filter Land greift erst,
  wenn eine Adresse da ist. Bis dahin an `domain` (.pl, .fr, .se) erkennen
  und als Grenzfall markieren.
- **Dieselbe Firma auf mehreren Listen:** eine Zeile, alle Fundstellen
  bleiben erhalten. Mehrere Listen sind ein Legitimitätssignal.
- **Discovery findet keine brauchbare Quelle:** eine bekannte Liste direkt
  geben (`python -m arvantir harvest "<Listen-URL>"`), statt die Nische
  immer breiter zu formulieren.

## Zusammenspiel

- Steht vor allen anderen: liefert die Liste, die company-research-agent,
  technographic-qualifier und icp-scorer sonst aus Listenkauf oder
  Altbestand bekommen.
- Tier A/B danach an buying-signal-detector für die Timing-Frage. Der
  Re-Ranker-Score sagt nur, ob die Firma passt, nicht ob jetzt.
- Begründungssatz und Fundstelle sind ein fertiger Aufhänger für
  personalization-writer (z. B. "gesehen, dass ihr Mitglied bei ... seid").
- Mit verbundenem Clay Agent Plugin: CSV als neue Table anlegen oder in
  eine bestehende schreiben; `datenluecken` steuert, welche Enrichments
  Clay nachkauft.
- Mit Supabase: `adapters/supabase.sql` einmal einspielen; die Rohfunde
  bleiben unveränderlich in `raw_pages`, die Lead-Tabellen lassen sich
  daraus jederzeit neu bauen.

## Checkliste vor Abgabe

- [ ] Jede genutzte Quelle angesehen und als Firmenliste der Nische bestätigt
- [ ] Tier-Verteilung kommentiert, Grenzfälle (`mensch_prueft`) separat ausgewiesen
- [ ] Sperrliste angewendet, gesperrte Zeilen nicht im Webhook
- [ ] Dark-TAM-Zahl nur aus `in_ai_ark = nein`, nicht aus "unbekannt"
- [ ] Häufigste Datenlücken genannt, mit dem günstigsten Weg sie zu füllen
