"""Configuration, montages et état mutable du serveur.

Une instance peut servir plusieurs **montages** : chaque montage porte un nom
(le premier segment de l'URL) et une racine sur le disque. Le serveur reste
local ; les montages sont les bornes de sécurité.

La configuration vit dans ``$XDG_CONFIG_HOME/docwatch/config.toml`` :

    [server]
    port = 8771

    [[mounts]]
    name = "drave"
    path = "~/GitHub/Qtrinet"
    label = "Drave"

    [[mounts]]
    name = "docwatch"
    path = "~/GitHub/Qtrinet/tools/docwatch"

    [diagrams]
    enabled = true
    plantuml = "plantuml"
    mermaid = "mmdc"
"""

from __future__ import annotations

import os
import re
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Tuple

try:  # Python 3.11+
    import tomllib
except ImportError:  # pragma: no cover - dépend de la version de Python
    import tomli as tomllib  # type: ignore[no-redef]

DEFAULT_PORT = 8770
DEFAULT_HOST = "127.0.0.1"
NOM_MONTAGE = re.compile(r"^[A-Za-z0-9._-]+$")

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


def default_config_path() -> str:
    return os.path.join(_xdg("XDG_CONFIG_HOME", ".config"), "docwatch", "config.toml")


def _reel(chemin: str) -> str:
    return os.path.realpath(os.path.abspath(os.path.expanduser(chemin)))


def _nom_depuis_racine(chemin: str) -> str:
    nom = re.sub(r"[^A-Za-z0-9._-]+", "-", os.path.basename(chemin)).strip("-")
    return nom or "root"


@dataclass(frozen=True)
class Mount:
    """Un dépôt monté sous un nom d'URL."""

    name: str
    path: str
    label: str = ""

    def as_dict(self) -> Dict[str, str]:
        return {"name": self.name, "path": self.path, "label": self.label or self.name}


@dataclass(frozen=True)
class DiagramSettings:
    """Réglages de génération des diagrammes PlantUML/Mermaid."""

    enabled: bool = True
    plantuml: str = "plantuml"
    mermaid: str = "mmdc"
    timeout: float = 30.0
    puppeteer: str = ""


@dataclass(frozen=True)
class Settings:
    """Réglages immuables d'une instance."""

    mounts: Tuple[Mount, ...]
    port: int = DEFAULT_PORT
    host: str = DEFAULT_HOST
    cache_dir: str = ""
    config_dir: str = ""
    exclude: FrozenSet[str] = EXCLUDE
    diagrams: DiagramSettings = DiagramSettings()

    @property
    def root(self) -> str:
        """Premier montage : compatibilité avec le mode mono-racine."""
        return self.mounts[0].path

    @property
    def pins_file(self) -> str:
        return os.path.join(self.config_dir, "pins.json")


def _mounts_depuis_liste(brut: Any) -> Tuple[Mount, ...]:
    if not isinstance(brut, list) or not brut:
        raise ValueError("la configuration doit déclarer au moins un [[mounts]]")
    mounts: List[Mount] = []
    noms = set()
    for item in brut:
        if not isinstance(item, dict):
            raise ValueError("chaque [[mounts]] doit être une table")
        nom = str(item.get("name") or "").strip()
        if not NOM_MONTAGE.match(nom):
            raise ValueError("nom de montage invalide : %r" % nom)
        if nom in noms:
            raise ValueError("nom de montage en double : %s" % nom)
        noms.add(nom)
        chemin = _reel(str(item.get("path") or ""))
        if not os.path.isdir(chemin):
            raise ValueError("racine de montage invalide (%s) : %s" % (nom, chemin))
        mounts.append(Mount(name=nom, path=chemin, label=str(item.get("label") or "")))
    return tuple(mounts)


def load_config(path: str) -> Tuple[Tuple[Mount, ...], Optional[int], DiagramSettings]:
    """Lit un ``config.toml``. Lève ``ValueError`` si le fichier est invalide."""
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except OSError as exc:
        raise ValueError("configuration illisible : %s (%s)" % (path, exc)) from exc
    except tomllib.TOMLDecodeError as exc:
        raise ValueError("TOML invalide dans %s : %s" % (path, exc)) from exc

    server = data.get("server") or {}
    port = server.get("port")
    if port is not None:
        try:
            port = int(port)
        except (TypeError, ValueError):
            raise ValueError("port invalide dans la configuration") from None
        if not 0 <= port <= 65535:
            raise ValueError("port invalide dans la configuration : %s" % port)

    diagrams_data = data.get("diagrams") or {}
    diagrams = DiagramSettings(
        enabled=bool(diagrams_data.get("enabled", True)),
        plantuml=str(diagrams_data.get("plantuml") or "plantuml"),
        mermaid=str(diagrams_data.get("mermaid") or "mmdc"),
        timeout=float(diagrams_data.get("timeout", 30.0)),
        puppeteer=str(diagrams_data.get("puppeteer") or ""),
    )
    return _mounts_depuis_liste(data.get("mounts")), port, diagrams


def config_template(root: Optional[str] = None) -> str:
    """Modèle commenté pour ``docwatch --init-config``."""
    racine = _reel(root or os.getcwd())
    nom = _nom_depuis_racine(racine)
    return """# docwatch — configuration d'une instance multi-racines.
# Les montages deviennent les premiers segments de l'URL :
#   /{nom}/docs/guide.md

[server]
port = 8771

[[mounts]]
name = "{nom}"
path = "{racine}"
label = "{nom}"

# Ajoute d'autres dépôts ainsi :
# [[mounts]]
# name = "autre"
# path = "~/Documents/autre"
# label = "Autre dépôt"

[diagrams]
enabled = true
plantuml = "plantuml"
mermaid = "mmdc"
timeout = 30
""".format(nom=nom, racine=racine)


