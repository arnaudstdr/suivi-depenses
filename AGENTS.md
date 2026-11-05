# AGENTS.md

Ce fichier est le guide projet à la racine, au format Markdown natif reconnu automatiquement par OpenCode. Il est versionné pour être partagé avec toute personne travaillant sur le dépôt. Aucune configuration OpenCode supplémentaire n'est nécessaire pour le charger.

## Mission du projet

Construire **Suivi de dépenses**, une application web familiale pour deux membres d'un même foyer. L'objectif principal est de fournir un disponible personnel prévisionnel fiable, tout en séparant clairement les dépenses personnelles, les charges communes et le budget courses partagé.

Ce dépôt est en transition entre la conception validée et le début de l'implémentation. Le frontend existant est une maquette UX avec données fictives, pas une application métier connectée.

## Instructions de travail

- Répondre en français, sauf demande contraire.
- Avant toute modification fonctionnelle, lire les documents de référence pertinents dans `docs/`.
- Ne pas supposer qu'une fonctionnalité est implémentée parce qu'elle figure dans une spécification ou dans la maquette.
- Avancer par petites étapes cohérentes. Pour une demande large, proposer un plan court, puis implémenter une tranche verticale testable.
- Ne pas générer toute l'application en une seule passe. Ne pas ajouter de fonctionnalités hors périmètre sans demande ou justification explicite.
- Ne pas modifier les règles métier validées pour simplifier l'implémentation. En cas de contradiction documentaire ou d'ambiguïté, la signaler et demander une décision avant de coder la règle concernée.
- Ne pas réécrire les documents de conception au seul motif que l'implémentation choisit une organisation de code différente. Mettre à jour la documentation si une décision métier ou technique est réellement modifiée.
- Ne jamais annoncer qu'une commande, un test, un build, une migration ou une vérification a réussi sans l'avoir exécuté et observé.
- Ne pas écraser des changements utilisateur non commités. Examiner `git status` et le diff avant toute modification importante.
- Ne pas créer de commit ni pousser vers une branche distante sans demande explicite.

## Documents de référence

Lire les fichiers ci-dessous selon le sujet traité :

- `docs/SPECIFICATIONS.md` : règles fonctionnelles et critères d'acceptation. Référence métier principale.
- `docs/DATA_MODEL.md` : entités, contraintes, relations et règles de persistance.
- `docs/ERD.md` : relations entre entités.
- `docs/API_SPEC.md` : routes et contrats HTTP conceptuels.
- `docs/ARCHITECTURE.md` : architecture cible, responsabilités et exploitation.
- `docs/UX_DESIGN.md` : parcours et comportements attendus de l'interface.
- `docs/ROADMAP.md` : ordre de réalisation.

Les contrats et modèles sont des spécifications de conception, pas la preuve que les tables, routes ou écrans existent déjà. Si deux documents se contredisent, ne choisis pas silencieusement : expose le conflit et propose une correction cohérente.

## Stack et architecture cible

- Backend : Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic.
- Base de données : PostgreSQL.
- Frontend : React 18, TypeScript strict, Vite.
- PWA : vite-plugin-pwa, consultation hors ligne en lecture seule en V1.
- Conteneurs et déploiement : Docker Compose, Caddy.
- Tâches asynchrones : Celery et Redis uniquement pour les traitements réellement longs ou planifiés.
- Observabilité : Sentry côté backend, avec filtrage strict des données sensibles.
- Architecture : monolithe modulaire. Pas de microservices.

Respecter les versions et dépendances déjà présentes dans les fichiers de configuration. Ne pas inventer de commande de test, de lint ou de formatage : inspecter les scripts et la configuration du projet avant de les utiliser. Tant que le backend et ses fichiers de dépendances ne sont pas créés, ne prétendre pas qu'il existe une commande backend opérationnelle.

## Organisation du code visée

La structure exacte peut évoluer, mais conserver une séparation nette des responsabilités.

Backend cible :

