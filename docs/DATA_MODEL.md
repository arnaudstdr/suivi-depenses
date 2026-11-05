# Modèle de données — Budget familial

**Version :** 0.2  
**Statut :** Proposition consolidée, à valider techniquement  
**Backend cible :** Python 3.12 / FastAPI  
**ORM :** SQLAlchemy 2  
**Base :** PostgreSQL  
**Migrations :** Alembic

> Ce document décrit le modèle conceptuel et logique. Il ne constitue pas encore un schéma SQL prêt pour migration. Les contraintes, snapshots et règles d'accès devront être vérifiés lors de la conception de l'ERD et des contrats API.

# 1. Principes

- Identifiants UUID.
- Montants en centimes entiers (BIGINT).
- Aucun calcul monétaire avec des flottants binaires.
- Dates métier en DATE, horodatages techniques en TIMESTAMPTZ.
- Fuseau horaire du foyer : Europe/Paris.
- Données personnelles et communes séparées.
- Historisation des règles et résultats mensuels.
- Suppression logique pour les données nécessitant une traçabilité.
- Contrôle des autorisations côté backend.

# 2. Domaines et tables

| Domaine | Tables |
|---|---|
| Utilisateurs | users, households, household_members |
| Confidentialité | financial_privacy_settings |
| Transactions | categories, transactions |
| Budgets | budgets, budget_periods |
| Récurrences | recurring_expenses, recurring_occurrences |
| Revenus et répartition | incomes, allocation_rules, allocation_rule_members, monthly_allocations, allocation_items |
| Notifications | notifications, notification_preferences |
| Import/export | import_batches, export_jobs |
| Traçabilité | audit_logs |

Le périmètre décrit 19 tables principales.

# 3. Utilisateurs et foyer

## 3.1 users

| Champ | Type | Règle |
|---|---|---|
| id | UUID | PK |
| email | VARCHAR(255) | UNIQUE, NOT NULL |
| hashed_password | VARCHAR(255) | NOT NULL |
| first_name | VARCHAR(100) | NOT NULL |
| is_active | BOOLEAN | NOT NULL |
| created_at | TIMESTAMPTZ | NOT NULL |
| updated_at | TIMESTAMPTZ | NOT NULL |

Le mot de passe n'est jamais stocké en clair.

## 3.2 households

| Champ | Type | Règle |
|---|---|---|
| id | UUID | PK |
| name | VARCHAR(150) | NOT NULL |
| currency | VARCHAR(3) | EUR par défaut |
| timezone | VARCHAR(50) | Europe/Paris par défaut |
| created_at | TIMESTAMPTZ | NOT NULL |
| updated_at | TIMESTAMPTZ | NOT NULL |

## 3.3 household_members

| Champ | Type | Règle |
|---|---|---|
| id | UUID | PK |
| household_id | UUID | FK households |
| user_id | UUID | FK users |
| role | VARCHAR(30) | owner / member |
| joined_at | TIMESTAMPTZ | NOT NULL |
| is_active | BOOLEAN | NOT NULL |

Contrainte UNIQUE (household_id, user_id). Les deux membres ont les mêmes droits fonctionnels sur les données communes en V1.

# 4. Confidentialité

## financial_privacy_settings

| Champ | Type | Règle |
|---|---|---|
| id | UUID | PK |
| user_id | UUID | FK users, UNIQUE |
| share_income_amount | BOOLEAN | FALSE par défaut |
| allow_income_for_allocation | BOOLEAN | TRUE par défaut |
| share_allocation_percentage | BOOLEAN | TRUE par défaut |
| share_allocation_amount | BOOLEAN | TRUE par défaut |
| updated_at | TIMESTAMPTZ | NOT NULL |

Les paramètres sont indépendants. Un revenu peut être utilisé par le moteur de calcul sans être exposé à l'autre membre.

Le backend doit filtrer les champs sensibles avant sérialisation. Les données privées ne doivent pas être chargées dans une réponse API puis masquées dans le navigateur.

# 5. Catégories et transactions

## 5.1 categories

| Champ | Type | Règle |
|---|---|---|
| id | UUID | PK |
| household_id | UUID nullable | FK households ; NULL pour catégorie système |
| name | VARCHAR(100) | NOT NULL |
| category_type | VARCHAR(30) | income / expense |
| icon | VARCHAR(50) | nullable |
| color | VARCHAR(20) | nullable |
| is_active | BOOLEAN | NOT NULL |
| created_at | TIMESTAMPTZ | NOT NULL |

## 5.2 transactions

