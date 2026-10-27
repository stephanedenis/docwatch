# mdserve

**Un lecteur Markdown local, en lecture seule : arborescence, rendu, rechargement
automatique, épingles — dans le navigateur.**

[![CI](https://github.com/stephanedenis/mdserve/actions/workflows/ci.yml/badge.svg)](https://github.com/stephanedenis/mdserve/actions/workflows/ci.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![Licence MIT](https://img.shields.io/badge/licence-MIT-green.svg)](LICENSE)

Lire vingt fiches Markdown dans un terminal n'est pas lire. `mdserve` rend un
arbre de documents dans le navigateur, affiche les tableaux, les schémas SVG et
les images, recharge la page quand un fichier change, et garde les dossiers
importants en accès rapide.

```
┌──────────────────────┬─────────────────────────────────────────────┐
│ 🗂 Arborescence       │  # Titre du document                        │
│  ▸ docs/             │                                             │
│  ▸ reports/          │  Un tableau, des liens, des images…         │
│  ▸ journal/          │                                             │
│  ☆  fiches épinglées │  rendu par le navigateur, pas dans le terminal│
└──────────────────────┴─────────────────────────────────────────────┘
```

## Ce qu'il fait

| | |
|---|---|
| **Arborescence** | chargée à la demande, un niveau à la fois ; jamais un scan complet du disque |
| **Rendu** | Markdown → HTML (tableaux, notes de bas de page, HTML brut), dans le navigateur |
| **Rechargement** | le navigateur interroge `/stat` toutes les 3 s ; seuls les changements sont signalés, la position de lecture est conservée |
| **Épingles** | dossiers **et** documents, stockés dans `~/.config/mdserve/pins.json` |
| **Filtre temporel** | uniquement ce qui a bougé depuis 1 h, 24 h, 7 j ou N heures |
| **Images et annexes** | SVG, PNG, PDF, CSS, polices… servis avec leur type MIME, résolus contre le dossier du document |
| **Liens entre documents** | un lien vers un `.md` ouvre le document dans le lecteur, pas un 404 |
| **Lecture seule** | aucun fichier source n'est ouvert en écriture ; seules les épingles s'écrivent |
| **Local par construction** | le serveur n'écoute que sur `127.0.0.1` et vérifie l'en-tête `Host` |

## Installation

```bash
pipx install "git+https://github.com/stephanedenis/mdserve.git"
```

Ou, pour développer :

```bash
git clone https://github.com/stephanedenis/mdserve.git
cd mdserve
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

> La distribution s'appelle `mdserve-local` (le nom `mdserve` est déjà pris sur
> PyPI) ; les commandes installées sont `mdserve` et `mdopen`.

## Utilisation

```bash
mdserve ~/Documents/docs                 # sert le dossier, ouvre le navigateur
mdserve ~/Documents/docs --port 8787     # un autre port
mdserve ~/Documents/docs --no-browser    # pour un service
mdserve                                 # sert le répertoire courant

mdopen ~/Documents/docs/guide.md         # démarre le serveur si besoin et ouvre le document
mdopen a.md b.md -r ~/Documents/docs     # plusieurs documents, racine explicite
```

### Épingles en ligne de commande

```bash
mdserve ~/Documents/docs --pin guide                  # épingle un dossier (relatif à la racine)
mdserve ~/Documents/docs --pin-file guide/intro.md    # épingle un document
mdserve ~/Documents/docs --unpin guide                # retire un dossier (et ses documents)
mdserve --list-pins                                # liste tout
```

### Options

| option | effet |
|---|---|
| `--port N` | port d'écoute (défaut `8770` ; `0` choisit un port libre) |
| `--no-browser` | n'ouvre pas de navigateur au démarrage |
| `--config-dir DIR` | remplace `$XDG_CONFIG_HOME/mdserve` |
| `--cache-dir DIR` | remplace `$XDG_CACHE_HOME/mdserve` |
| `--pin`, `--unpin`, `--pin-file`, `--unpin-file`, `--list-pins` | gestion des épingles, sans lancer le serveur |
| `--version` | version |

## Comment ça marche

Le serveur est un `ThreadingHTTPServer` de la bibliothèque standard. Les routes
sont volontairement peu nombreuses :

| route | rôle |
|---|---|
| `GET /` | la page (arbre + lecteur) |
| `GET /tree?path=…` | un niveau d'arborescence |
| `GET /render?path=…&force=0` | un document Markdown rendu en HTML |
| `GET /stat?path=…&token=…&dir_token=…` | comparaison de fraîcheur, sans rendu |
| `GET /asset?path=…` | une image, un PDF, une police — type MIME vérifié |
| `GET /pins` | les épingles visibles dans la racine courante |
| `GET /recent?heures=24` | les documents modifiés récemment |
| `GET /root`, `GET /status` | racine courante, périmètre, port |
| `POST /pins` | ajouter, retirer ou basculer une épingle |
| `POST /root` | restreindre la vue à un sous-dossier |
| `POST /changed` | comparaison groupée de dates (lecture seule) |

Le cache de rendu est un fichier HTML par `(chemin, mtime, taille)` dans
`$XDG_CACHE_HOME/mdserve`. Le rendu utilise [mistune](https://mistune.lepture.com/)
et retombe sur `markdown-it-py` ou `markdown` s'il est absent.

## Sécurité

`mdserve` est un outil **local**, pas un serveur public :

- écoute uniquement sur `127.0.0.1` ;
- refuse un en-tête `Host` qui ne désigne pas `localhost` / `127.0.0.1`
  (protection contre le rebinding DNS) ;
- vérifie l'origine des `POST` ;
- résout les liens symboliques avant de comparer les chemins : impossible de
  sortir de la racine par `../` ou par un lien ;
- ne sert par `/asset` qu'une liste fermée de types de fichiers (images,
  polices, CSS/JS, PDF, textes) — un `.env` ou une clé privée n'est jamais
  téléchargeable ;
- n'ouvre les fichiers source qu'en lecture binaire.

Le rendu HTML conserve le HTML brut du Markdown (`escape=False`) : ne servez
que des documents auxquels vous faites confiance.

## Service systemd (utilisateur)

```ini
# ~/.config/systemd/user/mdserve.service
[Unit]
Description=mdserve — lecteur Markdown local
After=default.target

[Service]
ExecStart=%h/.local/bin/mdserve %h/Documents/docs --port 8771 --no-browser
Restart=always
RestartSec=3

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now mdserve.service
```

## Développement

```bash
pip install -e ".[dev]"
pytest
ruff check .
```

Les tests couvrent le rendu, le cache, la réécriture des liens et des images,
les épingles, la traversée de chemins, les routes HTTP et les garde-fous
(`Host`, `Origin`, méthodes refusées).

## Origine

`mdserve` est extrait de l'outillage de documentation de
[Drave](https://github.com/stephanedenis/drave), où il servait à parcourir
`docs/`, `reports/` et `journal/`. Il vit désormais sa propre vie : le code ne
dépend d'aucun chemin ni d'aucune convention de ce projet.

## Licence

[MIT](LICENSE).
