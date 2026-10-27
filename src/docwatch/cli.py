"""Point d'entrée en ligne de commande de ``docwatch``."""

from __future__ import annotations

import argparse
import os
import sys
from typing import List, Optional

from . import __version__
from .config import DEFAULT_PORT, State, config_template, default_config_path, make_settings
from .paths import safe_path
from .pins import load_pins, pins_action
from .server import run


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="docwatch",
        description="Lecteur Markdown local, en lecture seule : arborescence, "
        "rendu, rechargement automatique, épingles.",
        epilog="Les documents ne sont jamais ouverts en écriture ; les SVG de "
        "diagrammes peuvent être générés. Le serveur n'écoute que sur 127.0.0.1.",
    )
    p.add_argument(
        "racine", nargs="?", default=None, help="dossier servi (défaut : répertoire courant)"
    )
    p.add_argument(
        "--port",
        type=int,
        default=None,
        help="port d'écoute (défaut : configuration ou %d ; 0 = port libre)" % DEFAULT_PORT,
    )
    p.add_argument(
        "--config",
        default=None,
        help="fichier de configuration TOML (défaut : XDG_CONFIG_HOME/docwatch/config.toml)",
    )
    p.add_argument(
        "--init-config",
        action="store_true",
        help="écrit un modèle de configuration puis quitte",
    )
    p.add_argument("--force", action="store_true", help="avec --init-config : écrase le fichier")
    p.add_argument(
        "--no-browser", action="store_true", help="ne pas ouvrir de navigateur au démarrage"
    )
    p.add_argument(
        "--config-dir",
        default=None,
        help="répertoire de configuration (défaut : XDG_CONFIG_HOME/docwatch)",
    )
    p.add_argument(
        "--cache-dir", default=None, help="répertoire de cache (défaut : XDG_CACHE_HOME/docwatch)"
    )
    p.add_argument("--version", action="version", version="%(prog)s " + __version__)
    p.add_argument(
        "--mount",
        default=None,
        help="montage utilisé pour les chemins relatifs des épingles",
    )
    p.add_argument(
        "--pin", action="append", metavar="DOSSIER", help="épingle un dossier (répétable)"
    )
    p.add_argument(
        "--unpin",
        action="append",
        metavar="DOSSIER",
        help="retire une épingle de dossier (répétable)",
    )
    p.add_argument(
        "--pin-file", action="append", metavar="DOC.md", help="épingle un document (répétable)"
    )
    p.add_argument(
        "--unpin-file",
        action="append",
        metavar="DOC.md",
        help="retire une épingle de document (répétable)",
    )
    p.add_argument("--list-pins", action="store_true", help="liste les épingles puis quitte")
    return p


def _resoudre(chemin: str, racine: str) -> str:
    """Résout un chemin relatif par rapport à la racine servie."""
    brut = os.path.expanduser(chemin)
    if not os.path.isabs(brut):
        brut = os.path.join(racine, brut)
    return os.path.abspath(brut)


def _gerer_epingles(args: argparse.Namespace, state: State) -> int:
    """Exécute les commandes d'épingles. Retourne 0 si tout s'est bien passé."""
    if args.mount:
        montage = state.mount_by_name(args.mount)
        if not montage:
            print("docwatch: montage inconnu: %s" % args.mount, file=sys.stderr)
            return 1
    else:
        montage = state.mounts[0]
    racine = montage.path

    if args.list_pins:
        pins = load_pins(state.pins_file)
        total = len(pins["folders"]) + len(pins["files"])
        if not total:
            print("docwatch: aucune epingle")
        for x in pins["folders"]:
            print("dossier   %s" % x["path"])
        for x in pins["files"]:
            print("document  %s" % x["path"])

    operations = (
        (args.pin, "folder", "add"),
        (args.unpin, "folder", "remove"),
        (args.pin_file, "file", "add"),
        (args.unpin_file, "file", "remove"),
    )
    for valeurs, kind, action in operations:
        for valeur in valeurs or []:
            brut = _resoudre(valeur, racine)
            p = safe_path(brut, racine)
            if not p or not os.path.exists(p):
                print("docwatch: chemin invalide ou hors racine: %s" % valeur, file=sys.stderr)
                return 1
            if kind == "file" and (not os.path.isfile(p) or not p.lower().endswith(".md")):
                print(
                    "docwatch: un document epingle doit etre un fichier .md: %s" % valeur,
                    file=sys.stderr,
                )
                return 1
            if kind == "folder" and not os.path.isdir(p):
                print("docwatch: dossier inexistant: %s" % valeur, file=sys.stderr)
                return 1
            try:
                pins_action(action, p, kind, state.pins_file)
            except OSError as exc:
                print("docwatch: ecriture impossible: %s" % exc, file=sys.stderr)
                return 1
            verbe = "epingle" if action == "add" else "retire"
            print("docwatch: %s (%s) %s" % (verbe, kind, p))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.init_config:
        chemin = args.config or default_config_path()
        if os.path.exists(chemin) and not args.force:
            print("docwatch: %s existe déjà (utiliser --force)" % chemin, file=sys.stderr)
            return 1
        try:
            os.makedirs(os.path.dirname(chemin) or ".", exist_ok=True)
            with open(chemin, "w", encoding="utf-8") as f:
                f.write(config_template(args.racine))
        except OSError as exc:
            print("docwatch: écriture impossible: %s" % exc, file=sys.stderr)
            return 1
        print("docwatch: configuration écrite dans %s" % chemin)
        return 0

    try:
        settings = make_settings(
            root=args.racine,
            port=args.port,
            cache_dir=args.cache_dir,
            config_dir=args.config_dir,
            config_path=args.config,
        )
    except ValueError as exc:
        print("docwatch: %s" % exc, file=sys.stderr)
        return 2

    state = State(settings)
    if args.list_pins or args.pin or args.unpin or args.pin_file or args.unpin_file:
        return _gerer_epingles(args, state)

    try:
        return run(state, open_browser=not args.no_browser)
    except OSError as exc:
        print(
            "docwatch: impossible de demarrer sur le port %s: %s" % (settings.port, exc),
            file=sys.stderr,
        )
        return 1
