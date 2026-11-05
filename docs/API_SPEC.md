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
- Pourcentages en points de pourcentage, avec 3 décimales maximum (55.000 = 55 %), sérialisés en chaîne décimale pour préserver la précision.
- Les permissions sont vérifiées côté serveur.
- Les listes paginées acceptent `limit` (défaut 50, max 200) et `offset`, et renvoient `{items, total, limit, offset}`.
- Les erreurs suivent un format commun.

## 2. Authentification

| Méthode | Route | Description |
|---|---|---|
| GET | `/auth/csrf` | Obtenir le jeton CSRF et son cookie |
| POST | `/auth/login` | Connexion |
| POST | `/auth/logout` | Déconnexion |
| GET | `/auth/me` | Utilisateur courant, foyer et membres |
| PATCH | `/users/me` | Modifier son profil |
| GET | `/households/me` | Foyer courant et membres |
| POST | `/households/me/invitations` | Créer une invitation (propriétaire uniquement) |
| GET | `/households/me/invitations` | Lister les invitations (propriétaire uniquement) |
| POST | `/invitations/{token}/accept` | Accepter une invitation |

### Sessions et CSRF

- Session opaque stockée côté serveur : seul le hash SHA-256 du token est conservé. Cookie `suivi_session`, `HttpOnly`, `Secure` en production, `SameSite=Lax`, durée de 30 jours par défaut.
- Protection CSRF par double-submit : cookie `suivi_csrf` lisible par le frontend et en-tête `X-CSRF-Token` identique, obligatoire sur `login`, `logout`, `PATCH /users/me`, création d'invitation et acceptation d'invitation.
- Le frontend appelle `GET /auth/csrf` avant la première mutation. Le jeton est stable tant que le cookie existe.
- Toutes les réponses `/api/v1` sont renvoyées avec `Cache-Control: no-store`.

### Création de compte et invitations

La création du premier foyer et du compte propriétaire se fait hors HTTP, par la commande CLI documentée dans `backend/README.md`. Aucune route publique d'inscription n'existe.

Le propriétaire crée ensuite une invitation pour le second membre. Le token brut est renvoyé **une seule fois** dans la réponse de création ; seul son hash est stocké. L'invitation expire après 7 jours, est à usage unique et doit être acceptée avec l'email invité. L'acceptation crée l'utilisateur, l'appartenance au foyer et une session dans une transaction unique.

Codes d'erreur spécifiques : `invalid_credentials`, `invalid_invitation`, `invitation_pending`, `household_full`, `email_already_registered`, `csrf_failed`, `unauthorized`, `forbidden`, `no_household`.

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

Si `recorded_at` est omis, le serveur utilise l'instant courant.

### 3.1 Catégories

| Méthode | Route | Description |
|---|---|---|
| GET | `/categories` | Lister les catégories globales et du foyer |
| POST | `/categories` | Créer une catégorie du foyer |
| PATCH | `/categories/{id}` | Modifier le nom, l'icône ou le statut actif |

Les catégories globales sont en lecture seule. Les catégories du foyer ne peuvent pas dupliquer un nom global ou du foyer. Le caractère `is_grocery` est défini à la création et n'est pas modifiable.

## 4. Tableau de bord personnel

| Méthode | Route | Description |
|---|---|---|
| GET | `/users/me/dashboard?period=2026-11` | Synthèse personnelle |

La Phase 4 ne calcule que le mois courant. Un autre `period` renvoie `422 unsupported_period`.

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

La réponse complète contient aussi `deductions.total_cents`, `grocery_budget` et les listes `upcoming_recurring` et `recent_personal_transactions`. Les transactions liées à une occurrence récurrente, à une dépense prévue ou à un virement de participation sont exclues des déductions de transactions personnelles afin d'éviter un double comptage. Pour les éléments payés, le mois retenu est celui du paiement réel ; pour les éléments non payés, celui de l'échéance ou de la date prévue.

## 5. Participation au foyer

| Méthode | Route | Description |
|---|---|---|
| GET | `/households/me/allocation-rules` | Lire les règles de répartition |
| PUT | `/households/me/allocation-rules/default` | Définir la répartition par défaut (propriétaire) |
| PUT | `/recurring-expenses/{id}/allocation-rule` | Définir une règle spécifique à une charge commune |
| DELETE | `/recurring-expenses/{id}/allocation-rule` | Revenir à la règle par défaut |
| GET | `/households/me/contributions?period=YYYY-MM` | Lire les contributions de la période |
| GET | `/households/me/contributions/history?date_from=YYYY-MM&date_to=YYYY-MM` | Lire l'historique conservé des contributions |
| POST | `/households/me/contributions/{contribution_id}/mark-transferred` | Pointer son propre virement avec sa date et son montant réels |
| POST | `/households/me/contributions/{contribution_id}/correct-transfer` | Corriger explicitement un virement déjà pointé |

