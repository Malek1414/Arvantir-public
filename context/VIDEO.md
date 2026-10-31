# Abgabe-Video (2:00): Demo-Ablauf und Skript

Aufbau nach Maleks `/pitch`-Skill (sieben Schritte: Person, Versuch, Produkt, Moment, Beweis, Bedeutung, Bitte). Etwa 260 gesprochene Wörter plus Demo-Luft. Jede Zahl hat eine Quelle in der Fakten-Tabelle unten. Was dort als OFFEN markiert ist, wird erst gesagt, wenn die Zahl existiert.

## Demo-Ablauf (was auf dem Bildschirm passiert)

| Zeit | Bild | Was passiert |
|---|---|---|
| 0:00–0:12 | Gesicht | Einstieg, kein Bildschirm |
| 0:12–0:25 | Gesicht, dann Clay-Tabelle / Liste | Wie es heute läuft |
| 0:25–0:32 | Startseite `127.0.0.1:8400` | "Palantir" wird durchgestrichen, "Arvantir." erscheint |
| 0:32–1:05 | Demo, Vollbild | **Live-Eingabe:** "Metzgereien" oder die Nische der Jury tippen, Start. Funnel zählt hoch: Quellen, Firmen, eine Firma eine Zeile, mit Website, mit Entscheider, gerankt. Nicht live warten: nach dem Start auf den fertigen Lauf schneiden (Replay `/?replay=run_145130.json&lead=1`), die Wartezeit im Schnitt raffen |
| 1:05–1:20 | Lead-Karte | Eine Zeile anklicken: Firma, Entscheider aus dem Impressum, ICP-Score, Tier, Begründungssatz mit Quell-Link, Kanal "Brief" mit Grund |
| 1:20–1:35 | Beweis | Benchmark-Balken (`bench/results.md`, OFFEN) oder, falls nicht fertig: Funnel-Zahlen des Laufs plus Spalte "nicht in AI Ark" (OFFEN, braucht Key) |
| 1:35–1:45 | `/architecture`, 5 s | Kette von discover bis channel, darunter Searchify, rechts Clay, Supabase, "eure 12 Skills" |
| 1:45–2:00 | Gesicht | Bedeutung und Bitte |

**Backup, falls das Netz streikt:** alles über Replay `run_145130` (Asset Manager) und `run_143435` (Bäcker & Metzger), dazu `scripts/demo.sh` im Terminal als Beweis, dass es echt läuft.

## Skript (Deutsch, gesprochen)

**[Person, Gesicht]**
Vor zwei Tagen hat uns Arvana gesagt: Leads mit Agenten sortieren klappt nicht. Sie machen es lieber von Hand. [I1]

**[Versuch, Gesicht]**
Und die Leads selbst? Die kommen aus Datenbanken. Da steht jeder drin, der auf LinkedIn ist. [I2]
Die Metzgerei in Schwabing steht da nicht drin. Die Apotheke am Wittenbergplatz auch nicht. Dabei kaufen genau die. [F1]

**[Produkt, Startseite]**
Wir haben Arvantir gebaut. Man nennt eine Branche. Arvantir findet die Firmen, die keine Datenbank kennt.

**[Moment, Demo]**
Ich tippe: Metzgereien.
Arvantir sucht sich selbst die Listen: Branchenbücher, Verbände, Messen.
Es liest jede Firma aus. Filialen werden zu einer Firma.
Dann öffnet es jede Website und liest das Impressum. Da steht, wer entscheidet.
Am Ende sortiert es alle nach eurem Kundenprofil. Jede Zeile mit Grund und Quelle.
Und es sagt, wie man sie erreicht. Hier: ein Brief. Denn eine Metzgerei liest keine Kaltakquise-Mail.

**[Beweis, Lead-Karte / Benchmark]**
Sechzig Asset Manager in gut zwei Minuten, dreiunddreißig davon mit Namen des Chefs. [F2]
(Wenn fertig:) Und beim Sortieren stimmen wir mit eurer Handsortierung in X von hundert Fällen überein. [F3, OFFEN]

**[Bedeutung, Gesicht]**
Eure zwölf Skills fangen bei einer fertigen Liste an. [F4]
Arvantir ist der Skill davor. Er baut die Liste, im Format eurer Clay-Tabelle.

**[Bitte, Gesicht]**
Gebt uns am Montag eine Nische, für die ihr gerade keine Leads findet. Wir bringen die Liste.

## Fakten (jede Zahl im Skript braucht hier eine Zeile)

| Tag | Fakt | Beleg |
|---|---|---|
| I1 | Arvana sagte Sami am 29.10.2026, Lead-Sortierung mit Agenten laufe nicht gut, sie sortierten lieber von Hand | Samis Gespräch, `context/ARVANA.md` |
| I2 | Kundenkritik an Arvana betrifft vor allem veraltete Datenquellen und zu wenige Leads | `context/ARVANA.md` (Salesforge-Review) |
| F1 | Metzgereien und Apotheken aus dem Branchenbuch gefunden, z. B. Apotheke Am Wittenbergplatz | `data/run_144623.json`, `data/run_143435.json` |
| F2 | 60 Asset Manager, 33 mit Entscheider, Lauf 143 s | `data/run_145130.json` |
| F3 | Übereinstimmung mit Handsortierung | OFFEN: `bench/results.md` (Malek) |
| F4 | Alle 12 claude-gtm-skills starten bei einer fertigen Liste | `research/ARVANA_WORKFLOW.md` |
| F5 | "nicht in AI Ark" je Lauf | OFFEN: braucht `AIARK_API_KEY` |

Nicht sagen: "nicht in AI Ark" mit einer Zahl, solange F5 offen ist. Keine Zahl über AI Ark, die wir nicht selbst gemessen haben.

## Englische Fassung (falls die Jury Englisch will)

Two days ago Arvana told us: sorting leads with agents doesn't work. They'd rather do it by hand.
And the leads? They come from databases. Everyone on LinkedIn is in there. The butcher in Schwabing is not. Neither is the pharmacy on Wittenbergplatz. Yet they are the ones who buy.
So we built Arvantir. Name an industry. Arvantir finds the companies no database knows.
I type: butchers. Arvantir finds its own lists: business directories, associations, trade fairs. It reads every company and merges branches into one. Then it opens each website and reads the legal notice. That is where the decision maker is named. It ranks everyone against your customer profile, every row with a reason and a source. And it tells you how to reach them. Here: a letter. A butcher doesn't read cold emails.
Sixty asset managers in just over two minutes, thirty-three with the boss's name.
Your twelve skills all start from a finished list. Arvantir is the skill before that. It builds the list, in the format of your Clay table.
On Monday, give us one industry where you can't find leads today. We'll bring the list.
