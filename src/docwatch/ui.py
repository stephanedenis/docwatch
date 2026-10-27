"""Gabarit HTML de l'interface.

Le CSS et le JavaScript sont des fichiers statiques du paquet, extraits du
script d'origine pour rester éditables et testables séparément. Le gabarit ne
contient que l'initialisation de la page.
"""

from __future__ import annotations

import html
import json
import os
from importlib.resources import files


def _lire_statique(nom: str) -> str:
    return (files("docwatch") / "static" / nom).read_text(encoding="utf-8")


CSS = _lire_statique("style.css")
TREE_JS = _lire_statique("tree.js")


def page_html(root: str) -> str:
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>docwatch \u2014 {html.escape(os.path.basename(root))}</title>
<style>{CSS}</style></head><body>
<div id="wrap">
  <div id="side">
    <div class="hint">Cliquez un dossier pour le deplier. Survolez-le et cliquez
      ○ pour l'epingler. Les fichiers ne sont jamais modifies.</div>
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
// charge le premier niveau au demarrage
(async () => {{
  currentRoot = {json.dumps(root)};
  try {{                              // perimetre autorise, pour la barre
    const rr = await fetch('/root');
    const dd = await rr.json();
    borne = dd.borne || dd.root || currentRoot;
    if (dd.root) currentRoot = dd.root;
  }} catch (e) {{ borne = currentRoot; }}
  setSort(sortMode);                   // applique la preference enregistree
  toggleSoundIfNeeded();
  await loadPins(true);        // premier passage : nettoie les disparues
  const r = await fetch('/tree?path=' + encodeURIComponent(currentRoot));
  const data = await r.json();
  const tree = document.getElementById('tree');
  // l'horloge du serveur au chargement sert de reference : tout ce qui est
  // modifie apres est signale comme « change depuis l'ouverture »
  loadedAt = data.now || 0;
  trackEntries(data.files);
  rememberMtimes(data.files); rememberMtimes(data.dirs);
  rememberSubdirs(data.dirs);
  tree._data = data;                   // memorise pour pouvoir re-trier
  renderBox(tree, data);
  tree.dataset.loaded = '1';
  displayedDirs.add(currentRoot);
  for (const d of (data.dirs || [])) displayedDirs.add(d.path);
  paintRootbar();
  // la racine n'est pas « depliee » : on ne scrute pas ses 39 enfants
  paintUnseen();
  // ouverture directe : URL propre /docs/guide.md, ou ancienne /?f=/abs
  let cible = null;
  if (location.pathname.toLowerCase().endsWith('.md')) {{
    cible = resoudreLien(location.pathname);
  }} else {{
    cible = new URLSearchParams(location.search).get('f');
  }}
  if (cible) {{
    const up = cible.lastIndexOf('/');
    if (up > 0) await expandTo(cible.slice(0, up));   // devoile le chemin
    await openFile(cible, null, false, {{replace: true, hash: location.hash}});
  }}
}})();
</script></body></html>"""
