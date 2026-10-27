# Contribuer

Merci de vouloir améliorer `mdserve`.

## Mise en place

```bash
git clone https://github.com/stephanedenis/mdserve.git
cd mdserve
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

## Avant une proposition

```bash
pytest
ruff check .
```

Les deux doivent passer. La CI exécute la même chose sur Python 3.9 à 3.13.

## Règles du projet

- **Lecture seule** : aucun chemin de code ne doit ouvrir un document source en
  écriture. Le seul fichier écrit est `pins.json`.
- **Local par construction** : le serveur n'écoute que sur `127.0.0.1`. Ne pas
  ajouter d'option d'écoute réseau sans une discussion préalable.
- **Toute route qui reçoit un chemin** passe par `safe_path` ou `safe_bounded`.
- **Un correctif de sécurité** vient avec un test qui échoue avant et passe après.

## Signaler un problème

Pour une vulnérabilité, n'ouvrez pas d'issue publique : utilisez
l'onglet **Security → Report a vulnerability** du dépôt GitHub.
