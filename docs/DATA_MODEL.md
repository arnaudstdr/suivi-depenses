# Modèle de données — Suivi des dépenses

**Version :** 0.5  
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
| Comptes | users, households, household_members, sessions, invitations |
| Solde personnel | personal_balance_entries |
| Contributions foyer | household_contributions |
| Transactions | categories, transactions |
| Charges | recurring_expenses, recurring_occurrences |
| Prévisions | planned_expenses |
| Budget courses | budgets, budget_periods |
| Répartition | allocation_rules, allocation_rule_members |
| Historique | audit_logs |
| Fonctions annexes | notifications, notification_preferences, import_batches, export_jobs |

Les revenus de référence ne participent pas au calcul du disponible prévisionnel. Ils pourront être ajoutés ultérieurement si un besoin concret le justifie.

## 3. users, households, household_members

Ces tables constituent le socle d'identité implémenté par la migration `0001_identity_core`.

### users

| Champ | Type | Règle |
|---|---|---|
| id | UUID | PK |
| email | VARCHAR(320) | NOT NULL, UNIQUE, stocké en minuscules (`CHECK email = lower(email)`) |
| password_hash | VARCHAR(255) | NOT NULL, hachage Argon2id |
| first_name | VARCHAR(100) | NOT NULL, non vide |
| is_active | BOOLEAN | NOT NULL, défaut `true` |
| created_at | TIMESTAMPTZ | NOT NULL, défaut `now()` |
| updated_at | TIMESTAMPTZ | NOT NULL, défaut `now()` |

### households

| Champ | Type | Règle |
|---|---|---|
| id | UUID | PK |
| name | VARCHAR(150) | NOT NULL, non vide |
| currency | VARCHAR(3) | NOT NULL, défaut `EUR`, contrainte `EUR` en V1 |
| timezone | VARCHAR(64) | NOT NULL, défaut `Europe/Paris`, contrainte `Europe/Paris` en V1 |
| created_at | TIMESTAMPTZ | NOT NULL, défaut `now()` |
| updated_at | TIMESTAMPTZ | NOT NULL, défaut `now()` |

### household_members

| Champ | Type | Règle |
|---|---|---|
| id | UUID | PK |
| household_id | UUID | FK households, `ON DELETE CASCADE`, NOT NULL |
| user_id | UUID | FK users, `ON DELETE CASCADE`, NOT NULL |
| role | VARCHAR(20) | NOT NULL, `owner` ou `member`, défaut `member` |
| is_active | BOOLEAN | NOT NULL, défaut `true` |
| created_at | TIMESTAMPTZ | NOT NULL, défaut `now()` |
| updated_at | TIMESTAMPTZ | NOT NULL, défaut `now()` |

Contraintes : `UNIQUE(household_id, user_id)` et `UNIQUE(user_id)`, car un compte appartient à un seul foyer en V1. `household_members` associe les deux comptes au foyer avec un rôle et un statut actif.

### sessions

| Champ | Type | Règle |
|---|---|---|
| id | UUID | PK |
| user_id | UUID | FK users, `ON DELETE CASCADE`, NOT NULL |
| token_hash | VARCHAR(64) | NOT NULL, UNIQUE, SHA-256 du token opaque |
| created_at | TIMESTAMPTZ | NOT NULL |
| last_seen_at | TIMESTAMPTZ | NOT NULL |
| expires_at | TIMESTAMPTZ | NOT NULL, `CHECK expires_at > created_at` |
| revoked_at | TIMESTAMPTZ | nullable |

Le token de session brut n'est jamais stocké : seul son hash SHA-256 est conservé. Le cookie de session est `HttpOnly`, `Secure` en production, `SameSite=Lax` par défaut et expire après 30 jours. Une session révoquée ou expirée est refusée.

### invitations

| Champ | Type | Règle |
|---|---|---|
| id | UUID | PK |
| household_id | UUID | FK households, `ON DELETE CASCADE`, NOT NULL |
| email | VARCHAR(320) | NOT NULL, minuscules, non vide |
| role | VARCHAR(20) | NOT NULL, `member` en V1 |
| token_hash | VARCHAR(64) | NOT NULL, UNIQUE, SHA-256 du token |
| created_by_user_id | UUID | FK users, `ON DELETE CASCADE`, NOT NULL |
| accepted_by_user_id | UUID | FK users, `ON DELETE SET NULL`, nullable |
| expires_at | TIMESTAMPTZ | NOT NULL, `CHECK expires_at > created_at` |
| used_at | TIMESTAMPTZ | nullable |
| created_at | TIMESTAMPTZ | NOT NULL |

