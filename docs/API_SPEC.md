# Spécification API REST — Suivi des dépenses

**Version :** 0.6  
**Statut :** Contrat conceptuel aligné sur les règles métier  
**Base URL :** `/api/v1`  
**Backend :** FastAPI / Pydantic v2

## 1. Conventions

- Identifiants UUID.
- Dates métier ISO `YYYY-MM-DD`.
- Horodatages ISO 8601 avec fuseau.
- Montants en centimes entiers.
- Pourcentages en points de pourcentage (55.0000 = 55 %).
- Les permissions sont vérifiées côté serveur.
- Les listes sont paginées ; les erreurs suivent un format commun.

## 2. Authentification

| Méthode | Route | Description |
|---|---|---|
| POST | `/auth/login` | Connexion |
| POST | `/auth/logout` | Déconnexion |
| GET | `/auth/me` | Utilisateur courant |
| PATCH | `/users/me` | Modifier son profil |

Sessions par cookie HttpOnly, Secure, SameSite adapté et protection CSRF. La création de compte est sur invitation en V1.

## 3. Solde personnel

| Méthode | Route | Description |
|---|---|---|
| GET | `/users/me/personal-balance` | Dernier solde saisi |
| PUT | `/users/me/personal-balance` | Enregistrer une nouvelle saisie |
| GET | `/users/me/personal-balance/history` | Historique des saisies |

Le solde saisi est un instantané daté. Les sorties payées après `recorded_at` restent déduites du disponible jusqu'à la prochaine saisie de solde ; les sorties déjà passées avant cet instantané sont exclues.

Exemple PUT :

```json
{
  "balance_cents": 150000,
  "recorded_at": "2026-11-05T08:30:00+01:00"
}
```

Le backend conserve l'horodatage et l'historique. Aucun accès bancaire externe n'est appelé. Un solde négatif est accepté. `recorded_at` est l'instantané de référence pour déterminer quelles sorties sont déjà reflétées.

## 4. Tableau de bord personnel

| Méthode | Route | Description |
|---|---|---|
| GET | `/users/me/dashboard?period=2026-11` | Synthèse personnelle |

Exemple de réponse :

```json
{
  "period": "2026-11",
  "currency": "EUR",
  "personal_balance": {
    "balance_cents": 150000,
    "recorded_at": "2026-11-05T08:30:00+01:00"
  },
  "deductions": {
    "personal_recurring_remaining_cents": 25000,
    "household_contribution_remaining_cents": 30000,
    "household_contribution_status": "pending",
    "personal_planned_remaining_cents": 10000
  },
  "available_forecast_cents": 85000,
  "grocery_budget": {
    "allocated_cents": 49000,
    "spent_cents": 20580,
    "remaining_cents": 28420
  }
}
```

Les déductions couvrent les engagements non payés et les sorties payées après le dernier instantané de solde. Les revenus futurs et les achats de courses communes sont exclus du disponible personnel. La ligne household_contribution est agrégée ; elle inclut la contribution au budget courses et le détail est disponible dans les vues charges.

## 5. Participation au foyer

| Méthode | Route | Description |
|---|---|---|
| GET | `/households/{household_id}/contributions?period=YYYY-MM` | Lire la participation du membre pour la période |
| POST | `/households/{household_id}/contributions/{contribution_id}/mark-transferred` | Confirmer que le virement a été effectué |

La contribution mensuelle agrège la part du membre dans les charges communes et sa contribution au budget courses. Le statut passe de `pending` à `transferred` avec `transferred_at`. Cette action ne modifie pas à elle seule le disponible : si le virement est postérieur au dernier instantané de solde, son montant reste déduit. Une nouvelle saisie du solde après le virement l'intègre et supprime alors la déduction, sans double comptage.

## 6. Transactions

| Méthode | Route | Description |
|---|---|---|
| GET | `/transactions` | Lister les dépenses accessibles |
| POST | `/transactions` | Créer une dépense |
| GET | `/transactions/{id}` | Détail |
| PATCH | `/transactions/{id}` | Modifier |
| DELETE | `/transactions/{id}` | Supprimer logiquement |

Filtres : `scope`, `category_id`, `date_from`, `date_to`, `status`, `search`.

Exemple création dépense :

```json
{
  "label": "Courses hebdomadaires",
  "amount_cents": 6840,
  "transaction_date": "2026-11-05",
  "category_id": "uuid-category-grocery",
  "scope": "shared",
  "budget_id": "uuid-household-grocery-budget"
}
```

