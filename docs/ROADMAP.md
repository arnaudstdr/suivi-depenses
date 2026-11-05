# Roadmap — Suivi des dépenses

**Version :** 0.1  
**Statut :** Proposition de plan de réalisation  
**Principe :** valider chaque phase avant de passer à la suivante. La maquette frontend précède le développement du backend.

## 1. Principes de conduite

- Développer un monolithe modulaire, sans microservices.
- Garder PostgreSQL comme source de vérité.
- Livrer des incréments fonctionnels testables.
- Ne pas commencer le backend avant validation de la maquette et des parcours UX.
- Ne pas créer `AGENTS.md` avant validation des décisions de conception.
- Mettre à jour les spécifications, le modèle de données et l'API lorsqu'une décision impacte le contrat.

## 2. Vue synthétique des phases

| Phase | Objectif | Livrable principal | Validation attendue |
|---|---|---|---|
| 0 | Finaliser la conception | Documents cohérents | Arbitrages métier et techniques validés |
| 1 | Concevoir l'expérience | UX et maquette React navigable | Parcours et écrans validés |
| 2 | Préparer le cadre de développement | AGENTS.md, structure, CI, Docker | Environnement reproductible |
| 3 | Construire le socle backend | Auth, foyers, permissions, migrations | Deux comptes isolés et associés |
| 4 | Construire les fonctions financières | Transactions, catégories, revenus, budgets | Dépenses et budgets cohérents |
| 5 | Construire les récurrences et allocations | Prévisions, règles, calculs et snapshots | Calcul mensuel reproductible |
| 6 | Construire imports, exports et notifications | Traitements asynchrones | Flux vérifiés et idempotents |
| 7 | Finaliser PWA et sécurité | Cache privé, offline read-only, durcissement | Tests de sécurité et hors ligne |
| 8 | Déployer sur Raspberry Pi 5 | Application auto-hébergée | Déploiement restaurable et supervisé |

## 3. Phase 0 — Finalisation de la conception

### Travaux

- Relire les spécifications fonctionnelles, le modèle de données, l'ERD, l'API et l'architecture ensemble.
- Corriger les incohérences entre documents, notamment le modèle des prévisions manuelles et les sources de charges des snapshots.
- Clarifier l'éligibilité des revenus (notamment CAF) dans la base de répartition.
- Définir la gestion des revenus incomplets ou variables et des périodes sans revenu.
- Définir le traitement d'un remboursement après clôture d'une période.
- Vérifier les endpoints d'invitation et de correction d'un calcul définitif.
- Confirmer les règles d'accès et les champs exposés pour chaque combinaison de confidentialité.
- Créer un glossaire métier partagé.

### Livrables

- Spécifications fonctionnelles consolidées.
- Modèle de données et ERD alignés.
- Contrat API aligné sur le modèle.
- Architecture technique validée.
- Liste des décisions restantes avec responsable et statut.

### Critères de sortie

- Aucun désaccord entre les documents sur les concepts principaux.
- Chaque donnée financière a un propriétaire, un périmètre de visibilité et une règle de calcul.
- Les cas de correction, d'historique et de remboursement sont explicitement décrits.

## 4. Phase 1 — UX et maquette frontend

**Cette phase précède tout développement fonctionnel backend.** La maquette utilise des données fictives, sans API réelle.

### Travaux

- Définir l'identité visuelle, la navigation et les composants.
- Définir les vues desktop et mobile.
- Réaliser les écrans principaux :
  - connexion et acceptation d'invitation ;
  - tableau de bord du foyer ;
  - tableau de bord personnel ;
  - liste et détail des transactions ;
  - création et modification d'une dépense ;
  - budget alimentaire et budgets personnels ;
  - dépenses récurrentes ;
  - revenus de référence ;
  - répartition mensuelle ;
  - historique ;
  - paramètres et confidentialité.
- Prévoir les états vides, erreurs, chargement, confirmation et absence de réseau.
- Rendre les parcours navigables avec un jeu de données fictif cohérent.
- Vérifier l'accessibilité de base : navigation clavier, labels, contrastes et tailles tactiles.

### Livrables

- `docs/UX_DESIGN.md`.
- Maquette React/TypeScript responsive.
- Jeu de données fictif versionné.
- Parcours de démonstration navigables.

### Critères de sortie

- Les deux tableaux de bord sont compréhensibles.
- Un utilisateur peut parcourir les flux principaux sans écran bloquant.
- Les informations privées et partagées sont visuellement différenciées.
- La maquette est validée avant le début du backend.

## 5. Phase 2 — Préparation du développement

### Travaux

- Rédiger `AGENTS.md` à partir des décisions validées.
- Créer l'arborescence backend et frontend.
- Configurer les environnements Python et Node.
- Configurer Docker Compose pour le développement.
- Configurer PostgreSQL et Alembic.
- Configurer les outils de qualité et les tests.
- Créer la CI GitHub Actions.
- Préparer les variables d'environnement et les secrets de développement.

### Livrables

- `AGENTS.md`.
- Structure initiale du dépôt.
- Environnement local reproductible.
- Pipeline CI vert.

### Critères de sortie

- Un nouveau clone peut être démarré avec la procédure documentée.
- Les tests et contrôles qualité s'exécutent en local et en CI.
- Aucun secret n'est commité.

## 6. Phase 3 — Socle backend et sécurité

### Travaux

