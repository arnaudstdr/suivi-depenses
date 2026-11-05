# Modèle de données — Suivi des dépenses

**Version :** 0.3  
**Statut :** Modèle conceptuel aligné sur les règles métier validées  
**Backend cible :** Python 3.12 / FastAPI / SQLAlchemy 2  
**Base :** PostgreSQL

## 1. Principes

- UUID pour les identifiants.
- Montants en centimes entiers (BIGINT), jamais en float.
- Dates métier en DATE ; horodatages en TIMESTAMPTZ.
- Fuseau du foyer : Europe/Paris.
- Séparation stricte des données personnelles et du foyer.
- Pas de synchronisation bancaire.
- Le solde du compte courant personnel est saisi manuellement.
- Le compte joint n'a pas de solde suivi.
- Les calculs historiques et les dépenses payées ne sont pas réécrits silencieusement.

## 2. Entités principales

| Domaine | Entités |
|---|---|
| Comptes | users, households, household_members |
| Solde personnel | personal_balance_entries |
| Transactions | categories, transactions |
| Charges | recurring_expenses, recurring_occurrences |
| Prévisions | planned_expenses |
| Budget courses | budgets, budget_periods |
| Répartition | allocation_rules, allocation_rule_members |
| Historique | audit_logs |
| Fonctions annexes | notifications, notification_preferences, import_batches, export_jobs |

Les revenus de référence ne participent pas au calcul du disponible prévisionnel. Ils pourront être ajoutés ultérieurement si un besoin concret le justifie.

## 3. users, households, household_members

Les tables d'identité conservent les champs usuels : UUID, email unique, mot de passe haché, prénom, statut actif et timestamps. Un foyer possède un nom, une devise EUR et le fuseau Europe/Paris. household_members associe les deux comptes au foyer avec un rôle et un statut actif.

## 4. personal_balance_entries

Historise les saisies manuelles du solde du compte courant personnel.

| Champ | Type | Règle |
|---|---|---|
| id | UUID | PK |
| user_id | UUID | FK users, NOT NULL |
| balance_cents | BIGINT | NOT NULL, peut être négatif |
| recorded_at | TIMESTAMPTZ | NOT NULL |
| note | TEXT | nullable |
| created_at | TIMESTAMPTZ | NOT NULL |

Le solde courant de référence est la dernière saisie du propriétaire. Chaque nouvelle saisie remplace la référence pour les calculs futurs, sans supprimer l'historique. Aucun compte bancaire externe ou compte joint n'est modélisé en V1.

## 5. categories

| Champ | Type | Règle |
|---|---|---|
| id | UUID | PK |
| household_id | UUID nullable | FK households |
| name | VARCHAR(100) | NOT NULL |
| category_type | VARCHAR(20) | expense |
| is_grocery | BOOLEAN | NOT NULL, FALSE par défaut |
| icon | VARCHAR(50) | nullable |
| is_active | BOOLEAN | NOT NULL |

Les catégories marquées is_grocery identifient les dépenses pouvant consommer l'enveloppe courses.

## 6. transactions

| Champ | Type | Règle |
|---|---|---|
| id | UUID | PK |
| household_id | UUID nullable | FK households si commune |
| user_id | UUID | FK users, créateur |
| category_id | UUID | FK categories |
| recurring_occurrence_id | UUID nullable | FK recurring_occurrences |
| label | VARCHAR(255) | NOT NULL |
| amount_cents | BIGINT | CHECK > 0 |
| transaction_type | VARCHAR(20) | expense / refund |
| scope | VARCHAR(20) | personal / shared |
| budget_id | UUID nullable | FK budgets |
| transaction_date | DATE | NOT NULL |
| status | VARCHAR(20) | paid |
| original_transaction_id | UUID nullable | FK transactions pour remboursement |
| notes | TEXT | nullable |
| created_at / updated_at | TIMESTAMPTZ | NOT NULL |
| deleted_at | TIMESTAMPTZ | nullable |

Règles :
- Une transaction personal appartient à son créateur et n'a pas de household_id.
- Une transaction shared appartient au foyer.
- Une dépense de courses commune référence le budget courses du foyer et consomme uniquement ce budget.
- Une transaction personnelle n'alimente jamais le budget courses commun.
- Une transaction commune hors courses est répartie selon la règle configurée ; sa quote-part personnelle alimente la ligne agrégée Participation au foyer.
- Une dépense est enregistrée une seule fois.
- Un remboursement est une transaction distincte liée à l'originale.

## 7. recurring_expenses

| Champ | Type | Règle |
|---|---|---|
| id | UUID | PK |
| household_id | UUID nullable | FK households si commune |
| owner_user_id | UUID | FK users |
| category_id | UUID | FK categories |
| label | VARCHAR(255) | NOT NULL |
| amount_cents | BIGINT nullable | montant fixe ou référence |
| scope | VARCHAR(20) | personal / shared |
| frequency | VARCHAR(20) | weekly / monthly / quarterly / semiannual / yearly |
| start_date | DATE | NOT NULL |
| end_date | DATE nullable | facultatif |
| due_day | SMALLINT nullable | jour d'échéance |
| amount_is_variable | BOOLEAN | FALSE |
| is_active | BOOLEAN | NOT NULL |
| created_at / updated_at | TIMESTAMPTZ | NOT NULL |

Pour une charge shared, la règle de répartition est résolue à partir de la règle par défaut du foyer ou d'une règle spécifique à cette charge.

## 8. recurring_occurrences

