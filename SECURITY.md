# Sécurité

`docwatch` est un outil **local**, pas un serveur public.

## Modèle de sécurité

- Le serveur écoute uniquement sur `127.0.0.1`.
- Il refuse un en-tête `Host` qui ne désigne pas `localhost`, `127.0.0.1` ou
  `::1` (protection contre le rebinding DNS).
- Il vérifie l'origine des requêtes `POST`.
- Les chemins reçus sont résolus (liens symboliques compris) puis comparés à la
  racine : `../` et les liens sortants sont refusés.
- `/asset` ne sert qu'une liste fermée de types de fichiers. Un `.env`, une clé
  privée ou un binaire arbitraire n'est jamais téléchargeable.
- Les documents source ne sont ouverts qu'en lecture binaire.
- `pins.json` est écrit avec des permissions `0600`.

## Limites connues

- Le rendu conserve le HTML brut contenu dans le Markdown (`escape=False`).
  Un document hostile peut donc exécuter du JavaScript dans l'origine du
  serveur. Ne servez que des documents auxquels vous faites confiance.
- Il n'y a pas d'authentification : toute personne ayant accès à la machine
  peut lire les documents servis.

## Signaler une vulnérabilité

Utilisez l'onglet **Security → Report a vulnerability** du dépôt GitHub. Merci
de ne pas ouvrir d'issue publique avant qu'un correctif soit disponible.