Une invitation est à usage unique, expire après 7 jours par défaut et doit être acceptée avec l'email invité. Le token brut n'est affiché qu'une fois au propriétaire ; seul son hash est stocké. L'acceptation crée l'utilisateur, l'appartenance au foyer et une session, dans une seule transaction.

### audit_logs

| Champ | Type | Règle |
|---|---|---|
| id | UUID | PK |
| occurred_at | TIMESTAMPTZ | NOT NULL |
| actor_user_id | UUID | FK users, `ON DELETE SET NULL`, nullable |
| household_id | UUID | FK households, `ON DELETE SET NULL`, nullable |
| action | VARCHAR(100) | NOT NULL, non vide |
| entity_type | VARCHAR(50) | NOT NULL |
| entity_id | UUID | nullable |
| details | JSONB | nullable, sans secret ni donnée financière détaillée |
| request_id | VARCHAR(64) | nullable |

Actions enregistrées par le socle : `auth.login_succeeded`, `auth.login_failed`, `auth.logout`, `household.bootstrapped`, `invitation.created`, `invitation.accepted` et `user.profile_updated`.

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

Le solde courant de référence est la dernière saisie du propriétaire. Chaque nouvelle saisie constitue un instantané daté : les opérations antérieures ou égales à `recorded_at` sont réputées déjà reflétées dans le solde ; les sorties postérieures restent à déduire, même si elles sont marquées payées. Une nouvelle saisie remplace la référence pour les calculs futurs, sans supprimer l'historique. Aucun compte bancaire externe ou compte joint n'est modélisé en V1.

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

Les catégories marquées is_grocery identifient les dépenses pouvant consommer l'enveloppe courses. Les catégories globales par défaut sont seedées par les migrations `0003_financial_core` et `0005_allocations` : Courses / alimentation, Logement, Énergie, Transport, Santé, Abonnements, Loisirs, Divers et Participation au foyer. Un nom ne peut pas être dupliqué, globalement ou dans un foyer. Les catégories globales sont en lecture seule.

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
| paid_at | TIMESTAMPTZ nullable | date/heure réelle du paiement ; NULL si non payé |
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
- Une transaction de virement de participation est liée à `household_contributions.transaction_id` et ne doit pas être déduite une seconde fois en plus de la participation.
- `recurring_occurrence_id` est ajouté par la migration `0004_forecast` et référence l'échéance à l'origine de la transaction.
- Les transactions sont créées avec `status='paid'` et un `paid_at` renseigné. Si `paid_at` est omis, le serveur utilise midi dans le fuseau du foyer.
- La suppression est logique via `deleted_at`; une dépense ayant des remboursements ne peut pas être supprimée.
- Un remboursement ne peut pas dépasser le montant encore remboursable de la dépense d'origine.

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

Pour une charge shared, la règle de répartition sera résolue à partir de la règle par défaut du foyer ou d'une règle spécifique à cette charge. Le lien structurel vers les règles de répartition est ajouté avec la tranche 4.3.

## 8. recurring_occurrences

| Champ | Type | Règle |
|---|---|---|
| id | UUID | PK |
| recurring_expense_id | UUID | FK recurring_expenses |
| due_date | DATE | NOT NULL |
| expected_amount_cents | BIGINT nullable | montant attendu |
| confirmed_amount_cents | BIGINT nullable | montant confirmé |
| confirmed_at | TIMESTAMPTZ nullable | instant de la confirmation du montant |
| status | VARCHAR(30) | pending / confirmed / paid / skipped |
| paid_at | TIMESTAMPTZ nullable | date/heure réelle du paiement pointé |
| payment_amount_cents | BIGINT nullable | montant réellement payé, notamment pour montant variable |
| payment_note | TEXT nullable | note ou motif de correction |
| skipped_at | TIMESTAMPTZ nullable | instant où l'échéance a été ignorée |
| skip_reason | TEXT nullable | motif facultatif de l'échéance ignorée |
| transaction_id | UUID nullable | FK transactions, UNIQUE |
| created_at / updated_at | TIMESTAMPTZ | NOT NULL |

