# Backend — Suivi de dépenses

API FastAPI, SQLAlchemy 2 et Alembic, adossée à PostgreSQL.

## Prérequis

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- Docker et Docker Compose

## Installation

Depuis la racine du dépôt :

```bash
cp .env.example .env
docker compose up -d postgres
cd backend
uv sync
uv run alembic upgrade head
```

## Bootstrap du premier foyer

La création de compte est fermée en HTTP. Le premier foyer et son propriétaire
sont créés une seule fois par CLI, sur une base vide :

```bash
cd backend
uv run python -m app.cli bootstrap \
  --email owner@example.com \
  --first-name Alice \
  --household-name "Notre foyer"
```

La commande demande le mot de passe de façon interactive. Elle refuse un second
foyer, un email déjà utilisé ou un mot de passe de moins de 12 caractères.

## Démarrage

```bash
cd backend
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Alternative conteneurisée (PostgreSQL + API + frontend Nginx) :

```bash
make build   # depuis la racine du dépôt
make up      # build, migrations Alembic, PostgreSQL, API et frontend
make down    # arrêt sans suppression du volume PostgreSQL
```

Équivalent manuel :

```bash
docker compose --profile docker build api frontend
docker compose --profile docker run --rm api alembic upgrade head
docker compose --profile docker up -d api frontend
```

Endpoints disponibles :

- `GET /health/live` : le processus répond.
- `GET /health/ready` : PostgreSQL est joignable.
- `GET /docs` : documentation OpenAPI, si `DOCS_ENABLED=true`.

## Authentification et CSRF

Le parcours est le suivant :

1. `GET /api/v1/auth/csrf` : crée le cookie `suivi_csrf` et renvoie son jeton.
2. `POST /api/v1/auth/login` avec `X-CSRF-Token` : crée la session et le cookie
   `suivi_session`.
3. `GET /api/v1/auth/me` : renvoie l'utilisateur, le foyer et les membres.
4. `POST /api/v1/auth/logout` avec `X-CSRF-Token` : révoque la session.

Mutations protégées par CSRF : `login`, `logout`, `PATCH /users/me`, création
d'invitation et acceptation d'invitation. Le cookie de session est `HttpOnly`,
`Secure` en production, `SameSite=Lax` par défaut, et expire après 30 jours.

Le token de session et le token d'invitation ne sont jamais stockés en clair :
seul leur hash SHA-256 est conservé. Les tokens d'invitation sont retirés des
logs.

## Invitation du second membre

Le propriétaire crée une invitation :

```http
POST /api/v1/households/me/invitations
X-CSRF-Token: <jeton>
Content-Type: application/json

{"email": "membre@example.com"}
```

La réponse contient le token brut **une seule fois**, ainsi que `accept_path`.
Le second membre accepte avec l'email invité :

```http
POST /api/v1/invitations/<token>/accept
X-CSRF-Token: <jeton>
Content-Type: application/json

