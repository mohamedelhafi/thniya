# Sécurité

Merci de **ne pas ouvrir de ticket public** pour une faille de sécurité. Signalez-la en privé depuis l'onglet
**Security → Report a vulnerability** de ce dépôt, avec les étapes pour la reproduire.

Rappels pour déployer le projet :

- ne publiez jamais `infra/.env` ; remplacez toutes les valeurs `change-me` par des secrets aléatoires ;
- n'exposez jamais le back-office Directus ni la base de données sur Internet ;
- `infra/compose.local.yml` est réservé au développement.
