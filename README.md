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

La conception fonctionnelle et la maquette UX sont validées. Le socle backend est en place : FastAPI, SQLAlchemy 2, Alembic, PostgreSQL, endpoints de santé, tests et CI. Le frontend React/Vite est connecté à l'API, installable en PWA et consultable hors ligne en lecture seule.

Le socle sécurisé est également en place : bootstrap du foyer par CLI, sessions opaques, cookies sécurisés, protection CSRF, invitations à usage unique, contrôle d'accès propriétaire/membre et journal d'audit.

Les Phases 4 à 7 sont implémentées : solde personnel historisé, catégories, transactions personnelles/communes/courses, remboursements liés, budget courses mensuel de 490 € sans report, dépenses ponctuelles prévues/engagées, charges récurrentes, génération idempotente et automatique des occurrences, confirmation des montants variables, skip motivé, pointage avec transaction liée, corrections explicites et auditées, répartition 55/45 et règles spécifiques, participation au foyer, contribution au budget courses, calcul du disponible prévisionnel, tableau de bord personnel, historique des contributions, export CSV/XLSX, import avec prévisualisation, notifications in-app, frontend connecté, PWA installable, cache privé et lecture hors ligne en lecture seule.

## Documentation

- [Spécifications fonctionnelles](docs/SPECIFICATIONS.md)
- [Modèle de données](docs/DATA_MODEL.md)
- [Diagramme entité-association](docs/ERD.md)
- [Contrat API](docs/API_SPEC.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Roadmap](docs/ROADMAP.md)
- [Design UX](docs/UX_DESIGN.md)

## Déploiement Docker

Depuis la racine du dépôt :

```bash
make build   # construit les images de l'API et du frontend
make up      # build, migrations Alembic, PostgreSQL, API et frontend
make down    # arrête les conteneurs sans supprimer le volume PostgreSQL
```

Le frontend est servi par Nginx, qui proxifie `/api` vers FastAPI. Sur le
Raspberry Pi, copier `.env.example` vers `.env`, puis définir au minimum
`APP_ENV=prod` et un `POSTGRES_PASSWORD` fort. Le volume PostgreSQL est conservé
par `make down` ; les données ne sont pas supprimées.

### Accès via Tailscale

Caddy n'est pas utilisé dans ce premier déploiement. Le frontend écoute
uniquement sur `127.0.0.1:8080` et Tailscale Serve fournit le HTTPS et l'accès
au tailnet :

```bash
sudo tailscale serve --bg 8080
sudo tailscale serve status
```

L'application est ensuite accessible à l'adresse HTTPS du Raspberry Pi sur le
tailnet (`https://<machine>.<tailnet>.ts.net`). Pour révoquer l'exposition :

```bash
sudo tailscale serve reset
```

Pour un accès public, `tailscale funnel` peut être utilisé à la place de
`tailscale serve`, mais ce n'est pas le mode retenu par défaut.

## Prochaine étape

Poursuivre la Phase 8 : le déploiement Docker ARM64 et l'accès Tailscale sont en place ; restent les sauvegardes, Sentry filtré et les tests de restauration. Les commandes backend, le bootstrap et le parcours d'invitation sont documentés dans [`backend/README.md`](backend/README.md), et les commandes frontend dans [`frontend/README.md`](frontend/README.md).