- `backend/app/core/` : configuration, sécurité, dépendances transverses.
- `backend/app/api/` : assemblage des routes et dépendances HTTP.
- `backend/app/domains/<domain>/` : logique organisée par domaine métier.
- `backend/app/infrastructure/` : intégrations techniques.
- `backend/app/tasks/` : tâches asynchrones.
- `backend/migrations/` : migrations Alembic.
- `backend/tests/` : tests.

Domaines métier envisagés : auth, users, households, transactions, categories, budgets, recurring, balances, allocations, audit, notifications et imports/exports. Ne créer que les domaines nécessaires à la tranche en cours.

Frontend cible :

- `frontend/src/app/` : initialisation et composition de l'application.
- `frontend/src/features/` : fonctionnalités métier.
- `frontend/src/components/` : composants UI génériques.
- `frontend/src/lib/` : client API, formatage et utilitaires transverses.
- `frontend/src/hooks/` : hooks partagés.
- `frontend/src/styles/` : styles globaux et tokens.

Le frontend actuel est une maquette dans `frontend/src/App.tsx` et `frontend/src/styles.css`. Préserver son rendu et ses parcours validés pendant la mise en place de l'architecture. Extraire progressivement les composants et fonctionnalités, sans régression visuelle inutile.

## Règles métier non négociables

### Périmètres et comptes

- V1 : deux comptes distincts rattachés à un seul foyer, accès par invitation uniquement.
- Les données personnelles ne sont accessibles qu'à leur propriétaire.
- Les données communes sont accessibles aux membres du foyer.
- Le contexte Personnel est le contexte par défaut.
- Aucun compte bancaire n'est synchronisé. Le seul solde suivi est le solde du compte courant personnel, saisi manuellement.
- Le solde du compte joint n'est pas suivi en V1.

### Montants et dates

- Stocker tous les montants monétaires en centimes entiers, jamais en nombres flottants.
- Utiliser des types entiers adaptés en base, avec contraintes de positivité lorsque nécessaire.
- Les dates métier sont des dates sans heure. Les instants réels sont des horodatages avec fuseau.
- Fuseau métier du foyer : `Europe/Paris`. Stocker les instants en UTC et convertir à l'affichage.
- Utiliser des calculs déterministes et des règles d'arrondi explicites. Tester les répartitions et les arrondis au centime.

### Disponible prévisionnel et instantané de solde

Le dernier solde saisi est un instantané bancaire horodaté, pas un solde recalculé automatiquement.

- Une sortie déjà passée avant ou à `recorded_at` est réputée incluse dans le solde saisi : ne pas la déduire une seconde fois.
- Une sortie payée après `recorded_at` reste déduite jusqu'à la prochaine saisie du solde.
- Pour une transaction payée, comparer son horodatage réel `paid_at` à `recorded_at`. Ne pas utiliser seulement `transaction_date`, qui est une date métier.
- Le statut payé/transféré et l'inclusion dans le dernier instantané bancaire sont deux notions différentes.
- Pointer une charge ou une participation ne doit donc pas, à lui seul, faire disparaître la déduction.
- Une nouvelle saisie du solde après le paiement intègre la sortie dans le point de départ et supprime la déduction correspondante, sans double comptage.
- Les engagements non payés restant dus et les dépenses ponctuelles personnelles prévues/engagées sont déduits.
- Une dépense annulée cesse d'être déduite.
- Aucun revenu futur n'est ajouté au disponible.

Créer des tests unitaires dédiés à ces cas, y compris les paiements juste avant, exactement à et juste après l'instantané.

### Participation au foyer et charges communes

- La ligne « Participation au foyer » agrège la quote-part personnelle des charges communes hors courses et la contribution au budget courses.
- La contribution courses est incluse dans la participation, elle ne doit pas être ajoutée une seconde fois.
- Répartition initiale : 55 % / 45 %, modifiable globalement et par charge. La somme des parts doit faire exactement 100 %.
- Le budget courses initial est de 490 € par mois, configurable, sans report du reliquat.
- Les achats de courses communes diminuent uniquement l'enveloppe courses, jamais le disponible personnel.
- Le virement de participation est pointé explicitement, comme une échéance récurrente : confirmer la date réelle et le montant réellement transféré.
- Le pointage de participation doit être idempotent et historisé. Une correction est explicite et auditée.
- Un virement postérieur au dernier instantané reste déduit jusqu'à une nouvelle saisie du solde.

