"""Serveur HTTP local et routes JSON.

Toutes les routes sont en lecture seule, sauf ``POST /pins`` (épingles) et
``POST /root`` (restriction de la vue). Le serveur n'écoute que sur
``127.0.0.1`` et vérifie l'en-tête ``Host`` : une page web hostile ne peut pas
le piloter par rebinding DNS.
"""

from __future__ import annotations

import json
import os
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional, Type

from . import __version__
from .config import State
from .paths import safe_bounded, safe_path
from .pins import load_pins, pins_action, pins_for_root, pins_with_mtime, prune_pins
from .render import (
    ALLOWED_ASSET_SUFFIXES,
    TYPES_ASSETS,
    cached_render,
    freshness,
    reecrire_assets,
    stat_info,
)
from .tree import _recent_cache, arbre_recent, list_dir
from .ui import page_html

HOSTS_AUTORISES = frozenset({"127.0.0.1", "localhost", "::1", "[::1]"})


def _nom_hote(valeur: str) -> str:
    """Extrait le nom d'hôte d'un en-tête ``Host`` (port et crochets IPv6 gérés)."""
    valeur = (valeur or "").strip().lower()
    if not valeur:
        return ""
    if valeur.startswith("["):
        return valeur.split("]", 1)[0] + "]"
    return valeur.rsplit(":", 1)[0] if ":" in valeur else valeur


