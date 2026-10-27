"""Arborescence et filtre « documents récemment modifiés ».

L'arbre est chargé à la demande, un niveau à la fois : on ne scanne jamais
tout un disque. Le filtre temporel, lui, parcourt en largeur et s'arrête au
budget de temps ; il est mis en cache et rafraîchi en arrière-plan.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any, Dict, FrozenSet, List, Optional, Tuple

from .config import EXCLUDE

RECENT_MAX = 2000  # au-delà, on tronque et on le signale
RECENT_BUDGET = 3.0  # secondes : on ne bloque pas le serveur indéfiniment
RECENT_TTL = 45.0  # au-delà, le résultat est rafraîchi en arrière-plan
RECENT_FRAIS = 8.0  # en deçà, on ne relance même pas de parcours


def list_dir(
    path: str, exclude: FrozenSet[str] = EXCLUDE
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Liste un seul niveau. Jamais récursif : instantané même sur 18 000 dossiers.

    Chaque entrée porte ``mtime`` pour permettre le tri par date côté client.
    Une seule lecture de répertoire, un seul ``stat`` par entrée.
    """
    dirs: List[Dict[str, Any]] = []
    files: List[Dict[str, Any]] = []
    try:
        with os.scandir(path) as it:
            for e in it:
                try:
                    if e.is_dir(follow_symlinks=False):
                        if e.name in exclude or e.name.startswith("."):
                            continue
                        st = e.stat(follow_symlinks=False)
                        dirs.append({"name": e.name, "path": e.path, "mtime": int(st.st_mtime)})
                    elif e.name.lower().endswith(".md") and not e.name.startswith("."):
                        st = e.stat(follow_symlinks=False)
                        files.append(
                            {
                                "name": e.name,
                                "path": e.path,
                                "size": st.st_size,
                                "mtime": int(st.st_mtime),
                            }
                        )
                except OSError:
                    continue
    except (OSError, PermissionError):
        pass
    # Tri par défaut : plus récent d'abord, nom en second critère pour rester stable.
    dirs.sort(key=lambda x: (-x["mtime"], x["name"].lower()))
    files.sort(key=lambda x: (-x["mtime"], x["name"].lower()))
    return dirs, files


def elements_recents(
    racine: str, heures: float, exclude: FrozenSet[str] = EXCLUDE, budget: Optional[float] = None
) -> Tuple[List[Dict[str, Any]], bool]:
    """Renvoie ce qui a été modifié depuis ``heures`` heures, du plus récent.

    Le parcours est fait en largeur, en visitant les dossiers dont la date est
    la plus récente d'abord : comme on cherche justement ce qui vient d'être
    modifié, le contenu intéressant est atteint très vite. Un très gros arbre
    peut donc être interrogé en quelques secondes et le résultat est marqué
    ``tronque`` s'il reste des dossiers non visités.
    """
    budget = RECENT_BUDGET if budget is None else budget
    limite = time.time() - heures * 3600
    depart = time.time()
    trouves: List[Dict[str, Any]] = []
    tronque = False
    a_visiter = [(racine, time.time())]

    while a_visiter:
        if time.time() - depart > budget:
            tronque = True
            break
        chemin, _ = a_visiter.pop(0)
        try:
            with os.scandir(chemin) as it:
                sous, recents = [], []
                for e in it:
                    try:
                        if e.is_dir(follow_symlinks=False):
                            if e.name in exclude or e.name.startswith("."):
                                continue
                            sous.append((e.path, e.stat(follow_symlinks=False).st_mtime))
                        elif e.name.lower().endswith(".md") and not e.name.startswith("."):
                            st = e.stat(follow_symlinks=False)
                            if st.st_mtime >= limite:
                                recents.append(
                                    {
                                        "name": e.name,
                                        "path": e.path,
                                        "size": st.st_size,
                                        "mtime": int(st.st_mtime),
                                    }
                                )
                    except OSError:
                        continue
        except (OSError, PermissionError):
            continue
        trouves.extend(recents)
        if len(trouves) >= RECENT_MAX:
            trouves = trouves[:RECENT_MAX]
            tronque = True
            break
        # Dossiers récemment modifiés en tête : c'est là que se trouvent les
        # fichiers qui viennent de changer.
        sous.sort(key=lambda x: -x[1])
        a_visiter = sous + a_visiter

    trouves.sort(key=lambda x: -x["mtime"])
    return trouves, tronque


# Le parcours complet d'un gros arbre coûte cher (un stat par fichier). On le
# garde en cache par (racine, fenêtre) pendant RECENT_TTL : changer de fenêtre
# ou recharger la page ne relance pas le parcours.
_recent_cache_data: Dict[Tuple[str, float], Dict[str, Any]] = {}
_recent_lock = threading.Lock()


