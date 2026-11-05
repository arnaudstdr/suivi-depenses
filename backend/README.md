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

Alternative conteneurisée (PostgreSQL + API) :

```bash
docker compose --profile docker up -d --build api
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
- `POST /api/v1/recurring-occurrences/{id}/mark-paid`

Règles principales :

- Les occurrences sont générées à la demande pour une période, de façon
  idempotente, avec unicité `(recurring_expense_id, due_date)`.
- Les fréquences `weekly`, `monthly`, `quarterly`, `semiannual` et `yearly` sont
  supportées. Un jour d'échéance trop grand est ramené au dernier jour du mois.
- Une charge fixe exige un montant. Une charge variable exige un montant réel
  au pointage.
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