Contrainte UNIQUE (recurring_expense_id, due_date). La génération des occurrences est idempotente pour une période demandée, y compris sous accès concurrent, via `INSERT ... ON CONFLICT DO NOTHING`. Elle est déclenchée par la lecture des échéances, du tableau de bord et des contributions, ainsi que par la commande CLI planifiable. Le pointage `paid` renseigne `paid_at`, confirme `payment_amount_cents`, crée ou associe une transaction réelle, renseigne son `paid_at` et lie les deux enregistrements. Le pointage est idempotent : une seconde demande ne crée pas une deuxième transaction. Toute correction d'un paiement déjà pointé est une opération explicite et auditée (`correct-payment`) qui met à jour l'occurrence et sa transaction liée dans la même transaction SQL. Le statut `confirmed` fige un montant variable avant pointage ; le statut `skipped` exclut l'échéance des déductions et des contributions, avec horodatage et motif conservés.

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
| status | VARCHAR(20) | planned / committed / paid / cancelled |
| transaction_id | UUID nullable | FK transactions |
| created_at / updated_at | TIMESTAMPTZ | NOT NULL |

Les dépenses ponctuelles communes hors courses sont réparties et intégrées à la participation au foyer. Les dépenses ponctuelles de courses communes consomment le budget courses uniquement au moment du paiement, via la transaction créée. Le pointage payé est idempotent et lie une transaction unique. Une dépense annulée ou déjà payée ne peut plus être modifiée.

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

Le budget courses initial est de 49 000 centimes (490 €), mensuel et commun. Il est créé au bootstrap du foyer et pour les foyers existants par la migration `0003_financial_core`. Un seul budget `grocery` est autorisé par foyer. La période mensuelle est créée à la demande, avec le montant par défaut, sans report du reliquat.

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

Une règle peut être la répartition par défaut du foyer ou une règle spécifique à une charge. Chaque règle contient les pourcentages par membre, en `NUMERIC(6,3)`, totalisant exactement 100 %. La règle spécifique prévaut sur la règle par défaut.

À la création du foyer, la règle par défaut contient le seul propriétaire à 100 %. Quand le second membre rejoint le foyer, elle passe automatiquement à 55 % pour le premier membre et 45 % pour le second, tant qu'elle n'a pas déjà été personnalisée. Les foyers existants sont backfillés par la migration `0005_allocations`. La colonne `recurring_expenses.allocation_rule_id` permet de lier une règle spécifique à une charge commune.

Une charge commune est imputée à chaque membre selon son pourcentage. La répartition se fait au centime avec la méthode du plus fort reste, de façon déterministe, et la somme des parts est exactement égale au montant. Pour le tableau de bord personnel, seule la quote-part du membre connecté est agrégée dans Participation au foyer.

La contribution mensuelle au budget courses (55 % de 490 €, soit 269,50 € pour l'utilisateur et 220,50 € pour l'autre membre) est intégrée à la ligne Participation au foyer. Les achats de courses ne sont ensuite imputés qu'au budget courses : ils ne diminuent jamais le disponible personnel une seconde fois.

## 12. household_contributions

Suit le virement mensuel de participation au foyer de chaque membre. La contribution inclut la quote-part des charges communes et la contribution à l'enveloppe courses.

| Champ | Type | Règle |
|---|---|---|
| id | UUID | PK |
| household_id | UUID | FK households, NOT NULL |
| user_id | UUID | FK users, membre contributeur |
| period_start | DATE | premier jour du mois |
| amount_cents | BIGINT | montant de contribution figé pour la période |
| allocation_percentage | NUMERIC(6,3) | pourcentage appliqué, instantané historique |
| status | VARCHAR(20) | pending / transferred / cancelled |
| transferred_at | TIMESTAMPTZ nullable | date/heure réelle du virement confirmé |
| transferred_amount_cents | BIGINT nullable | montant réellement transféré, positif |
| transaction_id | UUID nullable | FK transactions, UNIQUE, transaction réelle du virement |
| created_at / updated_at | TIMESTAMPTZ | NOT NULL |

Contrainte UNIQUE (household_id, user_id, period_start). Le statut `transferred` signifie que l'utilisateur a pointé le virement comme une échéance récurrente, en confirmant `transferred_at` et `transferred_amount_cents` ; la transaction réelle associée est unique et le pointage est idempotent. Il ne signifie pas que la sortie est déjà incluse dans le dernier solde personnel saisi. Une contribution transférée après `personal_balance_entries.recorded_at` reste déduite du disponible jusqu'à la prochaine saisie de solde. Une contribution transférée avant ou à cette date est déjà reflétée dans le solde et est exclue. Une correction de virement passe par une action explicite et auditée (`correct-transfer`) qui met à jour la contribution et sa transaction liée.

Une contribution d'une période passée déjà matérialisée est figée : les lectures suivantes ne recalculent plus son montant ni son pourcentage. Une modification de règle ne réécrit donc pas les périodes passées. La première lecture d'une période passée jamais matérialisée crée la ligne avec les données disponibles à cet instant, puis la fige.

