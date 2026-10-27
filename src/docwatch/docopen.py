"""``docopen`` — ouvre un ou plusieurs Markdown dans docwatch.

Démarre le serveur si besoin, réutilise une instance dont la racine correspond,
puis ouvre chaque document dans un nouvel onglet. Le fichier source n'est
jamais modifié (lecture binaire uniquement).
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from typing import List, Optional
from urllib.parse import quote

from . import __version__
from .config import DEFAULT_PORT


def port_open(port: int, hote: str = "127.0.0.1", timeout: float = 0.4) -> bool:
    with socket.socket() as s:
        s.settimeout(timeout)
        return s.connect_ex((hote, port)) == 0


def server_root(port: int, timeout: float = 1.5) -> Optional[str]:
    """Interroge ``/status`` pour connaître la racine servie."""
    try:
        with urllib.request.urlopen("http://127.0.0.1:%d/status" % port, timeout=timeout) as r:
            return json.load(r).get("root")
    except Exception:  # noqa: BLE001 - un serveur absent ou ancien n'est pas une erreur fatale
        return None


def start_server(root: str, port: int) -> bool:
    """Démarre docwatch si besoin ; ne réutilise que si la racine correspond."""
    if port_open(port):
        serving = server_root(port)
        if serving and os.path.realpath(serving) == os.path.realpath(root):
            return True
        if serving:
            print("docopen: un serveur sert deja %s" % serving, file=sys.stderr)
            print("docopen: racine demandee differente (%s)" % root, file=sys.stderr)
        else:
            print("docopen: le port %d est occupe par un autre service" % port, file=sys.stderr)
        print("docopen: arretez-le (ou utilisez --port) puis relancez", file=sys.stderr)
        return False

    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "docwatch", "--no-browser", "--port", str(port), root],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as exc:
        print("docopen: impossible de demarrer docwatch: %s" % exc, file=sys.stderr)
        return False

    for _ in range(100):  # attend jusqu'à 10 s
        if port_open(port):
            return True
        code = proc.poll()
        if code is not None:
            print("docopen: docwatch s'est arrete (code %s)" % code, file=sys.stderr)
            return False
        time.sleep(0.1)
    print("docopen: docwatch n'a pas repondu dans les 10 s", file=sys.stderr)
    return False


def _racine_commune(fichiers: List[str]) -> str:
    dossiers = [os.path.dirname(f) for f in fichiers]
    try:
        return os.path.commonpath(dossiers)
    except ValueError:
        return dossiers[0]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="docopen",
        description="Ouvre des fichiers Markdown dans docwatch (lecture seule).",
    )
    p.add_argument("fichiers", nargs="+", help="fichiers .md à ouvrir")
    p.add_argument(
        "-r", "--root", default=None, help="racine servie (défaut : dossier commun des fichiers)"
    )
    p.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help="port du serveur (défaut : %d)" % DEFAULT_PORT,
    )
    p.add_argument(
        "--no-open", action="store_true", help="affiche les URL sans ouvrir de navigateur"
    )
    p.add_argument("--version", action="version", version="%(prog)s " + __version__)
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.port == 0:
        print(
            "docopen: --port 0 n'est pas utilisable (le port choisi serait inconnu)",
            file=sys.stderr,
        )
        return 2
    fichiers = [os.path.realpath(os.path.abspath(os.path.expanduser(f))) for f in args.fichiers]
    for f in fichiers:
        if not os.path.isfile(f):
            print("docopen: introuvable: %s" % f, file=sys.stderr)
            return 1
        if not f.lower().endswith(".md"):
            print("docopen: format inattendu (Markdown attendu): %s" % f, file=sys.stderr)
            return 1

    root = os.path.realpath(
        os.path.abspath(os.path.expanduser(args.root or _racine_commune(fichiers)))
    )
    if not os.path.isdir(root):
        print("docopen: racine invalide: %s" % root, file=sys.stderr)
        return 2
    if root == os.path.sep:
        print("docopen: la racine commune est / ; précisez -r DOSSIER", file=sys.stderr)
        return 2
    for f in fichiers:
        if not (f == root or f.startswith(root + os.sep)):
            print("docopen: hors de la racine servie (%s): %s" % (root, f), file=sys.stderr)
            print("docopen: utilisez -r pour elargir la racine", file=sys.stderr)
            return 1

    if not start_server(root, args.port):
        print("docopen: impossible de demarrer docwatch", file=sys.stderr)
        print(
            "docopen: une autre racine ? utilisez --port %d -r DOSSIER" % (args.port + 1),
            file=sys.stderr,
        )
        return 1

    for f in fichiers:
        rel = os.path.relpath(f, root).replace(os.sep, "/")
        url = "http://127.0.0.1:%d/%s" % (args.port, quote(rel))
        if args.no_open:
            print(url)
        else:
            try:
                webbrowser.open(url)
            except Exception:  # noqa: BLE001 - pas de navigateur n'empêche pas de servir
                print(url)
            print("docopen: %s  (lecture seule)" % f)
    return 0