| Champ | Type | Règle |
|---|---|---|
| id | UUID | PK |
| household_id | UUID nullable | FK households si commune |
| user_id | UUID | FK users, créateur/propriétaire |
| paid_by_user_id | UUID nullable | FK users |
| category_id | UUID | FK categories |
| recurring_occurrence_id | UUID nullable | FK recurring_occurrences |
| label | VARCHAR(255) | NOT NULL |
| amount_cents | BIGINT | positif |
| transaction_type | VARCHAR(30) | expense / income / refund |
| scope | VARCHAR(20) | personal / shared |
| transaction_date | DATE | NOT NULL |
| payment_method | VARCHAR(50) | nullable |
| notes | TEXT | nullable |
| created_at | TIMESTAMPTZ | NOT NULL |
| updated_at | TIMESTAMPTZ | NOT NULL |
| deleted_at | TIMESTAMPTZ | nullable |

Règles :
- Une transaction personnelle est rattachée à son propriétaire.
- Une transaction commune est rattachée à un foyer.
- paid_by_user_id distingue le payeur effectif du créateur.
- Une dépense alimentaire est enregistrée une seule fois ici ; le budget alimentaire l'agrège.
- Un remboursement est une transaction distincte de type refund.
- Les montants saisis sont positifs ; le type détermine le sens comptable.

Une validation métier doit empêcher une transaction commune sans foyer et une transaction personnelle appartenant à un autre utilisateur.

# 6. Budgets

## 6.1 budgets

| Champ | Type | Règle |
|---|---|---|
| id | UUID | PK |
| household_id | UUID nullable | Foyer pour budget commun |
| user_id | UUID nullable | Propriétaire pour budget personnel |
| category_id | UUID nullable | FK categories |
| name | VARCHAR(150) | NOT NULL |
| scope | VARCHAR(20) | personal / shared |
| budget_type | VARCHAR(30) | fixed / category |
| default_amount_cents | BIGINT | >= 0 |
| is_active | BOOLEAN | NOT NULL |
| created_at | TIMESTAMPTZ | NOT NULL |
| updated_at | TIMESTAMPTZ | NOT NULL |

Un budget est soit personnel, soit commun, jamais les deux.

## 6.2 budget_periods

| Champ | Type | Règle |
|---|---|---|
| id | UUID | PK |
| budget_id | UUID | FK budgets |
| period_start | DATE | premier jour du mois |
| period_end | DATE | dernier jour du mois |
| allocated_amount_cents | BIGINT | montant figé pour la période |
| status | VARCHAR(20) | open / closed |
| created_at | TIMESTAMPTZ | NOT NULL |

Contrainte UNIQUE (budget_id, period_start).

Aucun report de reliquat n'est autorisé. Le montant restant est calculé à partir de l'enveloppe de la période et des transactions éligibles. Les périodes passées restent consultables.

# 7. Dépenses récurrentes

## 7.1 recurring_expenses

| Champ | Type | Règle |
|---|---|---|
| id | UUID | PK |
| household_id | UUID nullable | FK households |
| user_id | UUID | FK users |
| category_id | UUID | FK categories |
| label | VARCHAR(255) | NOT NULL |
| amount_cents | BIGINT nullable | montant de référence |
| scope | VARCHAR(20) | personal / shared |
| frequency | VARCHAR(20) | weekly / monthly / quarterly / yearly |
| start_date | DATE | NOT NULL |
| end_date | DATE nullable | facultatif |
| day_of_month | SMALLINT nullable | échéance mensuelle |
| amount_confirmation_required | BOOLEAN | FALSE par défaut |
| is_active | BOOLEAN | NOT NULL |
| created_at | TIMESTAMPTZ | NOT NULL |
| updated_at | TIMESTAMPTZ | NOT NULL |

## 7.2 recurring_occurrences

| Champ | Type | Règle |
|---|---|---|
| id | UUID | PK |
| recurring_expense_id | UUID | FK recurring_expenses |
| period_date | DATE | échéance |
| expected_amount_cents | BIGINT nullable | montant indicatif |
| confirmed_amount_cents | BIGINT nullable | montant confirmé |
| status | VARCHAR(30) | pending_confirmation / confirmed / paid / skipped |
| transaction_id | UUID nullable | FK transactions |
| created_at | TIMESTAMPTZ | NOT NULL |
| updated_at | TIMESTAMPTZ | NOT NULL |

Contrainte UNIQUE (recurring_expense_id, period_date).

Pour une dépense variable :
1. l'occurrence est générée ;
2. l'utilisateur confirme le montant ;
3. l'occurrence passe à confirmed ;
4. la transaction réelle peut être créée ;
5. le paiement fait passer l'occurrence à paid.

Une occurrence non confirmée n'est pas une dépense réelle et ne réduit aucun budget.

Une occurrence payée référence une seule transaction. La création de la transaction et la mise à jour de l'occurrence doivent être atomiques.

