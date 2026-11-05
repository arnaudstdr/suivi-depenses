# Suivi de dépenses

Application web familiale de suivi des dépenses personnelles et des charges du foyer, avec un budget courses commun.

## Objectif produit

Au premier coup d'œil, l'utilisateur doit connaître son **budget personnel prévisionnel restant sur le mois**, après déduction des charges récurrentes et des dépenses ponctuelles prévues.

L'application distingue deux suivis :
- **Personnel** : solde du compte courant personnel saisi manuellement, dépenses personnelles et participation prévue au foyer.
- **Foyer** : charges communes réparties entre les membres et enveloppe courses commune de 490 € par mois.

Les achats enregistrés comme courses communes diminuent uniquement l'enveloppe courses. Ils ne diminuent pas une seconde fois le suivi personnel.

## Règles métier centrales

- Les charges peuvent être personnelles ou communes.
- Chaque charge commune possède une répartition en pourcentage (référence actuelle : 55 % pour l'utilisateur et 45 % pour l'autre membre).
- La participation personnelle aux charges communes est présentée sur le tableau de bord personnel sous **une seule ligne agrégée : « Participation au foyer »**.
- Les charges personnelles sont déduites individuellement du disponible prévisionnel.
- Le budget courses est une enveloppe commune de 490 €/mois, configurable et sans report.
- Une dépense de courses marquée « commune » diminue l'enveloppe courses, pas le suivi personnel.
- Le solde bancaire est saisi manuellement. Aucun revenu futur n'est ajouté au calcul du disponible prévisionnel.
- Les dépenses récurrentes non encore payées et les dépenses ponctuelles prévues sont déduites une seule fois.
- Les montants sont stockés en centimes entiers.

## Stack cible

- Backend : Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic.
- Frontend : React, TypeScript, Vite.
- Base : PostgreSQL.
- PWA : vite-plugin-pwa.
- Déploiement : Docker Compose sur Raspberry Pi 5.

## État du projet

La conception fonctionnelle et la maquette UX sont validées. Le dépôt entre en phase d'implémentation ; le frontend actuel reste une maquette avec données fictives et ne constitue pas encore une application connectée à un backend.

## Documentation

- [Spécifications fonctionnelles](docs/SPECIFICATIONS.md)
- [Modèle de données](docs/DATA_MODEL.md)
- [Diagramme entité-association](docs/ERD.md)
- [Contrat API](docs/API_SPEC.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Roadmap](docs/ROADMAP.md)
- [Design UX](docs/UX_DESIGN.md)

## Prochaine étape

Démarrer l'implémentation par la mise en place du socle backend et de son environnement de développement, en suivant `AGENTS.md` et `docs/ROADMAP.md`.
