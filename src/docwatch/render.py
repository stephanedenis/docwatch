"""Rendu Markdown, cache disque et réécriture des fichiers annexes.

Le serveur ne sert que du Markdown, mais un document Markdown référence des
images, des feuilles de style, des PDF. Ces fichiers ne sont pas à la racine
du serveur : ils sont à côté du document. On réécrit donc leurs URL vers
``/asset?path=…``, résolues contre le dossier du document. Les liens vers un
autre document Markdown sont réécrits vers une URL propre (``/docs/guide.md``)
pour s'ouvrir dans le lecteur au lieu de renvoyer un 404.
"""

from __future__ import annotations

import hashlib
import html
import os
import re
import time
from typing import Callable, Dict, Optional, Tuple
from urllib.parse import quote, unquote

from .config import DiagramSettings
from .diagrams import preparer_texte, remplacer_placeholders
from .paths import in_root

#: Types servis par ``/asset``. La liste est volontairement fermée : un
#: répertoire de documentation peut contenir des `.env`, des clés, des
#: scripts ; ils ne doivent pas devenir téléchargeables par le navigateur.
TYPES_ASSETS: Dict[str, str] = {
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".avif": "image/avif",
    ".bmp": "image/bmp",
    ".ico": "image/x-icon",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    ".csv": "text/csv; charset=utf-8",
    ".pdf": "application/pdf",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".ttf": "font/ttf",
    ".otf": "font/otf",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".m4a": "audio/mp4",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
}

ALLOWED_ASSET_SUFFIXES = frozenset(TYPES_ASSETS)

_TAG_RE = re.compile(r"<(img|a)\b([^>]*)>", re.IGNORECASE)
_ATTR_RE = re.compile(r'\b(src|href)\s*=\s*"([^"]*)"', re.IGNORECASE)
_SCHEME_RE = re.compile(r"^[a-z][a-z0-9+.\-]*:", re.IGNORECASE)

#: Marqueurs internes du rendu : un fichier absent ne doit pas être confondu
#: avec une URL déjà réécrite.
_DEJA_REECRIT = ("/asset?path=", "/?f=", "/diagram/")


def _decouper_url(valeur: str) -> Tuple[str, str]:
    """Sépare le chemin du suffixe ``?query#fragment``."""
    chemin, _, fragment = valeur.partition("#")
    chemin, _, requete = chemin.partition("?")
    suffixe = ""
    if requete:
        suffixe += "?" + requete
    if fragment:
        suffixe += "#" + fragment
    return chemin, suffixe


def _url_asset(
    valeur: str, doc_dir: str, root: str, initial_root: str, balise: str
) -> Optional[str]:
    """URL de remplacement pour un attribut, ou ``None`` pour le laisser tel quel.

    Un lien absolu (``/docs/x.md``) est relatif à la **racine de départ** :
    c'est elle qui définit l'arborescence du site, même quand la vue est
    restreinte à un sous-dossier. Un lien relatif est relatif au dossier du
    document. La cible doit rester sous la racine courante.
    """
    valeur = valeur.strip()
    if not valeur or valeur.startswith("#"):
        return None
    if valeur.startswith("//") or _SCHEME_RE.match(valeur):
        return None
    if valeur.startswith(_DEJA_REECRIT):
        return None

    chemin, suffixe = _decouper_url(valeur)
    if not chemin:
        return None
    brut = unquote(chemin)
    if brut.startswith("/"):
        cible = os.path.realpath(os.path.join(initial_root, brut.lstrip("/")))
    else:
        cible = os.path.realpath(os.path.join(doc_dir, brut))
    if not in_root(cible, root):
        return None

    est_markdown = cible.lower().endswith(".md")
    if est_markdown:
        if balise.lower() != "a":
            return None
        # URL propre, relative à la racine de départ : /docs/guide.md.
        # Le serveur sert la SPA sur ce chemin et le client ouvre le document.
        if not in_root(cible, initial_root):
            return None
        rel = os.path.relpath(cible, initial_root).replace(os.sep, "/")
        fragment = "#" + valeur.split("#", 1)[1] if "#" in valeur else ""
        return "/" + quote(rel) + fragment
    if os.path.splitext(cible)[1].lower() not in ALLOWED_ASSET_SUFFIXES:
        return None
    return "/asset?path=%s%s" % (quote(cible), suffixe)


def reecrire_assets(
    html_txt: str, doc_dir: str, root: str, initial_root: Optional[str] = None
) -> str:
    """Réécrit les ``src``/``href`` relatifs vers les routes du serveur.

    - image ou fichier annexe autorisé -> ``/asset?path=…`` ;
    - lien vers un ``.md`` -> URL propre ``/docs/guide.md`` (la SPA l'ouvre) ;
    - URL absolue, ancre, schéma ou cible hors racine -> inchangé.
    """
    initial_root = initial_root or root

    def remplacer_balise(m: "re.Match[str]") -> str:
        balise, attributs = m.group(1), m.group(2)
        attendu = "src" if balise.lower() == "img" else "href"

        def remplacer_attribut(a: "re.Match[str]") -> str:
            nom, valeur = a.group(1), a.group(2)
            if nom.lower() != attendu:
                return a.group(0)
            nouvelle = _url_asset(valeur, doc_dir, root, initial_root, balise)
            if nouvelle is None:
                return a.group(0)
            return '%s="%s"' % (nom, nouvelle)

        return "<%s%s>" % (balise, _ATTR_RE.sub(remplacer_attribut, attributs))

    return _TAG_RE.sub(remplacer_balise, html_txt)