def make_settings(
    root: Optional[str] = None,
    port: Optional[int] = None,
    host: str = DEFAULT_HOST,
    cache_dir: Optional[str] = None,
    config_dir: Optional[str] = None,
    config_path: Optional[str] = None,
) -> Settings:
    """Construit les réglages.

    - ``root`` fourni : un seul montage (mode historique) ;
    - sinon, ``config_path`` ou le fichier XDG par défaut s'il existe ;
    - sinon, le répertoire courant comme unique montage.
    """
    if root is not None and config_path:
        raise ValueError("une racine et un fichier de configuration sont exclusifs")

    choix_config = config_path
    if choix_config is None and root is None:
        defaut = default_config_path()
        if os.path.isfile(defaut):
            choix_config = defaut

    port_config: Optional[int] = None
    diagrams = DiagramSettings()
    if choix_config:
        mounts, port_config, diagrams = load_config(choix_config)
    else:
        brut = os.fspath(root) if root is not None else os.getcwd()
        chemin = _reel(brut)
        if not os.path.isdir(chemin):
            raise ValueError("racine invalide : %s" % chemin)
        mounts = (
            Mount(
                name=_nom_depuis_racine(chemin),
                path=chemin,
                label=os.path.basename(chemin) or chemin,
            ),
        )

    port_final = (
        port if port is not None else (port_config if port_config is not None else DEFAULT_PORT)
    )
    if not 0 <= int(port_final) <= 65535:
        raise ValueError("port invalide : %s" % port_final)

    if cache_dir:
        cache = _reel(cache_dir)
    else:
        cache = os.path.join(_xdg("XDG_CACHE_HOME", ".cache"), "docwatch")
    if config_dir:
        config = _reel(config_dir)
    else:
        config = os.path.join(_xdg("XDG_CONFIG_HOME", ".config"), "docwatch")
    return Settings(
        mounts=mounts,
        port=int(port_final),
        host=host,
        cache_dir=cache,
        config_dir=config,
        diagrams=diagrams,
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
    def mounts(self) -> Tuple[Mount, ...]:
        return self.settings.mounts

    @property
    def initial_root(self) -> str:
        """Premier montage : compatibilité avec le mode mono-racine."""
        return self.settings.root

    @property
    def pins_file(self) -> str:
        return self.settings.pins_file

    def set_root(self, chemin: str) -> None:
        with self._lock:
            self.root = chemin

    def mount_by_name(self, nom: str) -> Optional[Mount]:
        for m in self.mounts:
            if m.name == nom:
                return m
        return None

    def mount_for_path(self, chemin: str) -> Optional[Mount]:
        """Montage le plus précis contenant ``chemin`` (réel)."""
        try:
            p = _reel(chemin)
        except (OSError, ValueError):
            return None
        candidats = [m for m in self.mounts if self._dans(p, m.path)]
        if not candidats:
            return None
        return max(candidats, key=lambda m: len(m.path))

    @staticmethod
    def _dans(chemin: str, racine: str) -> bool:
        return chemin == racine or chemin.startswith(racine + os.sep)

    def resolve_path(self, raw: str) -> Optional[Tuple[Mount, str]]:
        """Résout un chemin absolu sous l'un des montages."""
        if raw is None:
            return None
        try:
            from urllib.parse import unquote

            texte = unquote(str(raw))
        except (UnicodeDecodeError, ValueError):
            return None
        if "\x00" in texte:
            return None
        if not texte:
            m = self.mounts[0]
            return m, m.path
        try:
            p = _reel(texte)
        except (OSError, ValueError):
            return None
        m = self.mount_for_path(p)
        return (m, p) if m else None

    def resolve_root(self, raw: str) -> Optional[Tuple[Mount, str]]:
        cible = self.resolve_path(raw)
        if cible and os.path.isdir(cible[1]):
            return cible
        return None

    def mount_from_url(self, pathname: str) -> Optional[Tuple[Mount, str]]:
        """Traduit ``/montage/docs/x.md`` en (montage, chemin absolu)."""
        from urllib.parse import unquote

        try:
            texte = unquote(pathname or "/")
        except (UnicodeDecodeError, ValueError):
            return None
        if "\x00" in texte:
            return None
        texte = texte.lstrip("/")
        segments = texte.split("/") if texte else []

        if len(self.mounts) > 1:
            m = self.mount_by_name(segments[0]) if segments else None
            if m:
                reste = "/".join(segments[1:])
                p = _reel(os.path.join(m.path, reste))
                return (m, p) if self._dans(p, m.path) else None
            # Ancienne URL sans préfixe : on essaie chaque montage, puis le
            # premier par défaut.
            for m in self.mounts:
                p = _reel(os.path.join(m.path, texte))
                if self._dans(p, m.path) and os.path.exists(p):
                    return m, p
            m = self.mounts[0]
            p = _reel(os.path.join(m.path, texte))
            return (m, p) if self._dans(p, m.path) else None

        m = self.mounts[0]
        p = _reel(os.path.join(m.path, texte))
        return (m, p) if self._dans(p, m.path) else None

    def mounts_json(self) -> List[Dict[str, str]]:
        return [m.as_dict() for m in self.mounts]
