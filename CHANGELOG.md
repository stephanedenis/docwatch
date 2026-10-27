# Journal des changements

Le format suit [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/) et le
versionnage sémantique.

## [0.2.0] — 2026-10-27

### Modifié

- **renommage du projet en `docwatch`** : distribution `docwatch`, module
  `docwatch`, commandes `docwatch` et `docopen`, répertoires
  `~/.config/docwatch` et `~/.cache/docwatch` ;
- `serveur-doc.py` retiré de Drave : `docwatch` est désormais le seul serveur
  de documentation du dépôt ;
- `--config-dir` et `--cache-dir` désignent le répertoire **final** ; le
  sous-dossier `docwatch` n'est ajouté qu'aux racines XDG par défaut ;
- 64 tests, dont le lien absolu résolu contre la racine.

### Conservé

- arborescence chargée à la demande, rechargement toutes les 3 s, épingles,
  filtre temporel, comparaison de jetons 64 bits, position de lecture conservée.

## [0.1.0] — 2026-10-27

Première version autonome, extraite de l'outillage documentaire de Drave et
publiée sous le nom `mdserve-local`.

### Ajouté

- paquet installable (`mdserve-local`), points d'entrée `mdserve` et `mdopen` ;
- tests de rendu, de cache, d'épingles, de sécurité des chemins et des routes HTTP ;
- CI GitHub Actions (Python 3.9 à 3.13) ;
- `--no-browser`, `--config-dir`, `--cache-dir`, `--version` ;
- port `0` (port libre choisi par le système) ;
- documentation de la sécurité et d'une unité systemd.

### Modifié par rapport au script d'origine

- la racine par défaut est le **répertoire courant**, et non un chemin propre à
  un projet ;
- les liens relatifs vers un `.md` ouvrent le document dans le lecteur
  (`/?f=…`) au lieu de renvoyer un 404 ;
- les liens absolus (`/docs/x.md`) sont résolus contre la racine servie ;
- `/asset` ne sert plus qu'une **liste fermée** de types (images, polices,
  CSS/JS, PDF, textes) : un `.env` n'est plus téléchargeable ;
- le serveur vérifie les en-têtes `Host` et `Origin` ;
- le CSS et le JavaScript sont des fichiers statiques du paquet, plus des
  constantes noyées dans le script ;
- les épingles sont écrites avec des permissions `0600` ;
- les fichiers et dossiers cachés ne sont plus listés dans l'arborescence ;
- `mdopen` déduit la racine du dossier commun des fichiers et n'a plus de
  chemins d'installation codés en dur.