# 8. Revenus

## incomes

| Champ | Type | Règle |
|---|---|---|
| id | UUID | PK |
| household_id | UUID | FK households |
| user_id | UUID nullable | propriétaire si revenu personnel |
| label | VARCHAR(150) | NOT NULL |
| amount_cents | BIGINT | positif |
| income_type | VARCHAR(30) | salary / benefit / other |
| scope | VARCHAR(20) | personal / household |
| period_start | DATE | NOT NULL |
| period_end | DATE | NOT NULL |
| created_at | TIMESTAMPTZ | NOT NULL |
| updated_at | TIMESTAMPTZ | NOT NULL |

Règles :
- Un revenu personnel exige un user_id.
- Un revenu du foyer n'a pas de user_id.
- La CAF est enregistrée comme revenu du foyer.
- Les revenus personnels sont soumis aux règles de confidentialité.
- L'inclusion d'un revenu dans la base de répartition est une règle distincte de son partage visuel.

Une future évolution peut ajouter une table de configuration d'éligibilité des types de revenus à la répartition, si cette configuration devient plus complexe.

# 9. Répartition

## 9.1 allocation_rules

| Champ | Type | Règle |
|---|---|---|
| id | UUID | PK |
| household_id | UUID | FK households |
| name | VARCHAR(150) | NOT NULL |
| calculation_method | VARCHAR(30) | income_percentage / custom_percentage |
| target_type | VARCHAR(30) | household / category / recurring_expense |
| target_id | UUID nullable | identifiant de la cible |
| effective_from | DATE | début d'effet |
| effective_until | DATE nullable | fin d'effet |
| is_active | BOOLEAN | NOT NULL |
| created_at | TIMESTAMPTZ | NOT NULL |
| updated_at | TIMESTAMPTZ | NOT NULL |

La méthode proportionnelle utilise les revenus admissibles. La méthode personnalisée utilise les pourcentages définis pour chaque membre.

Les cibles polymorphes (target_type, target_id) ne bénéficient pas d'une FK SQL classique. L'ERD devra confirmer si une table de règles par charge ou une association explicite est préférable.

## 9.2 allocation_rule_members

| Champ | Type | Règle |
|---|---|---|
| id | UUID | PK |
| allocation_rule_id | UUID | FK allocation_rules |
| user_id | UUID | FK users |
| percentage_basis | NUMERIC(7,4) | pourcentage |
| created_at | TIMESTAMPTZ | NOT NULL |

Contrainte UNIQUE (allocation_rule_id, user_id).

Pour une règle personnalisée, la somme des parts doit être égale à 100 %. Cette vérification doit être effectuée dans une transaction métier, ou au moyen d'une stratégie de contrainte différée si elle est implémentée en base.

## 9.3 monthly_allocations

| Champ | Type | Règle |
|---|---|---|
| id | UUID | PK |
| household_id | UUID | FK households |
| allocation_rule_id | UUID | FK allocation_rules |
| period_start | DATE | premier jour du mois |
| total_income_cents | BIGINT | base admissible |
| total_expenses_cents | BIGINT | charges réparties |
| calculation_status | VARCHAR(20) | complete / incomplete |
| calculation_snapshot | JSONB | paramètres et données de calcul |
| created_at | TIMESTAMPTZ | NOT NULL |

Le snapshot conserve les paramètres utilisés, les revenus admissibles, les règles et les arrondis nécessaires à l'explication du calcul. Les données sensibles doivent rester protégées dans les lectures API.

Contrainte d'unicité à définir sur le foyer, la période et la portée de la répartition.

## 9.4 allocation_items

| Champ | Type | Règle |
|---|---|---|
| id | UUID | PK |
| monthly_allocation_id | UUID | FK monthly_allocations |
| user_id | UUID | FK users |
| income_basis_cents | BIGINT nullable | revenu de référence |
| percentage_basis | NUMERIC(7,4) nullable | pourcentage |
| allocated_amount_cents | BIGINT | montant dû |
| created_at | TIMESTAMPTZ | NOT NULL |

Les réponses API exposent les revenus de référence uniquement si les permissions du propriétaire les autorisent. Le pourcentage et le montant réparti sont soumis à leurs autorisations respectives.

L'arrondi doit garantir que la somme des montants attribués est égale au total réparti.

# 10. Notifications

## 10.1 notifications

Champs :
- id UUID PK ;
- user_id UUID FK users ;
- household_id UUID nullable ;
- notification_type VARCHAR(50) ;
- title VARCHAR(150) ;
- message TEXT ;
- is_read BOOLEAN ;
- created_at TIMESTAMPTZ ;
- read_at TIMESTAMPTZ nullable.

