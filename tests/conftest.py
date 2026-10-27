"""Fixtures partagées : un petit arbre de documentation et un serveur réel."""

from __future__ import annotations

import http.client as http_client
import json
import os
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from types import SimpleNamespace

import pytest

from docwatch.config import State, make_settings
from docwatch.server import make_server

SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
    '<rect width="10" height="10"/></svg>'
)
PNG = b"\x89PNG\r\n\x1a\n"


@pytest.fixture
def docs(tmp_path: Path) -> Path:
    root = tmp_path / "docs"
    root.mkdir()
    (root / "guide.md").write_text(
        "# Guide\n\n"
        "| a | b |\n|---|---|\n| 1 | 2 |\n\n"
        "![schema](img.svg)\n\n"
        "[Introduction](sub/intro.md)\n\n"
        "[Absolu](/sub/intro.md)\n\n"
        "[Externe](https://example.com)\n\n"
        "[Ancre](#guide)\n",
        encoding="utf-8",
    )
    (root / "img.svg").write_text(SVG, encoding="utf-8")
    (root / "secret.env").write_text("TOKEN=secret", encoding="utf-8")
    (root / "notes.txt").write_text("notes", encoding="utf-8")
    (root / "archive.zip").write_bytes(b"PK\x03\x04")
    (root / ".secret.svg").write_text(SVG, encoding="utf-8")
    (root / ".hidden.md").write_text("# cache", encoding="utf-8")

    sub = root / "sub"
    sub.mkdir()
    (sub / "intro.md").write_text("# Intro\n\n![pic](pic.png)\n", encoding="utf-8")
    (sub / "pic.png").write_bytes(PNG)

    for nom in (".cache", "node_modules"):
        d = root / nom
        d.mkdir()
        (d / "ignore.md").write_text("# ignore", encoding="utf-8")

    old = root / "old.md"
    old.write_text("# Vieux\n", encoding="utf-8")
    vieux = 1_600_000_000
    os.utime(old, (vieux, vieux))
    return root


@pytest.fixture
def srv(docs: Path, tmp_path: Path):
    settings = make_settings(
        root=str(docs),
        port=0,
        config_dir=str(tmp_path / "config"),
        cache_dir=str(tmp_path / "cache"),
    )
    state = State(settings)
    httpd = make_server(state)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = "http://127.0.0.1:%d" % state.port
    yield SimpleNamespace(
        httpd=httpd, state=state, base=base, root=docs, port=state.port, thread=thread
    )
    httpd.shutdown()
    httpd.server_close()
    thread.join(timeout=5)


def url_for(base: str, chemin: str, **params) -> str:
    url = base + chemin
    if params:
        url += "?" + urllib.parse.urlencode(params)
    return url


def http(base: str, chemin: str, method: str = "GET", payload=None, headers=None, **params):
    """Requête HTTP qui ne lève pas sur 4xx/5xx : renvoie (statut, entêtes, corps)."""
    url = url_for(base, chemin, **params)
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def http_host(port: int, hote: str, chemin: str = "/") -> int:
    """Requête brute avec un en-tête Host imposé (test anti-rebinding)."""
    conn = http_client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request("GET", chemin, headers={"Host": hote})
        reponse = conn.getresponse()
        reponse.read()
        return reponse.status
    finally:
        conn.close()