def make_handler(state: State) -> Type[BaseHTTPRequestHandler]:
    """Construit la classe de handler liée à un :class:`State`."""

    class Handler(BaseHTTPRequestHandler):
        server_version = "docwatch/" + __version__
        protocol_version = "HTTP/1.1"

        def log_message(self, *args: Any) -> None:
            pass

        # --- garde-fous ---------------------------------------------------
        def _hote_ok(self) -> bool:
            hote = self.headers.get("Host")
            if not hote:  # HTTP/1.0 sans Host : toléré, les navigateurs en envoient un
                return True
            return _nom_hote(hote) in HOSTS_AUTORISES

        def _origine_ok(self) -> bool:
            origine = self.headers.get("Origin")
            if not origine:
                return True
            try:
                u = urllib.parse.urlparse(origine)
            except ValueError:
                return False
            return u.scheme == "http" and (u.hostname or "").lower() in HOSTS_AUTORISES

        def _refuser(self) -> bool:
            if not self._hote_ok():
                self._send(403, {"error": "hote non autorise"})
                return True
            if self.command == "POST" and not self._origine_ok():
                self._send(403, {"error": "origine non autorisee"})
                return True
            return False

        # --- envoi --------------------------------------------------------
        def _send(
            self, code: int, corps: Any, ctype: str = "application/json; charset=utf-8"
        ) -> None:
            if isinstance(corps, (dict, list)):
                data = json.dumps(corps).encode("utf-8")
            elif isinstance(corps, str):
                data = corps.encode("utf-8")
            else:
                data = corps
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(data)

        def _lire_json(self, limite: int) -> Optional[Dict[str, Any]]:
            try:
                length = int(self.headers.get("Content-Length") or 0)
                if length <= 0 or length > limite:
                    raise ValueError("corps de requete invalide")
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except (ValueError, TypeError, json.JSONDecodeError):
                self._send(400, {"error": "requete invalide"})
                return None
            if not isinstance(payload, dict):
                self._send(400, {"error": "objet JSON attendu"})
                return None
            return payload

        # --- lecture ------------------------------------------------------
        def do_GET(self) -> None:  # noqa: N802
            if self._refuser():
                return
            u = urllib.parse.urlparse(self.path)
            q = urllib.parse.parse_qs(u.query)

            if u.path == "/":
                return self._send(200, page_html(state.root), "text/html; charset=utf-8")

            if u.path == "/tree":
                raw = (q.get("path") or [""])[0]
                p = safe_path(raw, state.root)
                if not p or not os.path.isdir(p):
                    return self._send(404, {"error": "dossier invalide"})
                dirs, files = list_dir(p, state.settings.exclude)
                # `now` vient du serveur : c'est l'horloge de référence pour
                # décider ce qui a été modifié depuis l'ouverture de la page.
                return self._send(200, {"dirs": dirs, "files": files, "now": int(time.time())})

            if u.path == "/asset":
                # Sert un fichier de la racine avec SON type (images, styles, pdf).
                p = safe_path((q.get("path") or [""])[0], state.root)
                if not p or not os.path.isfile(p):
                    return self._send(404, {"error": "fichier introuvable"})
                if os.path.basename(p).startswith("."):
                    return self._send(404, {"error": "fichier introuvable"})
                suffixe = os.path.splitext(p)[1].lower()
                if suffixe not in ALLOWED_ASSET_SUFFIXES:
                    return self._send(404, {"error": "type de fichier non servi"})
                ctype = TYPES_ASSETS[suffixe]
                with open(p, "rb") as f:
                    return self._send(200, f.read(), ctype)

            if u.path == "/render":
                raw = (q.get("path") or [""])[0]
                p = safe_path(raw, state.root)
                if not p or not os.path.isfile(p) or not p.lower().endswith(".md"):
                    return self._send(404, {"error": "fichier invalide"})
                force = (q.get("force") or ["0"])[0] == "1"
                t0 = time.perf_counter()
                try:
                    body, hit = cached_render(p, state.settings.cache_dir, force=force)
                except Exception as exc:  # noqa: BLE001 - on renvoie l'erreur au client
                    return self._send(500, {"error": "%s: %s" % (type(exc).__name__, exc)})
                ms = round((time.perf_counter() - t0) * 1000)
                body = reecrire_assets(body, os.path.dirname(p), state.root, state.initial_root)
                out: Dict[str, Any] = {"body": body, "path": p, "ms": ms, "cache": hit}
                info = stat_info(p) or {}
                # Le jeton reste côté client pour les contrôles suivants ; il
                # n'est jamais comparé en JavaScript.
                out["token"] = str(info.get("token", 0))
                out["dir_token"] = str(info.get("dir_token", 0))
                for k in ("name", "size", "mtime", "now", "dir_mtime", "dir_name"):
                    if k in info:
                        out[k] = info[k]
                return self._send(200, out)

            if u.path == "/stat":
                # Contrôle de fraîcheur léger : un stat, pas de rendu. Le client
                # renvoie les jetons reçus au dernier rendu ; la comparaison se
                # fait ici, à pleine précision.
                raw = (q.get("path") or [""])[0]
                p = safe_path(raw, state.root)
                if not p or not os.path.isfile(p):
                    return self._send(404, {"error": "fichier absent"})
                try:
                    token = int((q.get("token") or ["0"])[0])
                    dir_token = int((q.get("dir_token") or ["0"])[0])
                except ValueError:
                    token = dir_token = 0
                return self._send(200, freshness(p, token, dir_token))

            if u.path == "/pins":
                if (q.get("prune") or ["0"])[0] == "1":
                    retires = prune_pins(state.pins_file, state.root)
                else:
                    retires = []
                visibles = pins_for_root(load_pins(state.pins_file), state.root)
                return self._send(
                    200,
                    {"pins": pins_with_mtime(visibles), "retires": retires, "racine": state.root},
                )

            if u.path == "/recent":
                try:
                    heures = float((q.get("heures") or ["24"])[0])
                except ValueError:
                    heures = 24.0
                heures = max(0.05, min(heures, 24 * 365))
                force = (q.get("force") or ["0"])[0] == "1"
                elements, tronque = _recent_cache(
                    state.root, heures, state.settings.exclude, force=force
                )
                return self._send(
                    200,
                    {
                        "heures": heures,
                        "elements": elements,
                        "tronque": tronque,
                        "arbre": arbre_recent(elements, state.root),
                        "racine": state.root,
                        "maintenant": int(time.time()),
                    },
                )

            if u.path == "/root":
                return self._send(200, {"root": state.root, "borne": state.initial_root})

            if u.path == "/status":
                return self._send(200, {"root": state.root, "port": state.port})

            # URL propre d'un document : /docs/guide.md. Le serveur renvoie la
            # SPA, qui lit ce chemin et ouvre le fichier ; un rechargement, un
            # favori ou un lien partagé fonctionne donc sans JavaScript côté
            # serveur. La cible est validée sous la racine de départ.
            if u.path.lower().endswith(".md"):
                brut = os.path.join(state.initial_root, u.path.lstrip("/"))
                p = safe_path(brut, state.initial_root)
                if p and os.path.isfile(p):
                    return self._send(200, page_html(state.root), "text/html; charset=utf-8")
                return self._send(404, {"error": "document introuvable"})

            return self._send(404, {"error": "route inconnue"})

        do_HEAD = do_GET

        # --- écriture -----------------------------------------------------
        def _set_root(self) -> None:
            """Change la racine de l'arbre affiché.

            Bornée par la racine de départ : on peut restreindre la vue à un
            sous-dossier (ce qui allège fortement le client comme le serveur),
            jamais élargir le périmètre au-delà de ce qui a été lancé.
            """
            payload = self._lire_json(65536)
            if payload is None:
                return
            raw = payload.get("path") or ""
            p = safe_bounded(raw, state.initial_root)
            if not p or not os.path.isdir(p):
                return self._send(
                    400,
                    {
                        "error": "hors du perimetre autorise (ou dossier inexistant): %s"
                        % state.initial_root
                    },
                )
            state.set_root(p)
            return self._send(200, {"root": state.root, "borne": state.initial_root})

        def _changed(self) -> None:
            """Compare en une requête les dates que le client connaît.

            Le client envoie ``{chemin: mtime}`` pour tout ce qu'il a affiché ;
            on répond uniquement ce qui a bougé. C'est ce qui permet de repérer
            une modification dans un dossier sans re-télécharger son contenu à
            chaque cycle de sonde.
            """
            payload = self._lire_json(4_000_000)
            if payload is None:
                return
            known = payload.get("known")
            if not isinstance(known, dict):
                return self._send(400, {"error": "champ 'known' attendu"})
            if len(known) > 20000:
                return self._send(413, {"error": "trop de chemins"})

            changed, missing = [], []
            for path, mtime in known.items():
                p = safe_path(path, state.root)
                if not p:
                    continue
                try:
                    st = os.stat(p)
                except OSError:
                    missing.append(path)
                    continue
                # Une date illisible compte comme un changement : le client
                # recevra la vraie valeur et se recalera.
                try:
                    same = int(mtime) == int(st.st_mtime)
                except (TypeError, ValueError):
                    same = False
                if not same:
                    changed.append(
                        {
                            "path": path,
                            "name": os.path.basename(path),
                            "size": st.st_size,
                            "mtime": int(st.st_mtime),
                        }
                    )
            return self._send(
                200, {"changed": changed, "missing": missing, "now": int(time.time())}
            )

        def do_POST(self) -> None:  # noqa: N802
            """Routes en écriture ou en comparaison groupée.

            ``/pins``    : écrit uniquement dans pins.json (dossiers et documents).
            ``/root``    : change la racine affichée, bornée par la racine de départ.
            ``/changed`` : comparaison groupée, lecture seule (aucune écriture).
            """
            if self._refuser():
                return
            u = urllib.parse.urlparse(self.path)
            if u.path == "/changed":
                return self._changed()
            if u.path == "/root":
                return self._set_root()
            if u.path != "/pins":
                return self._send(
                    405, {"error": "seules les routes /pins, /root et /changed acceptent POST"}
                )

            payload = self._lire_json(65536)
            if payload is None:
                return
            action = payload.get("action")
            raw = payload.get("path") or ""
            kind = payload.get("kind") or "folder"
            if action not in ("add", "remove", "toggle"):
                return self._send(400, {"error": "action inconnue"})
            # On épingle un dossier OU un document markdown, sous la racine servie.
            p = safe_path(raw, state.root)
            if not p or not os.path.exists(p):
                return self._send(400, {"error": "chemin hors racine ou inexistant"})
            if kind == "file":
                if not os.path.isfile(p) or not p.lower().endswith(".md"):
                    return self._send(
                        400, {"error": "un document epingle doit etre un fichier .md"}
                    )
            elif kind != "folder":
                return self._send(400, {"error": "kind doit valoir folder ou file"})
            elif not os.path.isdir(p):
                return self._send(400, {"error": "dossier inexistant"})

            try:
                pins = pins_action(action, p, kind, state.pins_file)
            except OSError as exc:
                return self._send(500, {"error": "ecriture impossible: %s" % exc})
            if pins is None:
                return self._send(400, {"error": "action inconnue"})
            return self._send(200, {"pins": pins_with_mtime(pins)})

        # Ces méthodes restent refusées : aucune suppression ni modification.
        def do_PUT(self) -> None:  # noqa: N802
            return self._send(405, {"error": "methode non autorisee"})

        do_DELETE = do_PUT
        do_PATCH = do_PUT

    return Handler


def make_server(state: State) -> ThreadingHTTPServer:
    """Lie le serveur à ``127.0.0.1`` (port éventuellement éphémère)."""
    os.makedirs(state.settings.cache_dir, exist_ok=True)
    httpd = ThreadingHTTPServer((state.settings.host, state.port), make_handler(state))
    httpd.daemon_threads = True
    state.port = httpd.server_address[1]
    return httpd


def run(state: State, open_browser: bool = True) -> int:
    """Démarre le serveur et bloque jusqu'à Ctrl+C."""
    httpd = make_server(state)
    url = "http://127.0.0.1:%d/" % state.port
    print("docwatch: %s" % state.root)
    print("docwatch: %s   (Ctrl+C pour arreter)" % url)
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:  # noqa: BLE001 - pas de navigateur : le serveur reste utile
            pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\ndocwatch: arret")
    finally:
        httpd.server_close()
    return 0