{
  "email": "membre@example.com",
  "first_name": "Bob",
  "password": "mot-de-passe-solide"
}
```

L'acceptation crée l'utilisateur, l'appartenance au foyer et une session dans
une transaction unique. L'invitation expire après 7 jours et ne peut être
utilisée qu'une fois. Le foyer est limité à deux membres actifs en V1.

## Suivi financier — tranche 4.1

La migration `0003_financial_core` ajoute :

- le solde personnel historisé ;
- les catégories globales et du foyer ;
- les transactions personnelles, communes et courses ;
- le budget courses et ses périodes mensuelles.

Le bootstrap crée les huit catégories globales et le budget courses initial de
49 000 centimes pour le foyer. Les foyers existants sont backfillés par la
migration.

Endpoints ajoutés :

- `GET/PUT /api/v1/users/me/personal-balance`
- `GET /api/v1/users/me/personal-balance/history`
- `GET/POST /api/v1/categories`
- `PATCH /api/v1/categories/{id}`
- `GET/POST /api/v1/transactions`
- `GET/PATCH/DELETE /api/v1/transactions/{id}`
- `GET/PATCH /api/v1/households/me/grocery-budget`
- `GET /api/v1/households/me/grocery-budget/transactions`

Règles principales :

- Une transaction personnelle n'a ni foyer ni budget.
- Une transaction commune de courses consomme automatiquement le budget courses.
- Une transaction commune hors courses n'a pas de budget ; sa quote-part sera
  intégrée à la participation en tranche 4.3.
- Une transaction personnelle n'est visible que par son propriétaire.
- Les remboursements sont des transactions distinctes liées à l'originale.
- La suppression est logique. Une dépense avec remboursements ne peut pas être
  supprimée.
- Les montants sont des centimes entiers stricts.

## Suivi financier — tranche 4.2

La migration `0004_forecast` ajoute :

- les dépenses ponctuelles prévues (`planned`, `committed`, `paid`, `cancelled`) ;
- les charges récurrentes et leurs occurrences ;
- le lien `transactions.recurring_occurrence_id`.

Endpoints ajoutés :

- `GET/POST /api/v1/planned-expenses`
- `GET/PATCH/DELETE /api/v1/planned-expenses/{id}`
- `POST /api/v1/planned-expenses/{id}/mark-paid`
- `GET/POST /api/v1/recurring-expenses`
- `GET/PATCH /api/v1/recurring-expenses/{id}`
- `POST /api/v1/recurring-expenses/{id}/deactivate`
- `GET /api/v1/recurring-expenses/{id}/occurrences?period=YYYY-MM`
- `POST /api/v1/recurring-occurrences/{id}/confirm-amount`
- `POST /api/v1/recurring-occurrences/{id}/skip`
- `POST /api/v1/recurring-occurrences/{id}/mark-paid`
- `POST /api/v1/recurring-occurrences/{id}/correct-payment`

Règles principales :

- Les occurrences sont générées de façon idempotente, y compris sous accès
  concurrent, avec unicité `(recurring_expense_id, due_date)`.
- Les fréquences `weekly`, `monthly`, `quarterly`, `semiannual` et `yearly` sont
  supportées. Un jour d'échéance trop grand est ramené au dernier jour du mois.
- Une charge fixe exige un montant. Une charge variable exige un montant réel
  au pointage, sauf si un montant a déjà été confirmé.
- Le pointage crée une transaction dans la même transaction SQL et lie les deux
  enregistrements de façon unique. Un second pointage renvoie l'existant.
- Une dépense prévue payée crée aussi une transaction unique et idempotente.
- Une dépense prévue annulée ne peut plus être payée ; une dépense payée ne peut
  plus être annulée.
- Une charge récurrente désactivée ne génère plus de nouvelles occurrences.
- Les règles de répartition par charge restent en tranche 4.3.

## Suivi financier — tranche 4.3

La migration `0005_allocations` ajoute :

- les règles de répartition et leurs membres ;
- les contributions mensuelles au foyer ;
- le lien `recurring_expenses.allocation_rule_id` ;
- la catégorie système « Participation au foyer ».

Endpoints ajoutés :

- `GET /api/v1/households/me/allocation-rules`
- `PUT /api/v1/households/me/allocation-rules/default`
- `PUT/DELETE /api/v1/recurring-expenses/{id}/allocation-rule`
- `GET /api/v1/households/me/contributions?period=YYYY-MM`
- `POST /api/v1/households/me/contributions/{id}/mark-transferred`

Règles principales :

- La règle par défaut vaut 100 % pour un membre seul, puis 55/45 à l'arrivée
  du second membre.
- Les pourcentages totalisent exactement 100 %. La répartition au centime
  utilise la méthode du plus fort reste.
- La contribution agrège la quote-part des charges communes non courses, les
  dépenses prévues communes et la contribution au budget courses.
- Une règle spécifique peut être liée à une charge récurrente commune.
- Le virement est pointé par le membre lui-même, de façon idempotente. Il crée
  une transaction personnelle « Participation au foyer » liée.
- Une contribution transférée est figée ; les nouvelles charges ne la modifient
  plus.

## Suivi financier — tranche 4.4

Le moteur de disponible prévisionnel est exposé par :

- `GET /api/v1/users/me/dashboard?period=YYYY-MM`

La Phase 4 ne calcule que le mois courant. L'endpoint renvoie :

- le dernier solde personnel et son instantané ;
- le détail des déductions (récurrent, prévu, transactions, participation) ;
- le disponible prévisionnel ;
- le budget courses alloué/consommé/restant ;
- les charges récurrentes à venir ;
- les dernières transactions personnelles.

Règles de calcul :

- Les éléments payés sont rattachés au mois du paiement réel, les éléments non
  payés au mois de leur échéance ou date prévue.
- Les transactions liées à une occurrence, une dépense prévue ou un virement de
  participation sont exclues des déductions de transactions personnelles.
- Une occurrence `skipped` et une dépense annulée sont exclues.
- Une contribution `pending` est déduite de son montant ; une contribution
  `transferred` est déduite si le virement est postérieur au dernier instantané
  de solde, et exclue sinon.
- Les achats de courses communes ne sont jamais déduits du disponible personnel.
- Une nouvelle saisie de solde réinitialise les déductions déjà reflétées.

## Phase 5 — récurrences et historique

La migration `0006_occurrence_history` ajoute `confirmed_at`, `skipped_at` et
`skip_reason` aux occurrences, ainsi qu'un index d'historique sur l'audit.

Endpoints ajoutés :

- `GET /api/v1/households/me/contributions/history`
- `POST /api/v1/households/me/contributions/{id}/correct-transfer`
- `POST /api/v1/planned-expenses/{id}/correct-payment`

Règles principales :

- La génération des échéances est déclenchée par la lecture du tableau de bord,
  des contributions et des occurrences. La commande
  `uv run python -m app.cli recurring generate --period YYYY-MM` permet une
  exécution planifiée, sans Celery ni Redis.
- Une occurrence variable peut être confirmée avant pointage. Le pointage
  utilise alors le montant confirmé si le montant réel n'est pas fourni.
- Une occurrence peut être ignorée avec un motif facultatif ; elle est exclue
  des déductions et des contributions.
- Un paiement d'occurrence, une dépense prévue payée ou un virement de
  contribution se corrige explicitement via son endpoint source. La correction
  met à jour la transaction liée dans la même transaction SQL et conserve les
  anciennes valeurs dans l'audit.
- Les transactions liées ne peuvent pas être modifiées ou supprimées via
  `/api/v1/transactions`.
- Une contribution d'une période passée déjà matérialisée est figée : une
  modification de règle ne réécrit pas l'historique.

## Phase 6 — import/export et notifications

La migration `0007_imports_notifications` ajoute `import_batches`,
`notifications` et `notification_preferences`.

Dépendances ajoutées : `python-multipart` (upload) et `openpyxl` (XLSX).

Endpoints ajoutés :

- `GET /api/v1/exports/transactions?format=csv|xlsx&scope=...`
- `GET /api/v1/exports/contributions?format=csv|xlsx`
- `POST /api/v1/imports/transactions/preview`
- `GET /api/v1/imports/{batch_id}`
- `POST /api/v1/imports/{batch_id}/validate`
- `POST /api/v1/imports/{batch_id}/cancel`
- `GET /api/v1/notifications`
- `GET /api/v1/notifications/unread-count`
- `POST /api/v1/notifications/{id}/read`
- `POST /api/v1/notifications/read-all`
- `GET/PUT /api/v1/notifications/preferences`

Règles principales :

- Les exports sont synchrones, filtrés par les permissions de lecture et
  renvoyés en `no-store`. La limite `EXPORT_MAX_ROWS` vaut 10 000 par défaut.
- L'import accepte CSV et XLSX, avec les colonnes `date`, `label`, `amount`,
  `category` et `notes` facultatif. Aucun fichier brut n'est conservé.
- La prévisualisation classe chaque ligne en `valid`, `duplicate` ou `error`.
  La validation est atomique et idempotente ; les doublons sont ignorés par
  défaut et peuvent être importés explicitement.
- Limites configurables : `IMPORT_MAX_BYTES` (2 Mo), `IMPORT_MAX_ROWS` (1 000)
  et `IMPORT_PREVIEW_TTL_SECONDS` (24 h).
- Les notifications in-app sont filtrées par destinataire. Les types
  `invitation_accepted` et `import_completed` sont créés automatiquement.
- Les préférences sont propres à chaque utilisateur et à chaque type. Le Web
  Push est différé ; `push_enabled` est conservé pour la suite.

## Phase 7 — sécurité HTTP

Toutes les réponses ajoutent `X-Content-Type-Options`, `X-Frame-Options`,
`Referrer-Policy` et `Permissions-Policy`. Les routes `/api/v1` et `/health`
ajoutent une CSP restrictive ; `Strict-Transport-Security` est ajouté en
production. Les réponses API restent en `Cache-Control: no-store`.

Le cache hors ligne privé est géré par le frontend, jamais par le service
worker sur `/api/v1`, et purgé à la déconnexion ou au changement de compte.

## Contrôles

```bash
cd backend
uv run ruff check .
uv run ruff format --check .
uv run mypy app
uv run pytest -q -m unit
TEST_DATABASE_URL=postgresql+psycopg://suivi:change-me-local-only@127.0.0.1:5432/suivi_depenses_test \
  uv run pytest -q
```

Les tests d'intégration créent et suppriment leurs propres bases temporaires à
partir de `TEST_DATABASE_URL`. L'utilisateur PostgreSQL doit donc pouvoir créer
des bases.

## Migrations

```bash
cd backend
uv run alembic upgrade head
uv run alembic current
uv run alembic check
uv run alembic revision --autogenerate -m "description"
```

- `0001_identity_core` : `users`, `households`, `household_members`.
- `0002_secure_auth` : `sessions`, `invitations`, `audit_logs`.

## Limites actuelles

- Pas d'envoi d'email : le token d'invitation est affiché au propriétaire.
- Pas de limitation de débit ni de verrouillage de compte sur les tentatives de
  connexion.
- Pas encore de révocation globale des sessions ni d'annulation d'invitation.
- Redis, Celery et le nettoyage planifié des sessions ne sont pas activés.
