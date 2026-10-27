"""Validation des chemins reçus du client.

Le serveur ne lit que sous une racine choisie au lancement. Toute route qui
accepte un chemin passe par :func:`safe_path` (racine courante) ou
:func:`safe_bounded` (racine de départ). Les deux résolvent les liens
symboliques avant de comparer : un lien qui pointe hors de l'arbre est refusé.
"""

from __future__ import annotations

import os
from typing import Optional
from urllib.parse import unquote


def in_root(chemin: str, root: str) -> bool:
    """Le chemin réel est-il dans l'arbre ``root`` (racine comprise) ?"""
    try:
        r = os.path.realpath(root)
        p = os.path.realpath(chemin)
    except (OSError, ValueError):
        return False
    return p == r or p.startswith(r + os.sep)


def safe_path(raw: str, root: str) -> Optional[str]:
    """Résout ``raw`` et vérifie qu'il reste sous ``root``.

    Retourne ``None`` si la cible sort de l'arbre. Le chemin vide désigne la
    racine elle-même, ce qui simplifie les appels ``/tree?path=``.
    """
    if raw is None:
        return None
    try:
        texte = unquote(str(raw))
    except (UnicodeDecodeError, ValueError):
        return None
    if "\x00" in texte:
        return None
    if not texte:
        return os.path.realpath(root)
    try:
        cible = os.path.realpath(os.path.abspath(os.path.expanduser(texte)))
    except (OSError, ValueError):
        return None
    return cible if in_root(cible, root) else None


def safe_bounded(raw: str, initial_root: str) -> Optional[str]:
    """Comme :func:`safe_path`, mais borné par la racine de départ.

    Sert au changement de racine affichée : on peut descendre dans l'arbre
    autorisé, jamais remonter au-dessus.
    """
    if raw is None:
        return None
    try:
        texte = unquote(str(raw))
    except (UnicodeDecodeError, ValueError):
        return None
    if "\x00" in texte:
        return None
    if not texte:
        return os.path.realpath(initial_root)
    try:
        cible = os.path.realpath(os.path.abspath(os.path.expanduser(texte)))
    except (OSError, ValueError):
        return None
    return cible if in_root(cible, initial_root) else None