def _recent_cache(
    racine: str, heures: float, exclude: FrozenSet[str] = EXCLUDE, force: bool = False
) -> Tuple[List[Dict[str, Any]], bool]:
    """Renvoie (éléments, tronqué) en réutilisant un parcours récent.

    Stratégie « stale-while-revalidate » : un résultat frais est servi
    directement ; un résultat plus vieux est servi IMMÉDIATEMENT et un parcours
    est relancé en arrière-plan pour le suivant. L'affichage ne bloque donc
    jamais, et un document tout juste créé apparaît au cycle suivant plutôt
    qu'après une attente.
    """
    cle = (os.path.realpath(racine), round(heures, 3))

    with _recent_lock:
        entree = _recent_cache_data.get(cle)
        if entree and not force:
            age = time.time() - entree["quand"]
            if age < RECENT_FRAIS:
                return entree["elements"], entree["tronque"]
            if age < 10 * RECENT_TTL and not entree.get("en_cours"):
                entree["en_cours"] = True  # relecture en tâche de fond
                threading.Thread(
                    target=_recent_rafraichir, args=(cle, heures, exclude), daemon=True
                ).start()
            return entree["elements"], entree["tronque"]

    elements, tronque = elements_recents(racine, heures, exclude)
    with _recent_lock:
        _recent_cache_data[cle] = {"quand": time.time(), "elements": elements, "tronque": tronque}
        for k in list(_recent_cache_data):
            if time.time() - _recent_cache_data[k]["quand"] > 10 * RECENT_TTL:
                del _recent_cache_data[k]
    return elements, tronque


def _recent_rafraichir(cle: Tuple[str, float], heures: float, exclude: FrozenSet[str]) -> None:
    """Relance un parcours sans faire attendre personne."""
    try:
        elements, tronque = elements_recents(cle[0], heures, exclude)
    except Exception:  # noqa: BLE001 - une tâche de fond ne doit jamais tuer le serveur
        elements, tronque = None, None
    with _recent_lock:
        if elements is not None:
            _recent_cache_data[cle] = {
                "quand": time.time(),
                "elements": elements,
                "tronque": tronque,
            }
        elif cle in _recent_cache_data:
            _recent_cache_data[cle]["en_cours"] = False


def arbre_recent(elements: List[Dict[str, Any]], racine: str) -> Dict[str, Any]:
    """Construit un arbre élagué : seuls les documents trouvés et leurs dossiers.

    Chaque dossier porte ``count``, le nombre de documents retenus dans sa
    descendance : c'est ce qui permet d'afficher un compteur sur la ligne du
    dossier et de savoir où se concentrent les changements. Les chemins sont
    reconstruits au fil du parcours, jamais stockés dans les nœuds
    intermédiaires.
    """
    racine = os.path.realpath(racine)
    noeud_racine: Dict[str, Any] = {"dossiers": {}, "fichiers": []}

    for e in elements:
        chemin = e["path"]
        if not chemin.startswith(racine + os.sep):
            continue
        morceaux = chemin[len(racine) + 1 :].split(os.sep)
        courant = noeud_racine
        for morceau in morceaux[:-1]:
            sous = courant["dossiers"].get(morceau)
            if sous is None:
                sous = {"dossiers": {}, "fichiers": []}
                courant["dossiers"][morceau] = sous
            courant = sous
        courant["fichiers"].append(e)

    def finaliser(noeud: Dict[str, Any], chemin: str, nom: str) -> Tuple[Dict[str, Any], int]:
        dossiers, fichiers, total = [], [], 0
        for nom_sous, sous in noeud["dossiers"].items():
            enfant, n = finaliser(sous, os.path.join(chemin, nom_sous), nom_sous)
            total += n
            dossiers.append(enfant)
        for e in noeud["fichiers"]:
            fichiers.append(
                {
                    "name": e["name"],
                    "path": e["path"],
                    "size": e["size"],
                    "mtime": e["mtime"],
                    "type": "file",
                }
            )
            total += 1
        # Dossiers les plus fournis d'abord, puis les plus récents.
        dossiers.sort(key=lambda x: (-x["count"], -x["mtime"], x["name"].lower()))
        fichiers.sort(key=lambda x: (-x["mtime"], x["name"].lower()))
        dates = [d["mtime"] for d in dossiers] + [f["mtime"] for f in fichiers]
        return (
            {
                "name": nom,
                "path": chemin,
                "type": "dir",
                "mtime": max(dates) if dates else 0,
                "count": total,
                "dirs": dossiers,
                "files": fichiers,
            },
            total,
        )

    arbre, total = finaliser(noeud_racine, racine, os.path.basename(racine) or racine)
    arbre["total"] = total
    arbre["maintenant"] = int(time.time())
    return arbre