Règles :
- `scope=personal` : dépense personnelle, rattachée à l'utilisateur connecté.
- `scope=shared` + catégorie courses : dépense commune qui consomme le budget courses ; elle n'affecte pas le disponible personnel.
- `scope=shared` hors courses : sa quote-part personnelle est intégrée à la participation au foyer, si elle est prévue et non payée depuis le budget personnel.
- Une transaction comporte `paid_at`, horodatage réel du paiement. Si `paid_at` est postérieur au dernier `recorded_at`, la sortie reste déduite du disponible jusqu'à une nouvelle saisie de solde. Si `paid_at` est antérieur ou égal à `recorded_at`, elle est déjà reflétée et n'est pas déduite.
- Le serveur déduit l'identité du créateur de la session.

## 7. Charges récurrentes

| Méthode | Route | Description |
|---|---|---|
| GET | `/recurring-expenses` | Lister |
| POST | `/recurring-expenses` | Créer |
| GET | `/recurring-expenses/{id}` | Détail |
| PATCH | `/recurring-expenses/{id}` | Modifier |
| POST | `/recurring-expenses/{id}/deactivate` | Désactiver |
| GET | `/recurring-expenses/{id}/occurrences` | Échéances |
| POST | `/recurring-occurrences/{occurrence_id}/mark-paid` | Pointer une échéance comme payée |

Champs de création : `label`, `amount_cents`, `category_id`, `scope` (personal/shared), `frequency`, `start_date`, `end_date`, `due_day`, `amount_is_variable`, et, si shared, une règle de répartition par défaut ou spécifique.

Une charge commune est répartie selon les pourcentages configurés. La part de l'utilisateur connecté est agrégée avec les autres charges communes dans la ligne « Participation au foyer » du tableau de bord personnel. Les détails par charge sont accessibles dans l'écran Charges.

Le pointage d'une occurrence se fait explicitement après le paiement réel. Le corps de `POST /recurring-occurrences/{occurrence_id}/mark-paid` accepte `paid_at`, `payment_amount_cents` et une note facultative. Le serveur passe l'occurrence à `paid`, crée ou associe une transaction réelle de manière idempotente et journalise l'opération. Pour une charge variable, `payment_amount_cents` est obligatoire ; pour une charge fixe, il est proposé à partir du montant attendu et peut être corrigé. Le montant payé après le dernier instantané de solde reste déduit du disponible jusqu'à une nouvelle saisie du solde. Une échéance déjà payée ne peut pas être repointée sans action de correction dédiée.

## 8. Dépenses ponctuelles prévues

| Méthode | Route | Description |
|---|---|---|
| GET | `/planned-expenses` | Lister |
| POST | `/planned-expenses` | Créer une prévision |
| PATCH | `/planned-expenses/{id}` | Modifier |
| POST | `/planned-expenses/{id}/mark-paid` | Marquer payée |
| DELETE | `/planned-expenses/{id}` | Annuler |

Une dépense personnelle prévue ou engagée est déduite. Si elle est payée après le dernier instantané de solde, elle reste déduite jusqu'à la prochaine saisie du solde ; si elle est payée avant l'instantané, elle est exclue. Une dépense commune hors courses est répartie et agrégée dans la participation au foyer. Une dépense commune de courses consomme uniquement le budget courses.

## 9. Budget courses du foyer

| Méthode | Route | Description |
|---|---|---|
| GET | `/households/{household_id}/grocery-budget?period=YYYY-MM` | Lire l'enveloppe et le consommé |
| PATCH | `/households/{household_id}/grocery-budget` | Modifier le montant de référence |
| GET | `/households/{household_id}/grocery-budget/transactions` | Historique des achats |

Valeur initiale : 49 000 centimes par mois. Répartition de contribution de référence : 55 % / 45 %, soit 269,50 € / 220,50 €. Le budget est remis à zéro chaque mois, sans report.

Une transaction commune de catégorie courses diminue le budget restant d'une seule fois. Elle n'est jamais incluse dans les dépenses personnelles ni dans la déduction personnelle du disponible.

## 10. Répartition

| Méthode | Route | Description |
|---|---|---|
| GET | `/households/{household_id}/allocation-rules` | Lire les répartitions |
| PUT | `/households/{household_id}/allocation-rules/default` | Définir 55/45 ou autre |
| PUT | `/recurring-expenses/{id}/allocation-rule` | Définir une exception |

Chaque règle contient un pourcentage par membre et doit totaliser exactement 100 %. Les règles spécifiques priment sur la règle par défaut. Les changements s'appliquent aux échéances futures, sans recalcul silencieux de l'historique.

## 11. Réponses et erreurs

Les ressources retournées ne contiennent que les champs autorisés. Utiliser des codes HTTP standards (200, 201, 204, 400, 401, 403, 404, 409, 422, 500) et un corps d'erreur stable avec `code`, `message`, `details` et `request_id`.