La règle par défaut contient 100 % pour le propriétaire tant qu'il est seul, puis passe à 55/45 à l'arrivée du second membre. Les pourcentages sont exprimés en points, totalisent exactement 100 et sont répartis au centime avec la méthode du plus fort reste. Une règle spécifique ne s'applique qu'à une charge récurrente commune.

La contribution mensuelle agrège la part du membre dans les charges communes et sa contribution au budget courses. Elle se pointe comme une échéance récurrente : le corps de la requête accepte `transferred_at`, `transferred_amount_cents` et une note facultative. Le serveur passe de `pending` à `transferred`, associe une transaction personnelle unique de catégorie « Participation au foyer » et journalise l'opération. Cette transaction est exclue des déductions de transactions personnelles pour éviter un double comptage. Le pointage est idempotent ; une correction ultérieure est explicite et auditée via `correct-transfer`, qui met à jour la contribution et sa transaction liée. Cette action ne modifie pas à elle seule le disponible : si le virement est postérieur au dernier instantané de solde, son montant reste déduit. Une nouvelle saisie du solde après le virement l'intègre et supprime alors la déduction, sans double comptage. Chaque membre ne peut pointer ou corriger que sa propre contribution.

Une contribution d'une période passée déjà matérialisée n'est plus recalculée : une modification de règle ne réécrit pas l'historique. L'endpoint `/history` expose les contributions conservées, filtrables par mois et paginées.

## 6. Transactions

| Méthode | Route | Description |
|---|---|---|
| GET | `/transactions` | Lister les dépenses accessibles |
| POST | `/transactions` | Créer une dépense |
| GET | `/transactions/{id}` | Détail |
| PATCH | `/transactions/{id}` | Modifier |
| DELETE | `/transactions/{id}` | Supprimer logiquement |

Filtres : `scope`, `category_id`, `date_from`, `date_to`, `status`, `search`. Pagination : `limit` et `offset`.

Si `paid_at` est omis à la création, le serveur utilise midi dans le fuseau du foyer pour la date de la transaction.

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
| GET | `/recurring-expenses/{id}/occurrences?period=YYYY-MM&status=...` | Échéances générées pour la période |
| POST | `/recurring-occurrences/{occurrence_id}/confirm-amount` | Confirmer le montant d'une échéance variable |
| POST | `/recurring-occurrences/{occurrence_id}/skip` | Ignorer une échéance avec motif facultatif |
| POST | `/recurring-occurrences/{occurrence_id}/mark-paid` | Pointer une échéance comme payée |
| POST | `/recurring-occurrences/{occurrence_id}/correct-payment` | Corriger explicitement un paiement déjà pointé |

Champs de création : `label`, `amount_cents`, `category_id`, `scope` (personal/shared), `frequency` (`weekly`, `monthly`, `quarterly`, `semiannual`, `yearly`), `start_date`, `end_date`, `due_day`, `amount_is_variable`. Une charge fixe exige `amount_cents`. Une règle de répartition spécifique peut être définie via `PUT /recurring-expenses/{id}/allocation-rule`.

Les occurrences sont générées de manière idempotente pour la période demandée, avec une contrainte d'unicité et une insertion `ON CONFLICT DO NOTHING`. La génération est déclenchée automatiquement à la lecture du tableau de bord et des contributions, ainsi que par la commande `python -m app.cli recurring generate --period YYYY-MM` pour une exécution planifiée. Le jour d'échéance est ramené au dernier jour du mois si nécessaire. Une charge désactivée ne génère plus de nouvelles occurrences.

Une charge commune est répartie selon les pourcentages configurés. La part de l'utilisateur connecté est agrégée avec les autres charges communes dans la ligne « Participation au foyer » du tableau de bord personnel. Les détails par charge sont accessibles dans l'écran Charges.

Le pointage d'une occurrence se fait explicitement après le paiement réel. Le corps de `POST /recurring-occurrences/{occurrence_id}/mark-paid` accepte `paid_at`, `payment_amount_cents` et une note facultative. Le serveur passe l'occurrence à `paid`, crée une transaction réelle liée de manière idempotente et journalise l'opération. Pour une charge variable, `payment_amount_cents` est obligatoire sauf si un montant a déjà été confirmé via `confirm-amount` ; pour une charge fixe, il est proposé à partir du montant attendu et peut être corrigé. Le montant payé après le dernier instantané de solde reste déduit du disponible jusqu'à une nouvelle saisie du solde. Une échéance déjà payée n'est pas repointée : la seconde demande renvoie l'occurrence existante. Toute correction passe par `correct-payment`, qui met à jour l'occurrence et la transaction liée dans la même transaction SQL et journalise les anciennes et nouvelles valeurs. Une occurrence `skipped` est exclue des déductions et des contributions ; elle conserve son motif et son horodatage. Une transaction liée à une occurrence, une dépense prévue ou une contribution ne peut pas être modifiée ou supprimée directement via `/transactions` : la correction doit passer par l'élément source.

