"""Echter Chrome als letzte Stufe: Seiten über den laufenden Chrome des Nutzers holen (CDP).

Wie chrome-real (chrome-devtools-mcp --autoConnect): Chrome schreibt Port und WebSocket-Pfad
nach DevToolsActivePort. Chrome fragt bei JEDER neuen Verbindung "Allow remote debugging?",
darum hält dieses Modul genau EINE Verbindung pro Lauf offen (einmal "Allow" klicken) und
öffnet darüber pro Seite einen Hintergrund-Tab: laden, gerendertes HTML lesen, optional
Screenshot als Beleg (data/proof/), Tab schließen.

Nur Rückfall, wenn httpx/r.jina.ai leer oder blockiert zurückkommt (echter Fingerprint,
echte Cookies). Abschalten: ARVANTIR_REAL_BROWSER=0. Obergrenze pro Lauf: ARVANTIR_REAL_MAX (40).
Wird "Allow" nicht geklickt oder abgelehnt, bleibt der echte Browser für den Rest des Laufs aus.
"""
from __future__ import annotations

import asyncio
import base64
import itertools
import json
import os
import threading
from pathlib import Path
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse

from .common import DATA

PORT_FILE = Path.home() / "Library/Application Support/Google/Chrome/DevToolsActivePort"
PROOF = DATA / "proof"


def _endpoint() -> Optional[str]:
    try:
        port, path = PORT_FILE.read_text().split("\n")[:2]
        return f"ws://127.0.0.1:{port.strip()}{path.strip()}"
    except (OSError, ValueError):
        return None


class _Chrome:
    """Eine geteilte CDP-Verbindung in einem eigenen Event-Loop-Thread."""

    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.loop.run_forever, daemon=True).start()
        self.ws = None
        self.dead = False
        self.used = 0
        self.ids = itertools.count(1)
        self.pending: Dict[int, asyncio.Future] = {}
        self.tabs = asyncio.Semaphore(3)
        self._lock = threading.Lock()

    async def _connect(self) -> None:
        import websockets

        print("[realbrowser] verbinde mit Chrome, bitte im Chrome-Dialog einmal 'Allow' klicken ...")
        self.ws = await websockets.connect(_endpoint(), max_size=60_000_000,
                                           open_timeout=float(os.getenv("ARVANTIR_REAL_ALLOW_WAIT", "60")))
        self.loop.create_task(self._reader())
        print("[realbrowser] verbunden")

    async def _reader(self) -> None:
        try:
            async for raw in self.ws:
                r = json.loads(raw)
                fut = self.pending.pop(r.get("id"), None)
                if fut and not fut.done():
                    fut.set_result(r.get("result") or {"_error": r.get("error")})
        except Exception:  # noqa: BLE001 - Verbindung weg: Rest des Laufs ohne echten Browser
            self.dead = True

    async def call(self, method: str, params: Optional[dict] = None, session: Optional[str] = None) -> dict:
        i = next(self.ids)
        fut = self.loop.create_future()
        self.pending[i] = fut
        msg = {"id": i, "method": method, "params": params or {}}
        if session:
            msg["sessionId"] = session
        await self.ws.send(json.dumps(msg))
        return await asyncio.wait_for(fut, 30)

    async def fetch(self, url: str, wait: float, proof: Optional[Path]) -> Tuple[str, str]:
        if self.ws is None:
            await self._connect()
        async with self.tabs:
            tid = (await self.call("Target.createTarget", {"url": url, "background": True}))["targetId"]
            try:
                s = (await self.call("Target.attachToTarget", {"targetId": tid, "flatten": True}))["sessionId"]
                for _ in range(20):  # bis zu 10 s auf readyState warten
                    r = await self.call("Runtime.evaluate", {"expression": "document.readyState",
                                                             "returnByValue": True}, s)
                    if r.get("result", {}).get("value") == "complete":
                        break
                    await asyncio.sleep(0.5)
                await asyncio.sleep(wait)
                r = await self.call("Runtime.evaluate", {
                    "expression": "[document.documentElement.outerHTML, location.href]",
                    "returnByValue": True}, s)
                html, final = r.get("result", {}).get("value") or ["", url]
                if proof:
                    shot = await self.call("Page.captureScreenshot", {"format": "png"}, s)
                    if shot.get("data"):
                        proof.parent.mkdir(parents=True, exist_ok=True)
                        proof.write_bytes(base64.b64decode(shot["data"]))
                return html or "", final or url
            finally:
                await self.call("Target.closeTarget", {"targetId": tid})


_chrome: Optional[_Chrome] = None
_init = threading.Lock()


def available() -> bool:
    return (os.getenv("ARVANTIR_REAL_BROWSER", "1") != "0" and _endpoint() is not None
            and not (_chrome and _chrome.dead))


def fetch_real(url: str, wait: float = 1.0, proof: bool = False, timeout: float = 90) -> Tuple[str, str]:
    """(html, final_url) aus dem echten Chrome, oder ("", url) wenn aus, abgelehnt oder Limit erreicht."""
    global _chrome
    from .harvest import is_public_url

    if not available() or not is_public_url(url):
        return "", url
    with _init:
        if _chrome is None:
            _chrome = _Chrome()
        ch = _chrome
        if ch.used >= int(os.getenv("ARVANTIR_REAL_MAX", "40")):
            return "", url
        ch.used += 1
    shot = PROOF / (urlparse(url).netloc.replace(":", "_") + ".png") if proof else None
    try:
        html, final = asyncio.run_coroutine_threadsafe(ch.fetch(url, wait, shot), ch.loop).result(timeout)
        print(f"[realbrowser] {len(html)} Zeichen: {url}")
        return html, final
    except Exception as e:  # noqa: BLE001 - echter Browser ist optional
        if ch.ws is None:
            ch.dead = True  # "Allow" nicht geklickt: nicht bei jeder Seite neu fragen
        print(f"[realbrowser] übersprungen ({type(e).__name__}): {url}")
        return "", url