### Charges récurrentes

- Générer les occurrences de manière idempotente.
- Une occurrence est suivie individuellement et peut être `pending`, `confirmed`, `paid` ou `skipped`.
- Le pointage confirme la date réelle et le montant réellement payé. Le montant attendu est prérempli pour une charge fixe et reste modifiable. Le montant réel est obligatoire pour une charge variable.
- Le pointage crée ou associe une transaction réelle dans la même transaction SQL, sans doublon.
- Une occurrence déjà payée ne peut être repointée qu'au moyen d'une correction explicite et auditée.
- Le montant payé après le dernier instantané reste déduit jusqu'à la prochaine saisie du solde.

### Dépenses, remboursements et budget courses

- Une dépense personnelle affecte le disponible personnel.
- Une dépense commune hors courses est répartie et agrégée dans la participation au foyer.
- Une dépense commune de courses consomme uniquement le budget courses.
- Un remboursement est une transaction distincte liée à la dépense d'origine. Ne pas écraser la dépense initiale.
- Les historiques financiers ne doivent pas être modifiés silencieusement.

## Backend : conventions de conception

- Garder les règles métier dans des services indépendants de FastAPI.
- Les routers gèrent HTTP, authentification, validation et codes de réponse, pas les calculs métier.
- Les schémas Pydantic définissent les contrats d'entrée/sortie ; les modèles SQLAlchemy définissent la persistance.
- Les repositories encapsulent les requêtes. Ils ne font pas de `commit()` implicite.
- Les services orchestrent les opérations et contrôlent les transactions SQL.
- Toute opération multi-étapes financière doit être atomique.
- Utiliser des contraintes PostgreSQL (FK, UNIQUE, CHECK) en complément des validations applicatives.
- Utiliser Alembic pour toutes les évolutions du schéma. Ne jamais modifier manuellement un schéma déjà migré en production.
- Déduire l'utilisateur connecté de la session côté serveur. Ne jamais faire confiance à un `user_id` ou `household_id` fourni par le client.
- Vérifier les autorisations au niveau service/repository pour chaque ressource personnelle ou du foyer.
- Prévoir pagination, filtres bornés et erreurs API homogènes selon `docs/API_SPEC.md`.
- Rendre idempotentes les opérations sensibles pouvant être répétées par le client ou par un worker.
- Injecter les dépendances importantes (session DB, horloge, repositories) pour faciliter les tests.

## Sécurité et confidentialité

- Mots de passe hachés avec Argon2id.
- Sessions opaques révocables, cookie `HttpOnly`, `Secure`, `SameSite` adapté.
- Protection CSRF pour les mutations.
- Invitations à usage unique, avec expiration et jeton stocké haché.
- Pas de secret, mot de passe, token, cookie ou clé dans le dépôt.
- Fournir un `.env.example` avec noms et exemples non sensibles uniquement.
- Ne jamais journaliser de mot de passe, token, cookie, données financières détaillées ou données privées inutiles.
- Configurer Sentry avec suppression des cookies, en-têtes sensibles, données financières et informations personnelles non nécessaires.
- Les réponses financières et caches PWA sont privés, jamais servis depuis un cache public/partagé.
- À la déconnexion ou au changement de compte, vider les données privées mises en cache.
- Les permissions doivent être vérifiées côté backend, jamais uniquement dans l'interface.

## Frontend : conventions

- TypeScript strict. Éviter `any`; typer les réponses API et les états.
- Organiser le code par fonctionnalité métier, sans créer de couches abstraites prématurées.
- Centraliser le client HTTP, la gestion des erreurs et le formatage des montants/dates.
- Les montants transitent en centimes entiers. Convertir en euros uniquement dans les fonctions de présentation et de saisie.
- Ne pas dupliquer dans le frontend les calculs financiers qui font autorité : le backend fournit le disponible prévisionnel.
- Gérer explicitement les états de chargement, erreur, vide, succès et mode hors ligne.
- En V1, le mode hors ligne est en lecture seule. Désactiver les mutations hors ligne, ne pas mettre en place de file d'écritures différées.
- Respecter l'accessibilité : labels, navigation clavier, focus visible, boutons avec libellés explicites et contrastes suffisants.
- Préserver les parcours et hiérarchies validés dans `docs/UX_DESIGN.md`.