La transaction du virement est une transaction personnelle de catégorie « Participation au foyer ». Elle est liée à la contribution et doit être exclue des déductions de transactions personnelles lors du calcul du disponible, afin de ne pas compter deux fois la participation. `allocation_percentage` conserve le pourcentage par défaut du membre comme référence historique ; le montant peut refléter des règles spécifiques par charge.

## 13. Calcul du disponible prévisionnel

Le backend calcule pour un mois donné :

`available_forecast_cents = latest_personal_balance_cents - personal_outflows_after_snapshot_cents - household_contributions_not_reflected_cents - personal_planned_expenses_not_reflected_cents`

Le calcul utilise `recorded_at` comme date de coupure. Pour les transactions, comparer `paid_at` à cet instantané ; ne pas utiliser uniquement `transaction_date`, qui représente la date métier et non l'instant réel de débit. Toute sortie effectivement payée après cet instantané est déduite, même si son statut est `paid` ou `transferred`. Une sortie payée avant ou à l'instantané est exclue, car elle est déjà intégrée au solde. Les engagements non payés restant dus sont également déduits. Les charges communes sont agrégées dans une seule ligne « Participation au foyer ». Les achats de courses communes restent exclus du calcul personnel : seule la contribution au budget courses est incluse dans la participation.

Le statut de paiement et l'inclusion dans l'instantané bancaire sont deux notions distinctes. Marquer un virement comme effectué ne modifie donc pas le disponible à lui seul ; une nouvelle saisie du solde après le virement actualise la base et fait disparaître la déduction correspondante sans double comptage.

Règles d'implémentation de la tranche 4.4 :

- Le calcul porte sur le mois courant.
- Pour les éléments payés, le mois retenu est celui du paiement réel (`paid_at` ou `transaction_date` de la transaction liée) ; pour les éléments non payés, celui de l'échéance ou de la date prévue.
- Les transactions liées à une occurrence récurrente, à une dépense prévue ou à un virement de participation sont exclues des déductions de transactions personnelles : leur montant est déjà porté par la ligne source.
- Une occurrence `skipped` et une dépense annulée sont exclues.
- Une contribution `pending` est déduite de son montant calculé. Une contribution `transferred` est déduite de son montant réel si le virement est postérieur à l'instantané, et exclue sinon.
- Les achats de courses communes ne sont jamais déduits du disponible personnel.
- Les déductions peuvent être négatives lorsqu'un remboursement personnel postérieur à l'instantané compense une dépense déjà reflétée.

Le calcul ne comprend aucun revenu attendu. Le solde négatif est autorisé et affiché explicitement.

## 14. Audit et fonctions annexes

Les opérations financières sensibles sont auditées : création/modification/suppression de charges, modification des répartitions avec pourcentages avant/après, saisie du solde, confirmation/pointage/skip/correction d'une occurrence, pointage et correction d'une contribution, modification et correction d'une dépense prévue. Les transactions liées à une occurrence, une dépense prévue ou une contribution ne peuvent pas être modifiées ou supprimées directement : la correction doit passer par l'élément source, ce qui garantit la cohérence de l'historique. Les notifications, imports et exports respectent les mêmes permissions que les données sources.

## 15. Contraintes et index

- Montants > 0 pour dépenses ; solde personnel signé.
- Pourcentages entre 0 et 100 et totalisant 100 % par règle.
- Une occurrence par récurrence et date.
- Une transaction liée au maximum à une occurrence.
- Une période par budget et mois.
- Une dépense de courses commune doit référencer le budget courses du foyer.
- Une transaction personnelle ne peut pas référencer un budget du foyer.
- Les règles de périmètre sont validées côté service et en base lorsque possible.

## 16. Tests métier indispensables

- Solde manuel et horodatage.
- Charges personnelles fixes et variables.
- Pointage manuel d'une échéance récurrente avec date et montant réellement payés.
- Pointage idempotent sans création de doublon de transaction.
- Échéance pointée payée après l'instantané de solde toujours déduite jusqu'à une nouvelle saisie du solde.
- Calcul de la quote-part 55/45 et règles spécifiques.
- Agrégation de toutes les charges communes dans une seule ligne.
- Exclusion des sorties payées avant ou à l'instantané de solde.
- Inclusion des sorties payées après l'instantané jusqu'à la prochaine saisie de solde.
- Marquage du virement de participation effectué sans variation artificielle du disponible.
- Nouvelle saisie de solde après virement sans double déduction.
- Exclusion des revenus futurs.
- Exclusion des achats courses communes du disponible personnel.
- Déduction d'une dépense courses commune du budget de 490 €.
- Absence de double comptage lors du paiement d'une charge.
- Arrondis au centime.
