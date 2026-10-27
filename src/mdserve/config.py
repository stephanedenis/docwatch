"""Configuration et état mutable du serveur.

Le serveur ne sert qu'un seul arbre à la fois. La racine affichée peut être
restreinte à un sous-dossier, mais jamais élargie au-delà de la racine de
départ : ``Settings.root`` est la borne, ``State.root`` la vue courante.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from typing import FrozenSet, Optional

DEFAULT_PORT = 8770
DEFAULT_HOST = "127.0.0.1"

#: Dossiers jamais parcourus : ils ne contiennent pas de documentation utile
#: et un scan récursif y perdrait son temps (ou suivrait des liens infinis).
EXCLUDE = frozenset(
    {
        ".git",
        "node_modules",
        ".cache",
        "__pycache__",
        ".venv",
        "venv",
        "dist",
        "build",
        ".mypy_cache",
        ".pytest_cache",
    }
)


def _xdg(variable: str, defaut: str) -> str:
    """Répertoire XDG, avec repli sur ``~/.cache`` ou ``~/.config``."""
    valeur = os.environ.get(variable)
    if valeur:
        return os.path.expanduser(valeur)
    return os.path.join(os.path.expanduser("~"), defaut)


@dataclass(frozen=True)
class Settings:
    """Réglages immuables d'une instance."""

    root: str
    port: int = DEFAULT_PORT
    host: str = DEFAULT_HOST
    cache_dir: str = ""
    config_dir: str = ""
    exclude: FrozenSet[str] = EXCLUDE

    @property
    def pins_file(self) -> str:
        return os.path.join(self.config_dir, "pins.json")


def make_settings(
    root: Optional[str] = None,
    port: int = DEFAULT_PORT,
    host: str = DEFAULT_HOST,
    cache_dir: Optional[str] = None,
    config_dir: Optional[str] = None,
) -> Settings:
    """Valide la racine et construit les réglages.

    ``root`` vaut le répertoire courant par défaut : un outil générique ne
    doit pas connaître l'arborescence d'un projet particulier.
    """
    brut = os.fspath(root) if root is not None else os.getcwd()
    chemin = os.path.realpath(os.path.abspath(os.path.expanduser(brut)))
    if not os.path.isdir(chemin):
        raise ValueError("racine invalide : %s" % chemin)
    if not 0 <= int(port) <= 65535:
        raise ValueError("port invalide : %s" % port)

    cache = os.path.realpath(
        os.path.expanduser(cache_dir) if cache_dir else _xdg("XDG_CACHE_HOME", ".cache")
    )
    config = os.path.realpath(
        os.path.expanduser(config_dir) if config_dir else _xdg("XDG_CONFIG_HOME", ".config")
    )
    return Settings(
        root=chemin,
        port=int(port),
        host=host,
        cache_dir=os.path.join(cache, "mdserve"),
        config_dir=os.path.join(config, "mdserve"),
    )


@dataclass
class State:
    """État partagé entre les requêtes d'une même instance."""

    settings: Settings
    root: str = ""
    port: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def __post_init__(self) -> None:
        if not self.root:
            self.root = self.settings.root
        if not self.port:
            self.port = self.settings.port

    @property
    def initial_root(self) -> str:
        """Borne du périmètre : la racine passée au lancement."""
        return self.settings.root

    @property
    def pins_file(self) -> str:
        return self.settings.pins_file

    def set_root(self, chemin: str) -> None:
        with self._lock:
            self.root = chemin
