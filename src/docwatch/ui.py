"""Gabarit HTML de l'interface.

Le CSS et le JavaScript sont des fichiers statiques du paquet, extraits du
script d'origine pour rester éditables et testables séparément. Le gabarit ne
contient que l'initialisation de la page : la liste des montages est injectée,
puis ``demarrer()`` (dans ``tree.js``) choisit le montage et le document à
partir de l'URL.
"""

from __future__ import annotations

import html
import json
import os
from importlib.resources import files
from typing import Sequence
from urllib.parse import quote

from .config import Mount


def _lire_statique(nom: str) -> str:
    return (files("docwatch") / "static" / nom).read_text(encoding="utf-8")


CSS = _lire_statique("style.css")
TREE_JS = _lire_statique("tree.js")


def page_html(mounts: Sequence[Mount], root: str) -> str:
    liens = ""
    if len(mounts) > 1:
        liens = "".join(
            '<a class="mount" href="/%s/" title="%s">%s</a>'
            % (
                quote(m.name),
                html.escape(m.path),
                html.escape(m.label or m.name),
            )
            for m in mounts
        )
    # JSON injecte dans un <script> : on neutralise une eventuelle chaine
    # </script> dans un libelle de montage.
    mounts_json = json.dumps([m.as_dict() for m in mounts]).replace("</", "<\\/")
    titre = html.escape(os.path.basename(root) or "docwatch")
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>docwatch \u2014 {titre}</title>
<style>{CSS}</style></head><body>
<div id="wrap">
  <div id="side">
    <div id="mounts">{liens}</div>
    <div class="hint">Cliquez un dossier pour le deplier. Survolez-le et cliquez
      ○ pour l'epingler. Les documents sont servis en lecture seule ; seules les
      epingles et les SVG de diagrammes generes s'ecrivent.</div>
    <div id="pins"></div>
    <div id="treehead">
      <h3>🗂 Arborescence</h3>
      <div id="rootbar"></div>
      <div id="filtrebar">
        <span title="N'afficher que les documents modifies recemment">🕒</span>
        <input type="number" id="fheures" min="1" max="8760" step="1" value="24"
               title="Nombre d'heures" onchange="recentLancer()">
        <span>h</span>
        <button data-h="1" onclick="recentRapide(1)">1 h</button>
        <button data-h="24" onclick="recentRapide(24)">24 h</button>
        <button data-h="168" onclick="recentRapide(168)">7 j</button>
        <button id="ftout" class="on" onclick="recentArreter()"
                title="Revenir a l'arborescence complete">Tout</button>
      </div>
      <div id="filtreinfo"></div>
      <div id="sortbar">
        <button data-mode="date" onclick="setSort('date')">🕒 Recents</button>
        <button data-mode="nom" onclick="setSort('nom')">A → Z</button>
        <span id="sortlabel"></span>
      </div>
    </div>
    <div id="tree"></div>
  </div>
  <div id="main"><h1>docwatch</h1>
    <p>Lecteur Markdown en lecture seule sur <code>{html.escape(root)}</code>.</p>
    <p>Choisissez un fichier dans l'arbre, ou epinglez un dossier pour y
       revenir en un clic.</p></div>
</div>
<div id="ctx" hidden></div>
<div id="meta">
  <span><b id="fname">\u2014</b></span>
  <span id="fmeta"></span>
  <span id="frel"></span>
  <span id="upd">\u21bb mis a jour</span>
  <span id="controls">
    <button id="refresh" title="Relire le fichier et l'arbre depuis le disque"
            onclick="refreshAll()">\u21bb Rafraichir</button>
    <button id="pinfile" onclick="togglePin(curPath, null, 'file')"
            title="Epingler le document affiche">☆</button>
    <button id="sound" onclick="toggleSound()"></button>
  </span>
</div>
<script>
{TREE_JS}
const MOUNTS = {mounts_json};
(async () => {{ await demarrer(); }})();
</script></body></html>"""
