# Suivi de dépenses

Application web familiale de suivi des finances personnelles et du budget du foyer.

## Objectifs
- Suivre les revenus et dépenses personnels.
- Partager les dépenses communes du foyer.
- Suivre une enveloppe mensuelle de courses commune.
- Gérer les dépenses récurrentes et leurs échéances.
- Répartir les charges selon les revenus ou des règles personnalisées.
- Consulter l'historique et exporter les données.

## Stack cible
- Backend : Python 3.12, FastAPI, Pydantic, SQLAlchemy 2, Alembic.
- Frontend : React, TypeScript, Vite, Tailwind CSS, shadcn/ui.
- Base de données : PostgreSQL.
- PWA : vite-plugin-pwa.
- Environnement : Docker Compose.

Ces choix constituent la stack cible ; aucun code applicatif n'a encore été implémenté.

## État du projet
Le projet est en phase de conception. Aucune implémentation backend ou frontend ne doit commencer avant validation des spécifications, du modèle de données, des contrats API et de la maquette UX.

## Documentation
- [Spécifications fonctionnelles](docs/SPECIFICATIONS.md)
- [Modèle de données](docs/DATA_MODEL.md)

## Principes
- Séparation des données personnelles et communes.
- Autorisations appliquées côté backend.
- Montants stockés en centimes entiers.
- Résultats historiques de répartition conservés.
- Budgets mensuels sans report.
- Remboursements enregistrés comme transactions distinctes.

## Prochaines étapes
1. Finaliser le diagramme entité-relation (ERD).
2. Définir les contrats de l'API REST.
3. Définir l'architecture technique détaillée.
4. Réaliser et valider la maquette React responsive/PWA.
5. Commencer le développement après validation.