## 10.2 notification_preferences

Champs :
- id UUID PK ;
- user_id UUID FK users ;
- notification_type VARCHAR(50) ;
- in_app_enabled BOOLEAN ;
- push_enabled BOOLEAN.

Types initiaux : grocery_budget_warning, grocery_budget_exceeded, recurring_expense_due, shared_transaction_created et shared_transaction_updated.

Contrainte UNIQUE (user_id, notification_type).

# 11. Import et export

## 11.1 import_batches

- id UUID PK ;
- user_id UUID FK users ;
- household_id UUID nullable ;
- filename VARCHAR(255) ;
- file_type VARCHAR(10), csv / xlsx ;
- status VARCHAR(20), pending / processing / completed / failed ;
- imported_rows INTEGER ;
- rejected_rows INTEGER ;
- created_at TIMESTAMPTZ.

L'import suit une phase de prévisualisation et validation. Les opérations doivent être idempotentes ou accompagnées d'une détection de doublons.

## 11.2 export_jobs

- id UUID PK ;
- user_id UUID FK users ;
- export_type VARCHAR(30) ;
- file_type VARCHAR(10) ;
- status VARCHAR(20) ;
- created_at TIMESTAMPTZ ;
- expires_at TIMESTAMPTZ.

Tout export applique les mêmes autorisations que les endpoints de lecture.

# 12. Audit

## audit_logs

- id UUID PK ;
- user_id UUID nullable ;
- household_id UUID nullable ;
- entity_type VARCHAR(50) ;
- entity_id UUID ;
- action VARCHAR(30), create / update / delete ;
- created_at TIMESTAMPTZ.

Ne jamais journaliser les mots de passe, les revenus privés en clair ou des données financières sensibles non nécessaires.

# 13. Règles d'intégrité

| Règle | Contrôle |
|---|---|
| Montants positifs | CHECK |
| Email unique | UNIQUE |
| Une occurrence par échéance | UNIQUE |
| Une période par budget et mois | UNIQUE |
| Une confidentialité par utilisateur | UNIQUE |
| Un membre une fois par foyer | UNIQUE |
| Dépense commune rattachée à un foyer | CHECK + validation |
| Revenu personnel avec propriétaire | CHECK |
| Revenu foyer sans propriétaire personnel | CHECK |
| Règle personnalisée totalisant 100 % | validation transactionnelle |
| Historique stable | snapshots |
| Récurrence sans double génération | UNIQUE + idempotence |

# 14. Périodes et dates

Les périodes budgétaires sont mensuelles, avec period_start au premier jour et period_end au dernier jour du mois. Les transactions conservent leur date réelle.

Les timestamps techniques sont en UTC (TIMESTAMPTZ). L'affichage utilise le fuseau du foyer.

# 15. Organisation SQLAlchemy

Organisation envisagée :

    backend/app/
    ├── models/
    │   ├── user.py
    │   ├── household.py
    │   ├── privacy.py
    │   ├── category.py
    │   ├── transaction.py
    │   ├── budget.py
    │   ├── recurring.py
    │   ├── income.py
    │   ├── allocation.py
    │   ├── notification.py
    │   ├── import_export.py
    │   └── audit.py
    ├── schemas/
    ├── repositories/
    ├── services/
    └── api/

Les modèles SQLAlchemy décrivent le stockage et les relations. La logique métier est centralisée dans les services.

# 16. Stratégie de tests

Unitaires :
- calcul des budgets restants ;
- calcul des proportions ;
- répartition au centime ;
- gestion des périodes ;
- génération des occurrences ;
- calcul avec revenus incomplets.

Intégration :
- création du foyer et association de deux utilisateurs ;
- transaction personnelle et commune ;
- génération puis confirmation d'une occurrence ;
- snapshot mensuel ;
- import et export.

Sécurité :
- isolation des transactions personnelles ;
- non-divulgation des revenus privés ;
- impossibilité de modifier les paramètres de confidentialité d'un autre membre ;
- accès contrôlé aux transactions communes ;
- permissions appliquées aux exports.

# 17. Points à arbitrer avant le schéma physique

1. Règle exacte d'éligibilité de chaque type de revenu (notamment CAF) dans la base de répartition.
2. Ciblage des règles de répartition : catégorie, dépense récurrente ou charge ponctuelle.
3. Unicité et granularité des snapshots mensuels.
4. Gestion des revenus variables et des périodes sans revenu.
5. Traitement d'un remboursement lorsqu'il concerne un budget déjà clôturé.
6. Gestion éventuelle des transferts entre comptes.
7. Choix d'un stockage séparé des snapshots sensibles si nécessaire.

---

**Fin — DATA_MODEL.md v0.2**