_RENDERER: Optional[Callable[[str], str]] = None


def _charger_moteur() -> Callable[[str], str]:
    """Choisit le premier moteur Markdown disponible, une seule fois."""
    global _RENDERER
    if _RENDERER is not None:
        return _RENDERER
    try:
        import mistune

        rendu = mistune.create_markdown(
            plugins=["table", "strikethrough", "url", "footnotes"],
            escape=False,
        )
        _RENDERER = rendu
        return _RENDERER
    except ImportError:
        pass
    try:
        from markdown_it import MarkdownIt

        moteur = MarkdownIt("commonmark", {"html": True}).enable(["table", "strikethrough"])
        _RENDERER = moteur.render
        return _RENDERER
    except ImportError:
        pass
    try:
        import markdown

        _RENDERER = lambda texte: markdown.markdown(  # noqa: E731
            texte, extensions=["tables", "fenced_code"]
        )
        return _RENDERER
    except ImportError:
        pass

    def repli(texte: str) -> str:
        # Dernier recours : texte lisible, jamais du Markdown brut non signalé.
        return (
            "<p><b>Aucun moteur Markdown disponible.</b> "
            "Installez <code>mistune</code>.</p><pre>" + html.escape(texte) + "</pre>"
        )

    _RENDERER = repli
    return _RENDERER


def render_markdown(text: str) -> str:
    """Rend le Markdown en HTML, avec repli en cascade."""
    return _charger_moteur()(text)


def cached_render(
    path: str,
    cache_dir: str,
    force: bool = False,
    diagrammes: Optional[DiagramSettings] = None,
) -> Tuple[str, bool]:
    """Rend le fichier en HTML, avec cache disque clé sur (chemin, mtime, taille).

    ``force=True`` ignore le cache : utile quand le fichier vient de changer et
    qu'on veut être certain de rendre la dernière version. Si ``diagrammes`` est
    fourni et actif, les blocs PlantUML/Mermaid sont convertis en SVG.
    """
    st = os.stat(path)
    actif = bool(diagrammes and diagrammes.enabled)
    cle = "%s|%s|%s|d%d" % (path, st.st_mtime_ns, st.st_size, 1 if actif else 0)
    key = hashlib.sha256(cle.encode()).hexdigest()[:32]
    cache_file = os.path.join(cache_dir, key + ".html")
    if not force and os.path.exists(cache_file):
        try:
            with open(cache_file, encoding="utf-8") as f:
                return f.read(), True
        except OSError:
            pass
    with open(path, "rb") as f:  # lecture seule, jamais d'écriture
        text = f.read().decode("utf-8", errors="replace")
    if actif and diagrammes is not None:
        text = preparer_texte(text, cache_dir, diagrammes)
    body = render_markdown(text)
    if actif:
        body = remplacer_placeholders(body)
    os.makedirs(cache_dir, exist_ok=True)
    tmp = cache_file + ".%d.tmp" % os.getpid()
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(body)
    os.replace(tmp, cache_file)
    return body, False


def stat_info(path: str) -> Optional[Dict[str, object]]:
    """Métadonnées de fraîcheur d'un fichier.

    Les dates sont volontairement ramenées à la seconde entière : un
    ``st_mtime_ns`` dépasse 2^53 et JavaScript l'arrondirait, ce qui rendrait
    toute comparaison côté client hasardeuse. ``now`` vient du serveur : c'est
    la seule horloge qui compte pour calculer un âge, celle du navigateur
    pouvant être décalée.
    """
    try:
        st = os.stat(path)
    except OSError:
        return None
    info: Dict[str, object] = {
        "path": path,
        "name": os.path.basename(path),
        "size": st.st_size,
        "mtime": int(st.st_mtime),
        "ctime": int(st.st_ctime),
        "now": time.time(),
        # Jeton de version : reste côté serveur, jamais comparé en JS (un mtime
        # en nanosecondes dépasse la précision d'un flottant JS).
        "token": st.st_mtime_ns,
    }
    parent = os.path.dirname(path)
    try:
        pst = os.stat(parent)
        info["dir_mtime"] = int(pst.st_mtime)
        info["dir_token"] = pst.st_mtime_ns
        info["dir_name"] = os.path.basename(parent) or parent
    except OSError:
        pass
    return info


def freshness(path: str, token: int, dir_token: int) -> Dict[str, object]:
    """Compare l'état courant du disque aux jetons fournis par le client.

    La comparaison se fait ici, sur les entiers 64 bits du système : le client
    n'a jamais à manipuler un mtime en nanosecondes. ``token`` absent (0) veut
    dire « je n'ai encore rien affiché », donc rien n'est signalé comme changé.
    """
    info = stat_info(path)
    if info is None:
        return {"exists": False}
    changed = bool(token) and info["token"] != token
    dir_changed = bool(dir_token) and info.get("dir_token", 0) != dir_token
    return {
        "exists": True,
        "changed": changed,
        "dir_changed": dir_changed,
        "name": info["name"],
        "size": info["size"],
        "mtime": info["mtime"],
        "now": info["now"],
        "dir_name": info.get("dir_name"),
        "dir_mtime": info.get("dir_mtime"),
    }
