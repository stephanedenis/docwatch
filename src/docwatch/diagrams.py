"""Génération des diagrammes PlantUML et Mermaid en SVG.

Deux sources sont prises en charge :

- les **fichiers** ``.puml``, ``.pu``, ``.plantuml``, ``.mmd``, ``.mermaid`` :
  le SVG est écrit à côté, en conservant l'extension en affixe
  (``diagram.puml`` → ``diagram.puml.svg``) ;
- les **blocs de code** Markdown ```puml / ```plantuml / ```mmd / ```mermaid :
  le SVG est mis en cache sous ``<hash>.<affixe>.svg`` et affiché par la route
  ``/diagram/<hash>.<affixe>.svg``.

Un outil absent ou une erreur de syntaxe laisse le bloc de code intact : un
document ne devient jamais illisible parce qu'un diagramme n'a pas pu être
généré. Les SVG générés reçoivent ``viewBox``, ``<title>`` et ``<desc>`` s'ils
manquent.
"""

from __future__ import annotations

import hashlib
import html
import os
import re
import shlex
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Iterable, Optional

from .config import EXCLUDE, DiagramSettings, State

#: affixe conservé dans le nom du SVG, et moteur associé.
AFFIXES = {
    "puml": "plantuml",
    "pu": "plantuml",
    "plantuml": "plantuml",
    "mmd": "mermaid",
    "mermaid": "mermaid",
}
EXTENSIONS = {("." + a): a for a in AFFIXES}

_FENCE = re.compile(
    r"^[ \t]*```[ \t]*(puml|pu|plantuml|mmd|mermaid)[ \t]*\n"
    r"(.*?)"
    r"^[ \t]*```[ \t]*$",
    re.MULTILINE | re.DOTALL,
)
_PLACEHOLDER = re.compile(r"<!--\s*diagram:([0-9a-f]{16,64})\.(puml|pu|plantuml|mmd|mermaid)\s*-->")
_URL_DIAGRAMME = re.compile(r"^/diagram/([0-9a-f]{16,64})\.(puml|pu|plantuml|mmd|mermaid)\.svg$")
_MARQUEUR = "docwatch-generated"


def extension_source(chemin: str) -> Optional[str]:
    """Affixe (``puml``, ``mmd``…) d'un fichier source, ou ``None``."""
    return EXTENSIONS.get(Path(chemin).suffix.lower())


def est_source(chemin: str) -> bool:
    return extension_source(chemin) is not None


def hash_source(moteur: str, source: str) -> str:
    return hashlib.sha256((moteur + "\x00" + source).encode("utf-8")).hexdigest()[:24]


def nom_svg_source(source: str) -> Path:
    """``diagram.puml`` → ``diagram.puml.svg`` (l'extension reste en affixe)."""
    p = Path(source)
    return p.with_name(p.name + ".svg")


def _commande(valeur: str) -> list[str]:
    return shlex.split(valeur) if valeur else []


def _enrichir(svg: str, titre: str, desc: str) -> str:
    """Ajoute viewBox, <title> et <desc> à la racine si le moteur ne les a pas mis."""
    if "<svg" not in svg:
        return svg
    debut = svg.find("<svg")
    fin = svg.find(">", debut)
    if fin < 0:
        return svg
    balise = svg[debut:fin]
    if "viewBox=" not in balise:
        m = re.search(
            r'\bwidth="([0-9.]+)(?:px)?"[^>]*\bheight="([0-9.]+)(?:px)?"',
            balise,
        )
        if m:
            largeur, hauteur = m.group(1), m.group(2)
            svg = svg[:fin] + ' viewBox="0 0 %s %s"' % (largeur, hauteur) + svg[fin:]
            fin = svg.find(">", debut)

    # Un <title> imbriqué (PlantUML en met un par participant) ne compte pas :
    # on regarde seulement ce qui suit immédiatement la balise racine.
    apres = svg[fin + 1 :].lstrip()
    if not apres.startswith("<title"):
        ajout = "<title>%s</title>" % html.escape(titre)
        svg = svg[: fin + 1] + ajout + svg[fin + 1 :]
    pos = fin + 1
    if svg[pos:].lstrip().startswith("<title"):
        fin_titre = svg.find("</title>", pos)
        if fin_titre >= 0:
            pos = fin_titre + len("</title>")
    if not svg[pos:].lstrip().startswith("<desc"):
        ajout = "<desc>%s</desc>" % html.escape(desc)
        svg = svg[:pos] + ajout + svg[pos:]
    return svg