## 8. Dépenses ponctuelles prévues

| Méthode | Route | Description |
|---|---|---|
| GET | `/planned-expenses` | Lister |
| POST | `/planned-expenses` | Créer une prévision |
| PATCH | `/planned-expenses/{id}` | Modifier |
| POST | `/planned-expenses/{id}/mark-paid` | Marquer payée |
| POST | `/planned-expenses/{id}/correct-payment` | Corriger explicitement un paiement déjà pointé |
| DELETE | `/planned-expenses/{id}` | Annuler |

Statuts disponibles : `planned`, `committed`, `paid`, `cancelled`. Les statuts `planned` et `committed` sont déduits. Une dépense personnelle prévue ou engagée est déduite. Si elle est payée après le dernier instantané de solde, elle reste déduite jusqu'à la prochaine saisie du solde ; si elle est payée avant l'instantané, elle est exclue. Une dépense commune hors courses est répartie et agrégée dans la participation au foyer. Une dépense commune de courses consomme uniquement le budget courses au moment du paiement.

`POST /planned-expenses/{id}/mark-paid` accepte `paid_at`, `payment_amount_cents` facultatif et une note. Le pointage est idempotent et crée une transaction liée. `DELETE /planned-expenses/{id}` annule la dépense ; une dépense déjà payée ne peut pas être annulée. `POST /planned-expenses/{id}/correct-payment` corrige explicitement le montant et la date d'une dépense payée en mettant à jour sa transaction liée, avec audit des valeurs précédentes.

## 9. Budget courses du foyer

| Méthode | Route | Description |
|---|---|---|
| GET | `/households/me/grocery-budget?period=YYYY-MM` | Lire l'enveloppe et le consommé |
| PATCH | `/households/me/grocery-budget` | Modifier le montant de référence (propriétaire) |
| GET | `/households/me/grocery-budget/transactions?period=YYYY-MM` | Historique des achats |

Le budget courses est créé à 49 000 centimes au bootstrap du foyer. Sa période mensuelle est créée à la demande ; aucun reliquat n'est reporté. Une modification du montant de référence s'applique à la période courante ouverte et aux périodes futures.

Valeur initiale : 49 000 centimes par mois. Répartition de contribution de référence : 55 % / 45 %, soit 269,50 € / 220,50 €. Le budget est remis à zéro chaque mois, sans report.

Une transaction commune de catégorie courses diminue le budget restant d'une seule fois. Elle n'est jamais incluse dans les dépenses personnelles ni dans la déduction personnelle du disponible.

## 10. Répartition

| Méthode | Route | Description |
|---|---|---|
| GET | `/households/{household_id}/allocation-rules` | Lire les répartitions |
| PUT | `/households/{household_id}/allocation-rules/default` | Définir 55/45 ou autre |
| PUT | `/recurring-expenses/{id}/allocation-rule` | Définir une exception |

Chaque règle contient un pourcentage par membre. Avec deux membres, la somme doit totaliser exactement 100 %. Avec un seul membre, une part inférieure à 100 % est acceptée ; la part non attribuée n'est pas suivie dans les contributions. Les règles spécifiques priment sur la règle par défaut. Les changements s'appliquent aux échéances futures, sans recalcul silencieux de l'historique.

Lorsque le second membre rejoint le foyer, la part personnalisée du premier membre est conservée et le complément est attribué au second. Si la règle était restée à 100 %, elle devient automatiquement 55/45.

## 11. Réponses et erreurs

Les ressources retournées ne contiennent que les champs autorisés. Utiliser des codes HTTP standards (200, 201, 204, 400, 401, 403, 404, 409, 422, 500) et un corps d'erreur stable avec `code`, `message`, `details` et `request_id`.

Exemple :

```json
{
  "code": "not_found",
  "message": "Not Found",
  "details": null,
  "request_id": "0e8aa9e0-13d8-4612-afb5-6973a41d7e1b"
}
```

Le même identifiant est renvoyé dans l'en-tête `X-Request-ID` et journalisé avec la requête. Les corps de validation ne renvoient pas les valeurs saisies.

## 12. Santé

Ces routes sont hors du préfixe `/api/v1` et ne révèlent aucune information d'infrastructure.

| Méthode | Route | Description |
|---|---|---|
| GET | `/health/live` | Le processus répond |
| GET | `/health/ready` | PostgreSQL est joignable |

`/health/live` renvoie `200 {"status": "ok"}`. `/health/ready` renvoie `200 {"status": "ok"}` lorsque la base répond, sinon `503 {"status": "unavailable"}`.

## 13. Exports