- Configuration FastAPI et gestion centralisée des erreurs.
- Connexion, déconnexion, session sécurisée et protection CSRF.
- Invitations à usage unique et acceptation.
- Gestion des utilisateurs, foyers et membres.
- Permissions personnelles et partagées.
- Préférences de confidentialité et filtrage des champs de réponse.
- Journal d'audit pour les opérations sensibles.
- Migrations initiales.

### Critères de sortie

- Deux utilisateurs peuvent rejoindre le même foyer par invitation.
- Un utilisateur ne peut pas consulter les données personnelles de l'autre sans autorisation.
- Les données communes sont accessibles selon les règles du foyer.
- Les tests d'authentification, de CSRF et d'autorisation passent.

## 7. Phase 4 — Fonctions financières de base

### Travaux

- Catégories.
- Création, consultation, modification et suppression autorisée des transactions.
- Dépenses personnelles et partagées.
- Remboursements partiels liés à la dépense d'origine.
- Revenus de référence séparés des transactions de revenu.
- Budgets et périodes budgétaires.
- Budget alimentaire partagé avec une transaction enregistrée une seule fois.
- Historique et filtres.

### Critères de sortie

- Les montants sont stockés en centimes entiers.
- Les agrégations ne comptent aucune dépense deux fois.
- Les remboursements ne réécrivent pas la transaction d'origine.
- Les règles de visibilité sont appliquées aux listes, détails et agrégats.

## 8. Phase 5 — Récurrences, prévisions et répartitions

### Travaux

- Définitions de dépenses récurrentes.
- Génération idempotente des occurrences.
- Confirmation obligatoire du montant pour les récurrences variables.
- Ressources de prévision manuelle modifiables et supprimables avant finalisation.
- Règles de répartition et priorité des règles.
- Calcul proportionnel et règles personnalisées par charge.
- Gestion déterministe des arrondis au centime.
- Finalisation mensuelle atomique.
- Snapshots des revenus, charges et parts.
- Correction explicite avec motif et audit.

### Critères de sortie

- Un même calcul avec les mêmes entrées produit le même résultat.
- Une occurrence ne peut pas être générée deux fois.
- Une période possède une seule version définitive courante.
- Une correction est explicite, autorisée et auditée.
- Les snapshots historiques ne changent pas silencieusement.

## 9. Phase 6 — Imports, exports et notifications

### Travaux

- Import CSV/XLSX avec prévisualisation et validation explicite.
- Détection des doublons et idempotence.
- Export des données autorisées.
- Notifications in-app.
- Notifications push si supportées et autorisées.
- Celery et Redis pour les traitements longs et planifiés.
- Suivi de statut et gestion des échecs.

### Critères de sortie

- Un import n'écrit rien avant validation explicite.
- Les retries ne créent pas de doublons.
- Les exports respectent les permissions et paramètres de confidentialité.
- Une panne de notification ne bloque aucune opération financière.

## 10. Phase 7 — PWA et sécurité finale

### Travaux

- Manifest et installation PWA.
- Cache des ressources statiques.
- Cache privé des données déjà synchronisées.
- Consultation hors ligne en lecture seule.
- Purge du cache à la déconnexion et au changement de compte.
- Tests sur Safari iOS et navigateurs Chromium.
- Vérification des en-têtes HTTP, cookies, CSRF et contrôle d'accès.
- Vérification des dépendances et des journaux pour éviter les fuites de données.

### Critères de sortie

- Les données déjà consultées restent accessibles hors ligne.
- Aucune écriture n'est possible hors ligne.
- Aucun cache financier n'est partagé entre utilisateurs.
- Les données locales sont supprimées à la déconnexion.
- Les tests de sécurité critiques passent.

## 11. Phase 8 — Déploiement et exploitation sur Raspberry Pi 5

### Travaux

- Préparer les images Docker ARM64.
- Déployer Caddy, frontend, API, PostgreSQL, Redis, worker et scheduler.
- Configurer le domaine ou l'accès réseau retenu et HTTPS.
- Configurer Sentry avec filtrage des données sensibles.
- Configurer les sauvegardes PostgreSQL et fichiers sur le second disque USB.
- Configurer Restic + rclone vers kDrive via WebDAV.
- Mettre en place les alertes d'échec et d'ancienneté des sauvegardes.
- Tester une restauration complète sur environnement isolé.
- Documenter mise à jour, retour arrière et restauration.

### Critères de sortie

- Déploiement reproductible depuis le dépôt.
- Application accessible en HTTPS.
- Services internes non exposés directement à Internet.
- Sauvegarde locale et distante validées par restauration.
- Objectif de perte de données (RPO) maximal de 24 heures surveillé par alerte.
- Procédure de restauration documentée et testée.

## 12. Ordre de priorité MVP

Le MVP doit d'abord permettre de gérer correctement le foyer et les dépenses, avant d'ajouter les automatisations.

1. Authentification, invitations et permissions.
2. Foyer et comptes personnels.
3. Transactions, catégories et remboursements.
4. Budget alimentaire et budgets simples.
5. Revenus de référence et confidentialité.
6. Récurrences.
7. Répartition mensuelle et historique.
8. Import/export.
9. Notifications et push.
10. Consultation PWA hors ligne.

Les tâches de sécurité, tests et sauvegarde ne sont pas repoussées à la fin : elles sont introduites dès les phases correspondantes.

## 13. Gestion des changements

Toute évolution métier qui modifie un montant, une règle de répartition, une visibilité ou un historique doit mettre à jour les documents concernés avant implémentation.

Chaque phase se termine par :
- une démonstration ;
- une revue des critères de sortie ;
- une mise à jour documentaire ;
- une décision explicite de poursuivre ou de corriger.

---

**Fin — ROADMAP.md v0.1**