## Tests et vérifications

- Backend : pytest, tests unitaires des règles métier et tests d'intégration avec PostgreSQL.
- Frontend : Vitest et Testing Library pour logique et composants ; Playwright pour les parcours critiques lorsque la configuration existe.
- Couvrir au minimum : permissions, calcul du disponible, instantané de solde, arrondis 55/45, contribution au foyer, pointage idempotent, paiements récurrents, budget courses, remboursements et absence de double comptage.
- Tester les migrations sur une base vierge et sur une base ayant la migration précédente.
- Après chaque tranche, lancer les contrôles pertinents disponibles dans le dépôt. Commencer par les tests ciblés, puis les vérifications globales.
- Si un contrôle ne peut pas être exécuté (service PostgreSQL absent, dépendance manquante, script inexistant), le signaler clairement et ne pas le présenter comme réussi.
- Ne pas ajouter de dépendance de test ou de qualité sans vérifier qu'elle est justifiée et cohérente avec le projet.

## Workflow recommandé pour chaque tâche

1. Lire les documents métier/techniques concernés et inspecter le code existant.
2. Vérifier `git status` et les changements déjà présents.
3. Décrire brièvement l'approche si la tâche touche plusieurs couches ou une règle financière.
4. Implémenter une tranche limitée, avec migration si le schéma évolue.
5. Ajouter ou adapter les tests au même moment que le code.
6. Exécuter les contrôles ciblés puis les contrôles globaux disponibles.
7. Relire le diff, vérifier qu'aucun secret ou fichier généré n'est inclus.
8. Résumer les fichiers modifiés, les tests réellement exécutés et les points restant à faire.

## État actuel du dépôt

- Les documents de conception sont présents dans `docs/`.
- Le frontend contient une maquette React/Vite avec données fictives.
- Le backend FastAPI/SQLAlchemy/Alembic est présent dans `backend/`, avec les tables d'identité, de sécurité et le socle financier (`personal_balance_entries`, `categories`, `transactions`, `budgets`, `budget_periods`).
- Les migrations Alembic, les tests backend, Docker Compose pour PostgreSQL, le Dockerfile API et la CI GitHub Actions sont présents.
- Le socle sécurisé est implémenté : bootstrap CLI, sessions opaques, cookies sécurisés, CSRF, invitations à usage unique, contrôle d'accès propriétaire/membre et audit.
- Les Phases 4 à 7 sont implémentées : solde, catégories, transactions, remboursements, budget courses, dépenses prévues, récurrences, génération automatique et idempotente des occurrences, confirmation des montants variables, skip motivé, corrections auditées, répartition, participation, contribution au foyer, historique des contributions, calcul du disponible prévisionnel, dashboard personnel, export CSV/XLSX, import avec prévisualisation, notifications in-app, frontend connecté, PWA installable, cache privé et lecture hors ligne en lecture seule.
- Le frontend possède les scripts npm `dev`, `build`, `preview`, `typecheck` et `test`; il n'existe pas encore de script `lint` déclaré dans son `package.json`.
- Le frontend est conteneurisé dans une image Nginx qui sert le build React et proxifie `/api` et `/health` vers FastAPI. L'accès distant du Raspberry Pi passe par Tailscale Serve, sans Caddy dans le premier déploiement.
- Les commandes backend réellement disponibles sont documentées dans `backend/README.md` et dans le `Makefile`.
- La Phase 8 est en cours : le déploiement Docker ARM64 et l'accès Tailscale sont en place ; restent les sauvegardes, Sentry filtré et les tests de restauration.

Cette section doit être mise à jour lorsque l'architecture réelle du dépôt évolue. Ne pas créer des fichiers ou commandes manquants en supposant qu'ils existent.
