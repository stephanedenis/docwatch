# Journal des changements

Le format suit [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/) et le
versionnage sémantique.

## [0.4.0] — 2026-10-27

### Ajouté

- **configuration multi-racines** dans `$XDG_CONFIG_HOME/docwatch/config.toml` :
  une instance sert plusieurs dépôts, chaque `[[mounts]]` portant un nom et un
  chemin ; les URLs deviennent `/<montage>/docs/guide.md` ;
- routes `/mounts` et `/status` (liste des montages), liens de montage dans le
  panneau de gauche, changement de dépôt par navigation ;
- épingles et filtre temporel par montage (`/pins?root=…`, `/recent?root=…`) ;
- options `--config`, `--init-config`, `--force`, `--mount` ;
- **génération des diagrammes** PlantUML et Mermaid en SVG :
  - fichiers `.puml`, `.pu`, `.plantuml`, `.mmd`, `.mermaid` → `<source>.svg`
    en conservant l'extension en affixe (`diagram.puml` → `diagram.puml.svg`) ;
  - blocs Markdown ```` ```puml ````, ```` ```plantuml ````, ```` ```mmd ````,
    ```` ```mermaid ```` → cache `<hash>.<affixe>.svg` et route
    `/diagram/<hash>.<affixe>.svg` ;
  - `viewBox`, `<title>` et `<desc>` ajoutés à la racine des SVG ;
  - génération à la demande pour `/asset`, et surveillance périodique des
    montages pour produire les SVG des sources ;
  - un outil absent ou une erreur laisse le bloc de code intact ;
- réglages `[diagrams]` (`enabled`, `plantuml`, `mermaid`, `timeout`,
  `puppeteer`).

### Modifié

- `page_html` reçoit la liste des montages ; le panneau de gauche affiche les
  dépôts quand il y en a plusieurs ;
- la restriction de racine est purement locale au client, les routes recevant
  des chemins absolus bornés par les montages ;
- 87 tests, dont la génération PlantUML/Mermaid avec des outils factices.

## [0.3.0] — 2026-10-27

### Ajouté

- **navigation SPA** : l'URL porte le document courant (`/docs/guide.md`) ;
  cliquer un lien `.md` ne recharge plus la page, `pushState` tient l'historique,
  et les boutons Retour/Avant fonctionnent ;
- les fragments (`#section`) sont conservés et le défilement a lieu après le
  rendu ;
- les liens relatifs sont résolus contre le **document courant** (`../`, `./`,
  espaces, `%20`) et les liens absolus contre la **racine de départ** ;
- les anciennes URL `/?f=/chemin/absolu` restent acceptées et sont normalisées
  vers l'URL propre ;
- test navigateur automatisé (Chrome DevTools) : clic sans rechargement et
  retour arrière ; 69 tests au total.

### Modifié

- les liens `.md` sont rendus en URL propre au lieu de `/?f=…` ; le serveur sert
  la SPA sur `/<chemin>.md` pour qu'un favori ou un lien partagé fonctionne.

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
