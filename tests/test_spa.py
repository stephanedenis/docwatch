"""Navigation SPA : l'URL porte le document, le clic ne recharge pas la page.

Ce test pilote un vrai navigateur par le protocole DevTools. Il est sauté si
Chrome/Chromium ou ``websocket-client`` manque : la suite reste utilisable
partout, et la navigation est verrouillée quand le navigateur est là.
"""

from __future__ import annotations

import json
import shutil
import socket
import subprocess
import time
import urllib.request
from pathlib import Path

import pytest

websocket = pytest.importorskip("websocket")

BROWSER = (
    shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chromium-browser")
)
pytestmark = pytest.mark.skipif(not BROWSER, reason="Chrome/Chromium absent")


def _port_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _attendre(predicat, timeout=10):
    fin = time.time() + timeout
    dernier = None
    while time.time() < fin:
        dernier = predicat()
        if dernier:
            return dernier
        time.sleep(0.1)
    raise AssertionError("délai dépassé: %r" % (dernier,))


def test_clic_lien_md_sans_rechargement(srv, tmp_path: Path):
    port = _port_libre()
    chrome = subprocess.Popen(
        [
            BROWSER,
            "--headless=new",
            "--no-sandbox",
            "--disable-gpu",
            "--remote-debugging-port=%d" % port,
            "--remote-allow-origins=*",
            "--user-data-dir=%s" % (tmp_path / "chrome"),
            srv.base + "/guide.md",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    ws = None

    def json_cdp():
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d/json" % port, timeout=2) as r:
                return json.load(r)
        except OSError:
            return None

    try:
        cibles = _attendre(json_cdp, timeout=15)
        page = next(
            (
                t
                for t in cibles
                if t.get("type") == "page" and t.get("url", "").startswith(srv.base)
            ),
            None,
        )
        if page is None:
            pytest.skip("Chrome n'a pas ouvert la page docwatch")
        ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=10)
        compteur = [0]

        def js(expr):
            compteur[0] += 1
            ws.send(
                json.dumps(
                    {
                        "id": compteur[0],
                        "method": "Runtime.evaluate",
                        "params": {"expression": expr, "returnByValue": True, "awaitPromise": True},
                    }
                )
            )
            while True:
                msg = json.loads(ws.recv())
                if msg.get("id") == compteur[0]:
                    if "exceptionDetails" in msg.get("result", {}):
                        raise AssertionError(msg["result"]["exceptionDetails"])
                    return msg["result"]["result"].get("value")

        def etat():
            return json.loads(
                js(
                    "JSON.stringify({path:location.pathname, "
                    "h1:(document.querySelector('#main h1')||{}).textContent, "
                    "marker:window.__marker})"
                )
            )

        _attendre(lambda: etat().get("h1") == "Guide")
        js("window.__marker = 'keep'")
        js("document.querySelector('#main a[href$=\".md\"]').click()")
        etat_final = _attendre(lambda: (lambda e: e if e.get("h1") == "Intro" else None)(etat()))
        assert etat_final["path"] == "/sub/intro.md"
        assert etat_final["marker"] == "keep"  # pas de rechargement complet

        js("history.back()")
        retour = _attendre(lambda: (lambda e: e if e.get("h1") == "Guide" else None)(etat()))
        assert retour["path"] == "/guide.md"
        assert retour["marker"] == "keep"
    except AssertionError as exc:
        if ws is None:
            pytest.skip("Chrome headless n'a pas démarré: %s" % exc)
        raise
    finally:
        if ws is not None:
            ws.close()
        chrome.terminate()
        try:
            chrome.wait(timeout=5)
        except subprocess.TimeoutExpired:
            chrome.kill()