| Méthode | Route | Description |
|---|---|---|
| GET | `/exports/transactions?format=csv\|xlsx&scope=all\|personal\|shared&date_from=...&date_to=...` | Exporter les transactions accessibles |
| GET | `/exports/contributions?format=csv\|xlsx&date_from=YYYY-MM&date_to=YYYY-MM` | Exporter l'historique des contributions |

Les exports sont synchrones en V1 : aucun traitement asynchrone ni table `export_jobs` n'est nécessaire tant que les volumes restent sous la limite configurée. La réponse est privée, en `Cache-Control: no-store`, avec `Content-Disposition: attachment`.

Permissions :

- un export personnel ne contient que les transactions personnelles de l'utilisateur connecté ;
- un export commun contient uniquement les transactions communes du foyer ;
- `scope=all` agrège les deux périmètres accessibles ;
- un export de contributions contient les contributions du foyer, sans donnée personnelle d'un autre foyer.

La limite `export_max_rows` (10 000 par défaut) protège la mémoire ; au-delà, la réponse est `422 export_too_large`. Les cellules texte sont neutralisées contre l'injection de formules dans les tableurs.

## 14. Imports

| Méthode | Route | Description |
|---|---|---|
| POST | `/imports/transactions/preview` | Téléverser un CSV/XLSX et obtenir une prévisualisation |
| GET | `/imports/{batch_id}` | Relire une prévisualisation ou son résultat |
| POST | `/imports/{batch_id}/validate` | Valider l'import de façon atomique |
| POST | `/imports/{batch_id}/cancel` | Annuler une prévisualisation |

Le téléversement est un `multipart/form-data` avec un champ `file` et un champ `scope` (`personal` ou `shared`). Formats acceptés : `.csv` et `.xlsx`. Colonnes obligatoires : `date`, `label`, `amount`, `category`. Colonne facultative : `notes`. Les colonnes supplémentaires sont ignorées.

- `date` accepte `YYYY-MM-DD` ou `JJ/MM/AAAA`.
- `amount` est un montant en euros, positif, avec au maximum deux décimales ; la conversion en centimes est exacte.
- `category` est résolu par nom parmi les catégories actives accessibles au foyer.
- Le fichier est limité par `import_max_bytes` (2 Mo par défaut) et `import_max_rows` (1 000 par défaut).
- Aucun fichier brut n'est conservé : la prévisualisation normalisée est stockée dans `import_batches.preview`, avec une expiration (`import_preview_ttl_seconds`, 24 h par défaut).

La prévisualisation ne crée aucune transaction. Chaque ligne est classée `valid`, `duplicate` ou `error` avec ses motifs. Un doublon est détecté sur `(date, montant, libellé insensible à la casse, catégorie)` dans le périmètre ciblé.

`POST /imports/{batch_id}/validate` accepte `duplicate_policy` (`skip` par défaut, ou `import`). Toutes les lignes valides sont insérées dans une seule transaction SQL ; les lignes en erreur sont ignorées et comptées. Une validation déjà effectuée renvoie le résultat existant sans réinsérer. Si une insertion échoue, aucune ligne du lot n'est conservée. L'import est audité par compteurs, sans contenu financier détaillé.

## 15. Notifications in-app

| Méthode | Route | Description |
|---|---|---|
| GET | `/notifications?unread_only=false` | Lister ses notifications |
| GET | `/notifications/unread-count` | Compter les non lues |
| POST | `/notifications/{id}/read` | Marquer une notification lue |
| POST | `/notifications/read-all` | Marquer toutes les notifications lues |
| GET | `/notifications/preferences` | Lire ses préférences par type |
| PUT | `/notifications/preferences` | Mettre à jour ses préférences |

Types initiaux : `invitation_accepted` et `import_completed`. Les préférences sont propres à chaque utilisateur et à chaque type ; `in_app_enabled` vaut `true` par défaut et `push_enabled` vaut `false`. Les notifications sont filtrées par destinataire : un utilisateur ne peut ni lire ni marquer la notification d'un autre.

Le Web Push est différé : le champ `push_enabled` est conservé pour la compatibilité future, mais aucun envoi push n'est effectué en V1.

## 16. En-têtes de sécurité HTTP

Toutes les réponses backend ajoutent :

- `X-Content-Type-Options: nosniff` ;
- `X-Frame-Options: DENY` ;
- `Referrer-Policy: no-referrer` ;
- `Permissions-Policy: geolocation=(), microphone=(), camera=()` ;
- `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'; base-uri 'none'` sur `/api/v1` et `/health` ;
- `Strict-Transport-Security: max-age=31536000; includeSubDomains` en production.

Les réponses `/api/v1` conservent `Cache-Control: no-store`. Le cache privé hors ligne est géré côté application, avec purge à la déconnexion et au changement de compte ; il ne s'appuie pas sur le cache HTTP.

