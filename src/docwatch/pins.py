"""Épingles : dossiers et documents en accès rapide.

Le seul fichier que docwatch écrit (hors cache) est ``pins.json``. Il est
partagé entre toutes les racines servies : une épingle située hors de la vue
courante est masquée, jamais supprimée.
"""

from __future__ import annotations

import json
import os
import stat
import threading
from typing import Any, Dict, List, Optional

from .paths import in_root

_pins_lock = threading.Lock()


def _norm_pins(brut: Any) -> Optional[Dict[str, str]]:
    """Normalise une entrée épinglée en ``{path, name}``."""
    if isinstance(brut, str):
        brut = {"path": brut}
    if isinstance(brut, dict) and brut.get("path"):
        return {"path": brut["path"], "name": brut.get("name") or os.path.basename(brut["path"])}
    return None


def load_pins(pins_file: str) -> Dict[str, List[Dict[str, str]]]:
    """Lit les épingles. Ne lève jamais d'exception.

    Deux formats sont acceptés : l'ancien (une liste unique, tout étant
    supposé dossier) et le nouveau (``{folders, files}``). L'ancien est
    converti à la volée, un dossier existant restant un dossier.
    """
    vide: Dict[str, List[Dict[str, str]]] = {"folders": [], "files": []}
    try:
        with open(pins_file, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return vide
    if isinstance(data, dict) and ("folders" in data or "files" in data):
        return {
            "folders": [x for x in (_norm_pins(i) for i in data.get("folders") or []) if x],
            "files": [x for x in (_norm_pins(i) for i in data.get("files") or []) if x],
        }
    # ancien format : une seule liste, aiguillée selon le type réel
    liste = data.get("pins") if isinstance(data, dict) else data
    out = {"folders": [], "files": []}
    for item in liste if isinstance(liste, list) else []:
        entree = _norm_pins(item)
        if not entree:
            continue
        cible = "folders" if os.path.isdir(entree["path"]) else "files"
        out[cible].append(entree)
    return out


def save_pins(pins: Dict[str, List[Dict[str, str]]], pins_file: str) -> None:
    """Écrit les épingles de façon atomique (fichier temporaire puis renommage)."""
    dossier = os.path.dirname(pins_file) or "."
    os.makedirs(dossier, mode=0o700, exist_ok=True)
    tmp = pins_file + ".%d.tmp" % os.getpid()
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(pins, f, ensure_ascii=False, indent=2)
        f.write("\n")
    try:
        os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
    os.replace(tmp, pins_file)


def pin_entry(path: str) -> Dict[str, str]:
    return {"path": path, "name": os.path.basename(path) or path}


def pins_action(
    action: str, path: str, kind: str, pins_file: str
) -> Optional[Dict[str, List[Dict[str, str]]]]:
    """Ajoute, retire ou bascule une épingle. ``kind`` vaut ``folder`` ou ``file``.

    Dépinger un dossier retire aussi les documents épinglés qu'il contenait :
    les garder seuls, sans leur parent, n'aurait plus de sens dans la liste.
    """
    with _pins_lock:
        pins = load_pins(pins_file)
        cle = "folders" if kind == "folder" else "files"
        present = any(x["path"] == path for x in pins[cle])
        if action == "add":
            if not present:
                pins[cle].append(pin_entry(path))
        elif action == "remove":
            pins[cle] = [x for x in pins[cle] if x["path"] != path]
            if kind == "folder":  # nettoie les enfants
                prefixe = path + os.sep
                pins["files"] = [x for x in pins["files"] if not x["path"].startswith(prefixe)]
                pins["folders"] = [x for x in pins["folders"] if not x["path"].startswith(prefixe)]
        elif action == "toggle":
            if present:
                pins[cle] = [x for x in pins[cle] if x["path"] != path]
                if kind == "folder":
                    prefixe = path + os.sep
                    pins["files"] = [x for x in pins["files"] if not x["path"].startswith(prefixe)]
            else:
                pins[cle].append(pin_entry(path))
        else:
            return None
        save_pins(pins, pins_file)
        return pins


def pins_with_mtime(pins: Any) -> Dict[str, List[Dict[str, Any]]]:
    """Ajoute dates et tailles aux épingles, puis trie par date décroissante.

    Accepte l'ancienne forme (une liste) comme la nouvelle (dossiers +
    documents). Chaque entrée est annotée ``kind``, ce qui permet au client de
    savoir si un clic doit ouvrir un document ou déployer un dossier.
    """
    if isinstance(pins, list):
        pins = {"folders": pins, "files": []}

    def enrichir(entrees: Any, kind: str) -> List[Dict[str, Any]]:
        out = []
        for e in entrees or []:
            item = dict(e)
            item["kind"] = kind
            try:
                st = os.stat(item["path"])
                item["mtime"] = int(st.st_mtime)
                item["size"] = st.st_size if kind == "file" else 0
                item["existe"] = True
            except OSError:
                item["mtime"] = 0
                item["size"] = 0
                item["existe"] = False
            out.append(item)
        return out

    dossiers = enrichir(pins.get("folders"), "folder")
    fichiers = enrichir(pins.get("files"), "file")
    cle = lambda x: (-x["mtime"], x["name"].lower())  # noqa: E731
    return {"folders": sorted(dossiers, key=cle), "files": sorted(fichiers, key=cle)}


def pins_for_root(
    pins: Dict[str, List[Dict[str, str]]], root: str
) -> Dict[str, List[Dict[str, str]]]:
    """Ne garde que les épingles situées dans l'arbre affiché.

    Les autres restent dans ``pins.json`` : elles réapparaîtront en remontant
    la racine. On ne les perd donc jamais en se restreignant à un sous-dossier.
    """
    return {
        "folders": [x for x in pins.get("folders", []) if in_root(x["path"], root)],
        "files": [x for x in pins.get("files", []) if in_root(x["path"], root)],
    }


def prune_pins(pins_file: str, root: str) -> List[Dict[str, str]]:
    """Retire les épingles devenues inaccessibles dans la racine courante.

    Règles :
      - une épingle hors de la racine courante n'est jamais touchée : elle est
        seulement masquée, et l'élagage ne décide rien sur ce qu'il ne peut pas
        observer ;
      - un DOCUMENT disparu est retiré dès que son dossier parent n'existe plus :
        son emplacement a disparu, l'épingle ne peut plus rien ouvrir ;
      - un DOSSIER disparu est retiré seulement si plus aucun ancêtre ne
        subsiste : si un parent est encore là, l'arborescence est intacte et le
        dossier peut réapparaître (renommage, recréation), on garde l'épingle.
    """
    with _pins_lock:
        pins = load_pins(pins_file)
        retires: List[Dict[str, str]] = []
        gardes: Dict[str, List[Dict[str, str]]] = {"folders": [], "files": []}
        for cle, kind in (("folders", "folder"), ("files", "file")):
            for x in pins[cle]:
                chemin = x["path"]
                if os.path.exists(chemin) or not in_root(chemin, root):
                    gardes[cle].append(x)
                    continue
                # Le dossier parent décide :
                #   - il existe encore -> l'emplacement est là, l'élément a été
                #     supprimé ou renommé : on retire l'épingle ;
                #   - il n'existe plus -> tout le sous-arbre a disparu, on
                #     CONSERVE l'épingle : elle redeviendra utile si le dossier
                #     revient (support rebranché, dossier restauré).
                a_retirer = os.path.isdir(os.path.dirname(chemin))
                if a_retirer:
                    retires.append({"path": chemin, "name": x["name"], "kind": kind})
                else:
                    gardes[cle].append(x)
        if retires:
            try:
                save_pins(gardes, pins_file)
            except OSError:
                return []
    return retires