def generer(
    moteur: str, source: str, settings: DiagramSettings, cwd: Optional[str] = None
) -> Optional[str]:
    """Rend ``source`` en SVG. Retourne ``None`` si l'outil échoue."""
    try:
        if moteur == "plantuml":
            commande = _commande(settings.plantuml) + ["-tsvg", "-pipe"]
            if "@startuml" not in source.lower():
                source = "@startuml\n" + source + "\n@enduml\n"
            proc = subprocess.run(
                commande,
                input=source.encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=settings.timeout,
                cwd=cwd,
                check=False,
            )
            if proc.returncode != 0 or b"<svg" not in proc.stdout:
                return None
            svg = proc.stdout.decode("utf-8", errors="replace")
            return _enrichir(svg, "Diagramme PlantUML", "Généré par PlantUML")

        if moteur == "mermaid":
            with tempfile.TemporaryDirectory(prefix="docwatch-mermaid-") as td:
                entree = Path(td) / "diagramme.mmd"
                sortie = Path(td) / "diagramme.mmd.svg"
                entree.write_text(source, encoding="utf-8")
                commande = _commande(settings.mermaid) + [
                    "-i",
                    str(entree),
                    "-o",
                    str(sortie),
                ]
                if settings.puppeteer:
                    commande += ["-p", settings.puppeteer]
                proc = subprocess.run(
                    commande,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=settings.timeout,
                    cwd=td,
                    check=False,
                )
                if proc.returncode != 0 or not sortie.is_file():
                    return None
                svg = sortie.read_text(encoding="utf-8", errors="replace")
                if "<svg" not in svg:
                    return None
                return _enrichir(svg, "Diagramme Mermaid", "Généré par Mermaid")
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return None
    return None


def _ecrire(path: Path, contenu: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".%d.tmp" % os.getpid())
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(contenu)
    os.replace(tmp, path)


def preparer_texte(texte: str, cache_dir: str, settings: DiagramSettings) -> str:
    """Remplace les blocs de diagrammes par des placeholders cachés."""
    if not settings.enabled:
        return texte
    dossier = Path(cache_dir) / "diagrams"

    def remplacer(m: "re.Match[str]") -> str:
        affixe, source = m.group(1).lower(), m.group(2)
        moteur = AFFIXES[affixe]
        h = hash_source(moteur + ":" + affixe, source)
        cible = dossier / ("%s.%s.svg" % (h, affixe))
        if not cible.is_file():
            svg = generer(moteur, source, settings)
            if svg is None:
                return m.group(0)
            _ecrire(cible, svg)
        return "<!--diagram:%s.%s-->" % (h, affixe)

    return _FENCE.sub(remplacer, texte)


def remplacer_placeholders(html_txt: str) -> str:
    return _PLACEHOLDER.sub(
        lambda m: (
            '<figure class="diagram"><img src="/diagram/%s.%s.svg" '
            'alt="Diagramme %s"></figure>' % (m.group(1), m.group(2), m.group(2))
        ),
        html_txt,
    )


def chemin_cache(cache_dir: str, h: str, affixe: str) -> Optional[Path]:
    if affixe not in AFFIXES:
        return None
    p = Path(cache_dir) / "diagrams" / ("%s.%s.svg" % (h, affixe))
    return p if p.is_file() else None


def analyser_url_diagramme(pathname: str) -> Optional[tuple[str, str]]:
    """Décompose ``/diagram/<hash>.<affixe>.svg`` en (hash, affixe)."""
    m = _URL_DIAGRAMME.match(pathname)
    return (m.group(1), m.group(2)) if m else None


def generer_fichier_source(source: str, settings: DiagramSettings) -> Optional[Path]:
    """Génère ``<source>.svg`` pour un fichier .puml/.mmd, si nécessaire."""
    if not settings.enabled:
        return None
    src = Path(source)
    affixe = extension_source(str(src))
    if not affixe or not src.is_file():
        return None
    cible = nom_svg_source(str(src))
    try:
        if cible.is_file():
            if cible.stat().st_mtime >= src.stat().st_mtime:
                return cible
            # Ne pas écraser un SVG qui n'a pas été produit par docwatch.
            try:
                if _MARQUEUR not in cible.read_text(encoding="utf-8", errors="ignore"):
                    return cible
            except OSError:
                return None
        source_txt = src.read_text(encoding="utf-8", errors="replace")
        svg = generer(AFFIXES[affixe], source_txt, settings, cwd=str(src.parent))
        if svg is None:
            return None
        svg = "<!-- %s -->\n" % _MARQUEUR + svg
        _ecrire(cible, svg)
        return cible
    except OSError:
        return None


def sources_dans(racine: str, exclude: Iterable[str] = EXCLUDE) -> Iterable[str]:
    for dossier, sous_dossiers, fichiers in os.walk(racine):
        sous_dossiers[:] = [d for d in sous_dossiers if d not in exclude and not d.startswith(".")]
        for nom in fichiers:
            if extension_source(nom):
                yield os.path.join(dossier, nom)


def generer_sources(racine: str, settings: DiagramSettings) -> list[str]:
    faits = []
    for source in sources_dans(racine):
        produit = generer_fichier_source(source, settings)
        if produit is not None:
            faits.append(str(produit))
    return faits


def surveiller(state: State, stop: threading.Event, interval: float = 5.0) -> None:
    """Génère les SVG des fichiers sources des montages, en boucle."""
    if not state.settings.diagrams.enabled:
        return
    while not stop.is_set():
        for montage in state.mounts:
            try:
                generer_sources(montage.path, state.settings.diagrams)
            except Exception:  # noqa: BLE001 - un scan ne doit jamais tuer le serveur
                pass
        stop.wait(interval)
