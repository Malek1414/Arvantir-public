# Arvantir Web (Live-Demo)

Start aus dem Repo-Ordner, nur lokal:

    .venv/bin/uvicorn web.server:app --host 127.0.0.1 --port 8400

Dann http://127.0.0.1:8400 öffnen.

- Nische eingeben oder Beispiel-Chip anklicken, "Lauf starten": Funnel zählt live per SSE hoch, danach Tabelle, Klick auf eine Zeile öffnet die Lead-Karte.
- Fallback fürs Video ohne Wartezeit: gespeicherten Lauf im Dropdown abspielen, oder direkt `http://127.0.0.1:8400/?replay=run_145130.json` (mit `&lead=1` öffnet sich danach die erste Lead-Karte).
- Benchmark-Bereich erscheint automatisch, sobald `bench/results.json` oder `bench/results.md` existiert.

API: `POST /run {niche, icp?}`, `GET /events/{id}` (SSE), `GET /result/{id}`, `GET /runs`, `GET /runs/{datei}`, `GET /bench`.
Sicherheit: bindet nur an 127.0.0.1, kein CORS, alle fremden Texte werden im HTML escaped, nur http(s)-Links, Dateinamen per Regex geprüft, höchstens 2 Läufe gleichzeitig.
