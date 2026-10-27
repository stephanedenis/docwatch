# Journal des changements

Le format suit [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/) et le
versionnage sémantique.

## [0.1.0] — 2026-10-27

Première version autonome, extraite de l'outillage documentaire de Drave.

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

### Conservé

- arborescence chargée à la demande, rechargement toutes les 3 s, épingles,
  filtre temporel, comparaison de jetons 64 bits, position de lecture conservée.
