# Roadmap — Suivi des dépenses

**Version :** 0.2  
**Statut :** Plan de réalisation aligné sur le modèle fonctionnel

## 1. Principes

- Finaliser les règles métier et la maquette avant le backend.
- Garder un monolithe modulaire.
- PostgreSQL est la source de vérité.
- Aucun code métier backend avant validation des parcours.
- Créer AGENTS.md uniquement lorsque les choix de conception et la maquette sont validés.

## 2. Phases

| Phase | Objectif | Livrable |
|---|---|---|
| 0 | Conception métier | Spécifications, modèle, ERD et API cohérents |
| 1 | Maquette UX | Frontend React navigable et responsive |
| 2 | Préparation dev | AGENTS.md, structure, CI, Docker |
| 3 | Socle sécurisé | Authentification, foyer, permissions |
| 4 | Suivi financier | Solde manuel, dépenses, charges, budget courses |
| 5 | Automatisation | Récurrences, échéances, répartitions |
| 6 | Fonctions annexes | Import/export, notifications |
| 7 | PWA | Installation et lecture hors ligne |
| 8 | Déploiement | Raspberry Pi 5, sauvegardes, supervision |

## 3. Phase 0 — Conception métier

- Valider le disponible prévisionnel personnel : solde manuel moins charges restantes.
- Valider la distinction Personnel / Commune / Courses communes.
- Valider l'agrégation des quotes-parts communes dans une seule ligne « Participation au foyer ».
- Valider les règles de répartition 55/45, modifiables.
- Aligner SPECIFICATIONS, DATA_MODEL, ERD, API_SPEC et UX_DESIGN.

Critères de sortie : aucun document ne décrit un solde joint, une synchronisation bancaire, l'ajout de revenus futurs au disponible ou une déduction des achats courses communes du budget personnel.

## 4. Phase 1 — Maquette frontend

Priorité des écrans :
1. Tableau de bord Personnel avec disponible prévisionnel.
2. Saisie manuelle du solde.
3. Ajout d'une dépense personnelle/commune.
4. Budget courses commun à 490 €.
5. Liste et gestion des charges récurrentes.
6. Vue Foyer et détail des répartitions.
7. Historique et paramètres.

Données fictives uniquement. Aucune API réelle. Vérifier desktop, mobile, thèmes clair et sombre.

## 5. Phase 2 — Préparation technique

Créer AGENTS.md après validation de la conception et de la maquette. Préparer l'environnement Python/Node, Docker Compose, PostgreSQL, Alembic, tests, CI et conventions de qualité.

## 6. Phase 3 — Socle sécurisé

Authentification par session cookie sécurisée, invitations à usage unique, gestion des utilisateurs et du foyer, contrôle d'accès personnel/commun, audit et protection CSRF.

## 7. Phase 4 — Suivi financier

Solde personnel manuel et historisé ; transactions personnelles et communes ; catégories ; charges récurrentes ; dépenses ponctuelles prévues ; budget courses mensuel ; calcul du disponible prévisionnel ; tests anti-double-comptage.

Critères de sortie :
- solde saisi et horodaté ;
- les charges futures et impayées sont déduites ;
- les dépenses payées ne sont pas déduites une seconde fois ;
- la participation commune est agrégée ;
- les courses communes ne diminuent que l'enveloppe courses.

## 8. Phase 5 — Récurrences et répartition

Génération idempotente des échéances, confirmation des montants variables, règles de répartition globales et spécifiques, calcul au centime et conservation de l'historique.

## 9. Phase 6 — Import/export et notifications

Import CSV/XLSX avec prévisualisation, export respectant les permissions, notifications in-app et push si supportées. Celery/Redis uniquement pour les tâches qui le nécessitent.

## 10. Phase 7 — PWA et sécurité

Installation PWA, cache des données autorisées, lecture hors ligne uniquement, purge du cache à la déconnexion et au changement de compte, tests de sécurité.

## 11. Phase 8 — Déploiement

Déploiement ARM64 sur Raspberry Pi 5 avec Caddy, FastAPI, PostgreSQL, frontend, worker/scheduler si nécessaires. Sauvegardes locales et distantes, Sentry filtré, tests de restauration.

## 12. Règle de changement

Toute modification métier doit être répercutée dans les documents concernés avant son implémentation. Chaque phase se termine par une démonstration et une validation explicite.