| Champ | Type | Règle |
|---|---|---|
| id | UUID | PK |
| recurring_expense_id | UUID | FK recurring_expenses |
| due_date | DATE | NOT NULL |
| expected_amount_cents | BIGINT nullable | montant attendu |
| confirmed_amount_cents | BIGINT nullable | montant confirmé |
| status | VARCHAR(30) | pending / confirmed / paid / skipped |
| transaction_id | UUID nullable | FK transactions, UNIQUE |
| created_at / updated_at | TIMESTAMPTZ | NOT NULL |

Contrainte UNIQUE (recurring_expense_id, due_date). La génération des occurrences est idempotente.

## 9. planned_expenses

Dépenses ponctuelles prévues mais pas encore payées.

| Champ | Type | Règle |
|---|---|---|
| id | UUID | PK |
| household_id | UUID nullable | FK households si commune |
| user_id | UUID | FK users |
| category_id | UUID | FK categories |
| label | VARCHAR(255) | NOT NULL |
| amount_cents | BIGINT | CHECK > 0 |
| scope | VARCHAR(20) | personal / shared |
| planned_date | DATE | NOT NULL |
| status | VARCHAR(20) | planned / paid / cancelled |
| transaction_id | UUID nullable | FK transactions |
| created_at / updated_at | TIMESTAMPTZ | NOT NULL |

Les dépenses ponctuelles communes hors courses sont réparties et intégrées à la participation au foyer. Les dépenses ponctuelles de courses communes consomment le budget courses et ne sont pas ajoutées au suivi personnel.

## 10. Budgets et périodes

### budgets

| Champ | Type | Règle |
|---|---|---|
| id | UUID | PK |
| household_id | UUID | FK households, NOT NULL |
| name | VARCHAR(150) | NOT NULL |
| budget_type | VARCHAR(30) | grocery / other |
| category_id | UUID nullable | FK categories |
| default_amount_cents | BIGINT | >= 0 |
| is_active | BOOLEAN | NOT NULL |
| created_at / updated_at | TIMESTAMPTZ | NOT NULL |

Le budget courses initial est de 49 000 centimes (490 €), mensuel et commun.

### budget_periods

| Champ | Type | Règle |
|---|---|---|
| id | UUID | PK |
| budget_id | UUID | FK budgets |
| period_start | DATE | premier jour du mois |
| period_end | DATE | dernier jour du mois |
| allocated_amount_cents | BIGINT | montant figé |
| status | VARCHAR(20) | open / closed |
| created_at | TIMESTAMPTZ | NOT NULL |

Contrainte UNIQUE (budget_id, period_start). Aucun report du reliquat. Le consommé est l'agrégat des transactions communes éligibles affectées à ce budget.

## 11. allocation_rules et allocation_rule_members

Une règle peut être la répartition par défaut du foyer ou une règle spécifique à une charge. Chaque règle contient les pourcentages par membre.

Valeurs initiales : utilisateur courant 55 %, autre membre 45 %. Les pourcentages doivent totaliser exactement 100 %. La règle spécifique prévaut sur la règle par défaut.

Une charge commune est imputée à chaque membre selon son pourcentage. Pour le tableau de bord personnel, seule la quote-part du membre connecté est agrégée dans Participation au foyer.

La contribution mensuelle au budget courses (55 % de 490 €, soit 269,50 € pour l'utilisateur et 220,50 € pour l'autre membre) peut être représentée comme un engagement récurrent commun distinct, intégré à la ligne Participation au foyer. Les achats de courses ne sont ensuite imputés qu'au budget courses : ils ne diminuent jamais le disponible personnel une seconde fois.

## 12. Calcul du disponible prévisionnel

Le backend calcule pour un mois donné :

`available_forecast_cents = latest_personal_balance_cents - personal_recurring_due_cents - household_share_due_cents - personal_planned_expenses_cents`

Les sommes incluent uniquement les échéances à venir et non payées à la date de référence. Les charges communes sont agrégées en une seule valeur pour le tableau de bord. Les achats de courses communes sont exclus du calcul personnel.

Le solde saisi est déjà net des opérations bancaires réellement passées. Toute occurrence ou dépense marquée payée est donc exclue des déductions futures.

Le calcul ne comprend aucun revenu attendu. Le solde négatif est autorisé et affiché explicitement.

## 13. Audit et fonctions annexes

Les opérations financières sensibles sont auditées : création/modification/suppression de charges, modification des répartitions, saisie du solde, paiement d'une occurrence et modification d'une dépense prévue. Les notifications, imports et exports respectent les mêmes permissions que les données sources.

## 14. Contraintes et index

- Montants > 0 pour dépenses ; solde personnel signé.
- Pourcentages entre 0 et 100 et totalisant 100 % par règle.
- Une occurrence par récurrence et date.
- Une transaction liée au maximum à une occurrence.
- Une période par budget et mois.
- Une dépense de courses commune doit référencer le budget courses du foyer.
- Une transaction personnelle ne peut pas référencer un budget du foyer.
- Les règles de périmètre sont validées côté service et en base lorsque possible.

## 15. Tests métier indispensables

- Solde manuel et horodatage.
- Charges personnelles fixes et variables.
- Calcul de la quote-part 55/45 et règles spécifiques.
- Agrégation de toutes les charges communes dans une seule ligne.
- Exclusion des charges payées.
- Exclusion des revenus futurs.
- Exclusion des achats courses communes du disponible personnel.
- Déduction d'une dépense courses commune du budget de 490 €.
- Absence de double comptage lors du paiement d'une charge.
- Arrondis au centime.
