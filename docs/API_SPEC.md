# Spécification API REST — Suivi des dépenses

**Version :** 0.2  
**Statut :** Proposition technique à valider  
**Base URL :** `/api/v1`  
**Backend cible :** FastAPI / Pydantic v2  
**Format :** JSON UTF-8  
**Référence de données :** `docs/ERD.md` v0.3

Ce document définit les routes, les paramètres, les contrats JSON et les règles de comportement de l'API. Les exemples sont illustratifs ; les schémas Pydantic définitifs seront implémentés après validation de cette spécification.

## 1. Conventions générales

### 1.1 Format des réponses

- Les dates métier utilisent le format ISO 8601 `YYYY-MM-DD`.
- Les horodatages utilisent ISO 8601 avec fuseau horaire, en UTC dans les réponses.
- Les montants sont toujours des entiers en centimes : `amount_cents: 1299` signifie 12,99 €.
- Les pourcentages sont des nombres décimaux exprimés en points de pourcentage : `45.0000` signifie 45 %.
- Les identifiants sont des UUID.
- Les propriétés inconnues ou non autorisées ne sont jamais renvoyées.
- Les champs absents et les champs explicitement à `null` ont des significations distinctes selon le schéma.

### 1.2 Ressources et enveloppes

Les réponses d'une ressource unique utilisent directement un objet JSON. Les listes utilisent une enveloppe paginée :

```json
{
  "items": [],
  "pagination": {
    "page": 1,
    "page_size": 25,
    "total_items": 0,
    "total_pages": 0
  }
}
```

Les listes sont triées de manière déterministe. Le tri par défaut est généralement `created_at DESC` ou la date métier décroissante.

### 1.3 Pagination, filtres et tri

- Pagination par `page` (défaut 1) et `page_size` (défaut 25, maximum 100).
- Les filtres sont transmis en query parameters.
- Les dates de début et de fin sont inclusives.
- Le tri est limité à une liste blanche de champs définie par ressource.
- Les filtres de périmètre n'accordent jamais de droits supplémentaires.

### 1.4 Format des erreurs

Toutes les erreurs applicatives suivent le même format :

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Les données envoyées sont invalides.",
    "details": [
      {
        "field": "amount_cents",
        "issue": "must_be_positive"
      }
    ],
    "request_id": "8f2e..."
  }
}
```

Codes HTTP usuels :

| Code | Usage |
|---|---|
| 200 | Lecture ou mise à jour réussie |
| 201 | Ressource créée |
| 202 | Traitement asynchrone accepté |
| 204 | Suppression réussie sans contenu |
| 400 | Requête métier invalide |
| 401 | Non authentifié |
| 403 | Authentifié mais non autorisé |
| 404 | Ressource absente ou non accessible |
| 409 | Conflit d'état ou doublon |
| 422 | Validation du schéma d'entrée |
| 429 | Limite de requêtes atteinte |
| 500 | Erreur interne générique |

Ne pas révéler par une différence de réponse l'existence d'une ressource personnelle appartenant à un autre utilisateur : utiliser 404 pour une ressource hors périmètre.

### 1.5 Versionnement et compatibilité

Les routes sont préfixées par `/api/v1`. Toute modification incompatible nécessite une nouvelle version majeure de l'API. Les changements additifs peuvent être intégrés à la version courante.

## 2. Authentification et compte

### 2.1 Stratégie de session

Pour la PWA, proposition d'une authentification par cookies de session sécurisés :
- cookie de session `HttpOnly`, `Secure`, `SameSite` adapté au déploiement ;
- protection CSRF sur les requêtes modifiant les données ;
- expiration et révocation des sessions côté serveur ;
- mots de passe hachés avec un algorithme adapté (Argon2id recommandé).

Les cookies ne sont jamais accessibles au JavaScript de l'application. Les endpoints de connexion, déconnexion et rafraîchissement sont limités en fréquence.

### 2.2 Routes

| Méthode | Route | Description |
|---|---|---|
| POST | `/auth/register` | Créer un compte |
| POST | `/auth/login` | Ouvrir une session |
| POST | `/auth/logout` | Fermer la session |
| POST | `/auth/refresh` | Renouveler la session si nécessaire |
| GET | `/auth/me` | Utilisateur connecté et contexte courant |
| PATCH | `/users/me` | Modifier les informations du compte |
| POST | `/users/me/change-password` | Changer le mot de passe |

L'inscription peut être désactivée après création des deux comptes initiaux. L'ajout d'un utilisateur à un foyer doit nécessiter une invitation ou une action administrative explicite.

### 2.3 Exemple — Connexion

Requête :

```json
{
  "email": "personne@example.com",
  "password": "mot-de-passe"
}
```

Réponse `200` :

```json
{
  "user": {
    "id": "0d5c5f25-82d2-4db6-a17b-9b6e16b9a2b3",
    "email": "personne@example.com",
    "first_name": "Alex"
  },
  "households": [
    {
      "id": "e07b53c6-3e45-4f34-99b9-6f6a0f60c2d8",
      "name": "Notre foyer",
      "role": "member"
    }
  ]
}
```

Les cookies de session sont posés dans les en-têtes HTTP, pas dans le corps JSON.

## 3. Foyer et confidentialité

### 3.1 Foyer

| Méthode | Route | Description |
|---|---|---|
| GET | `/households` | Lister les foyers de l'utilisateur |
| GET | `/households/{household_id}` | Détail d'un foyer |
| PATCH | `/households/{household_id}` | Modifier le nom ou les paramètres non sensibles |
| GET | `/households/{household_id}/members` | Lister les membres et leurs droits visibles |

La V1 utilise un foyer partagé par les deux utilisateurs. Toute route de foyer vérifie l'appartenance active de l'utilisateur.

### 3.2 Confidentialité financière

| Méthode | Route | Description |
|---|---|---|
| GET | `/users/me/privacy-settings` | Lire ses préférences |
| PUT | `/users/me/privacy-settings` | Remplacer ses préférences |

Contrat :

```json
{
  "share_income_amount": false,
  "allow_income_for_allocation": true,
  "share_allocation_percentage": true,
  "share_allocation_amount": true
}
```

Ces paramètres sont globaux par utilisateur, et non propres à un foyer. Un utilisateur ne peut lire ou modifier que ses propres paramètres.

Le backend applique les règles de confidentialité avant la sérialisation. Les revenus privés et leurs valeurs ne doivent pas être envoyés au frontend pour y être masqués.

## 4. Tableau de bord

| Méthode | Route | Description |
|---|---|---|
| GET | `/households/{household_id}/dashboard` | Vue agrégée du foyer |
| GET | `/users/me/dashboard` | Vue personnelle |

Paramètres : `period=YYYY-MM` obligatoire ou valeur par défaut correspondant au mois courant dans le fuseau du foyer.

Exemple de réponse foyer :

```json
{
  "period": "2026-11",
  "currency": "EUR",
  "shared": {
    "expenses_cents": 125430,
    "grocery_budget_cents": 49000,
    "grocery_spent_cents": 32750,
    "grocery_remaining_cents": 16250,
    "grocery_usage_percentage": 66.84
  },
  "allocation": {
    "status": "finalized",
    "total_charges_cents": 210000,
    "members": [
      {
        "user_id": "0d5c5f25-82d2-4db6-a17b-9b6e16b9a2b3",
        "percentage": 45.0,
        "allocated_amount_cents": 94500
      }
    ]
  }
}
```

Les montants et pourcentages d'un membre ne sont présents que si les paramètres de confidentialité de ce membre les autorisent. Le statut de calcul et les agrégats non sensibles peuvent rester visibles même si certaines données individuelles sont masquées.

La vue personnelle ne contient que les transactions, budgets et revenus personnels de l'utilisateur, ainsi que les parts communes qu'il est autorisé à consulter.

## 5. Transactions

### 5.1 Routes

| Méthode | Route | Description |
|---|---|---|
| GET | `/transactions` | Lister les transactions accessibles |
| POST | `/transactions` | Créer une transaction |
| GET | `/transactions/{transaction_id}` | Détail |
| PATCH | `/transactions/{transaction_id}` | Modifier une transaction |
| DELETE | `/transactions/{transaction_id}` | Suppression logique |
| GET | `/transactions/{transaction_id}/refunds` | Lister les remboursements liés |

Filtres de liste :
- `scope=personal|shared`
- `transaction_type=expense|income|refund`
- `household_id`
- `category_id`
- `paid_by_user_id`
- `date_from`, `date_to`
- `search`
- `page`, `page_size`
- `sort`

Les filtres sont combinables. L'API ignore ou rejette un `household_id` qui n'appartient pas à l'utilisateur ; elle ne renvoie jamais les transactions d'un autre foyer.

### 5.2 Création

Requête :

```json
{
  "scope": "shared",
  "household_id": "e07b53c6-3e45-4f34-99b9-6f6a0f60c2d8",
  "paid_by_user_id": "0d5c5f25-82d2-4db6-a17b-9b6e16b9a2b3",
  "category_id": "6af1b947-fcc4-4c48-84e8-c4b6a2b7f0d1",
  "label": "Courses",
  "amount_cents": 7850,
  "transaction_type": "expense",
  "transaction_date": "2026-11-05",
  "payment_method": "card",
  "notes": null
}
```

Réponse `201` : ressource créée avec `id`, `user_id` (créateur), dates de création/modification et champs autorisés.

Règles :
- Le serveur déduit le créateur depuis la session ; le client ne peut pas définir `user_id`.
- Une transaction personnelle appartient à l'utilisateur connecté et ne comporte pas de `household_id`.
- Une transaction commune appartient à un foyer dont l'utilisateur est membre.
- `paid_by_user_id` doit désigner un membre actif du foyer pour une dépense commune.
- Le montant est strictement positif.
- Une transaction de type `refund` doit fournir `original_transaction_id`, qui doit référencer une dépense accessible et compatible.
- Le cumul des remboursements ne peut pas dépasser le montant remboursable de la dépense d'origine.
- Un remboursement reste une transaction indépendante et ne modifie pas la dépense d'origine.
- La suppression est logique ; une transaction déjà incluse dans un calcul définitif ne peut pas être supprimée ou modifiée sans procédure de correction auditée.

### 5.3 Contrat de réponse simplifié

```json
{
  "id": "2b41f4e1-7e8b-4d79-8e3d-c2b16a76f8d0",
  "scope": "shared",
  "household_id": "e07b53c6-3e45-4f34-99b9-6f6a0f60c2d8",
  "user_id": "0d5c5f25-82d2-4db6-a17b-9b6e16b9a2b3",
  "paid_by_user_id": "0d5c5f25-82d2-4db6-a17b-9b6e16b9a2b3",
  "category_id": "6af1b947-fcc4-4c48-84e8-c4b6a2b7f0d1",
  "original_transaction_id": null,
  "label": "Courses",
  "amount_cents": 7850,
  "transaction_type": "expense",
  "transaction_date": "2026-11-05",
  "created_at": "2026-11-05T08:30:00Z",
  "updated_at": "2026-11-05T08:30:00Z"
}
```

## 6. Catégories

| Méthode | Route | Description |
|---|---|---|
| GET | `/categories` | Lister les catégories système et celles du foyer |
| POST | `/categories` | Créer une catégorie personnalisée |
| PATCH | `/categories/{category_id}` | Modifier une catégorie personnalisée |
| DELETE | `/categories/{category_id}` | Désactiver une catégorie |

Une catégorie système est en lecture seule. Une catégorie déjà utilisée ne doit pas être supprimée physiquement. Le type de catégorie doit être cohérent avec le type de transaction ou de budget.

## 7. Budgets

| Méthode | Route | Description |
|---|---|---|
| GET | `/budgets` | Lister les budgets accessibles |
| POST | `/budgets` | Créer un budget personnel ou commun |
| GET | `/budgets/{budget_id}` | Détail du budget |
| PATCH | `/budgets/{budget_id}` | Modifier la configuration future |
| GET | `/budgets/{budget_id}/periods` | Lister les périodes |
| GET | `/budgets/{budget_id}/periods/{period_id}` | Détail d'une période |

Création :

```json
{
  "scope": "shared",
  "household_id": "e07b53c6-3e45-4f34-99b9-6f6a0f60c2d8",
  "category_id": "6af1b947-fcc4-4c48-84e8-c4b6a2b7f0d1",
  "name": "Courses",
  "budget_type": "category",
  "default_amount_cents": 49000
}
```

Règles :
- Un budget est personnel ou commun, jamais les deux.
- La période est mensuelle et figée à sa création.
- Aucune somme restante n'est reportée au mois suivant.
- Les transactions éligibles sont agrégées, sans duplication.
- Une modification de budget ne réécrit pas les périodes clôturées.
- Les périodes sont générées à la demande ou par une tâche planifiée idempotente.

## 8. Dépenses récurrentes et occurrences

| Méthode | Route | Description |
|---|---|---|
| GET | `/recurring-expenses` | Lister les définitions |
| POST | `/recurring-expenses` | Créer une définition |
| GET | `/recurring-expenses/{recurring_expense_id}` | Détail |
| PATCH | `/recurring-expenses/{recurring_expense_id}` | Modifier pour les occurrences futures |
| POST | `/recurring-expenses/{recurring_expense_id}/deactivate` | Désactiver |
| GET | `/recurring-expenses/{recurring_expense_id}/occurrences` | Lister les occurrences |
| POST | `/recurring-occurrences/{occurrence_id}/confirm` | Confirmer le montant |
| POST | `/recurring-occurrences/{occurrence_id}/pay` | Créer la transaction et marquer payée |
| POST | `/recurring-occurrences/{occurrence_id}/skip` | Ignorer une occurrence |

Fréquences autorisées : `weekly`, `monthly`, `quarterly`, `semiannual`, `yearly`.

Contrat de création :

```json
{
  "scope": "shared",
  "household_id": "e07b53c6-3e45-4f34-99b9-6f6a0f60c2d8",
  "category_id": "6af1b947-fcc4-4c48-84e8-c4b6a2b7f0d1",
  "label": "Électricité",
  "amount_cents": null,
  "frequency": "monthly",
  "start_date": "2026-11-01",
  "end_date": null,
  "day_of_month": 10,
  "amount_confirmation_required": true
}
```

Confirmation d'une occurrence :

```json
{
  "confirmed_amount_cents": 8430
}
```

Le endpoint `pay` accepte la date réelle de paiement, le payeur et les informations facultatives de transaction. La création de la transaction et le passage de l'occurrence à `paid` sont atomiques. Un endpoint appelé deux fois ne crée jamais deux transactions : il renvoie la transaction existante ou une erreur 409 documentée.

Les occurrences non confirmées ne sont pas comptabilisées comme dépenses réelles. Une définition modifiée ne change pas les occurrences passées.

## 9. Revenus servant à la répartition

| Méthode | Route | Description |
|---|---|---|
| GET | `/incomes` | Lister les revenus déclarés accessibles |
| POST | `/incomes` | Déclarer un revenu |
| GET | `/incomes/{income_id}` | Détail autorisé |
| PATCH | `/incomes/{income_id}` | Modifier un revenu futur |
| DELETE | `/incomes/{income_id}` | Désactiver/supprimer logiquement un revenu |

Contrat :

```json
{
  "scope": "personal",
  "household_id": "e07b53c6-3e45-4f34-99b9-6f6a0f60c2d8",
  "label": "Salaire",
  "amount_cents": 220000,
  "income_type": "salary",
  "period_start": "2026-11-01",
  "period_end": "2026-11-30"
}
```

Pour un revenu personnel, le propriétaire est toujours l'utilisateur connecté. Pour un revenu du foyer (ex. aide CAF), `user_id` est nul et le revenu est créé par un membre autorisé.

La valeur exacte d'un revenu personnel n'est retournée qu'à son propriétaire, sauf si celui-ci autorise son partage. Le paramètre `allow_income_for_allocation` détermine séparément son admissibilité dans le calcul. Les revenus déclarés sont une base de calcul ; ils ne constituent pas des transactions de trésorerie.

## 10. Règles de répartition et calcul mensuel

### 10.1 Règles

| Méthode | Route | Description |
|---|---|---|
| GET | `/households/{household_id}/allocation-rules` | Lister les règles |
| POST | `/households/{household_id}/allocation-rules` | Créer une règle |
| PATCH | `/allocation-rules/{rule_id}` | Modifier une règle pour l'avenir |
| POST | `/allocation-rules/{rule_id}/deactivate` | Désactiver |

Contrat de règle personnalisée :

```json
{
  "name": "Crédit voiture",
  "calculation_method": "custom_percentage",
  "effective_from": "2026-11-01",
  "effective_until": null,
  "targets": [
    {
      "target_type": "recurring_expense",
      "target_id": "9d5c5f25-82d2-4db6-a17b-9b6e16b9a2b3"
    }
  ],
  "members": [
    {
      "user_id": "0d5c5f25-82d2-4db6-a17b-9b6e16b9a2b3",
      "percentage": 0
    },
    {
      "user_id": "4b22d8f5-58bd-4a6a-93c4-b25d33acb4f1",
      "percentage": 100
    }
  ]
}
```

Une règle par défaut du foyer ne possède aucune cible. Une règle ciblée ne peut viser qu'une catégorie, une dépense récurrente ou une transaction. La somme des parts personnalisées doit être exactement égale à 100 %. Les règles sont datées ; leur historique ne peut pas être modifié rétroactivement.

Priorité d'application, de la plus spécifique à la plus générale :
1. règle ciblant la transaction ponctuelle ;
2. règle ciblant la dépense récurrente ;
3. règle ciblant la catégorie ;
4. règle par défaut du foyer.

Si plusieurs règles actives de même priorité correspondent à la même charge, le calcul est bloqué avec une erreur métier explicite jusqu'à résolution de l'ambiguïté.

### 10.2 Prévisions de charges

Les charges prévisionnelles sont distinctes des transactions réelles. Elles peuvent provenir :
- d'une occurrence de dépense récurrente ;
- d'une saisie manuelle sans transaction associée.

Elles sont utilisées dans le calcul de répartition prévisionnel du mois mais ne réduisent pas le budget consommé et ne sont pas affichées comme dépenses réellement payées.

| Méthode | Route | Description |
|---|---|---|
| GET | `/households/{household_id}/allocation-forecasts` | Lister les prévisions |
| POST | `/households/{household_id}/allocation-forecasts` | Créer une prévision manuelle |
| PATCH | `/allocation-forecasts/{forecast_id}` | Modifier avant finalisation |
| DELETE | `/allocation-forecasts/{forecast_id}` | Supprimer avant finalisation |

Contrat de création :

```json
{
  "label": "Assurance annuelle",
  "due_date": "2026-11-20",
  "amount_cents": 72000,
  "category_id": "6af1b947-fcc4-4c48-84e8-c4b6a2b7f0d1"
}
```

Les prévisions issues d'occurrences sont générées depuis ces dernières et ne doivent pas être créées une seconde fois manuellement.

### 10.3 Calcul définitif mensuel

| Méthode | Route | Description |
|---|---|---|
| POST | `/households/{household_id}/allocation-runs` | Calculer et finaliser la période |
| GET | `/households/{household_id}/allocation-runs/{period}` | Lire le calcul définitif |
| GET | `/allocation-runs/{run_id}/charges` | Détail des charges réparties |

Requête :

```json
{
  "period": "2026-11"
}
```

Le calcul :
1. rassemble les revenus admissibles et les charges réelles communes ainsi que les prévisions ;
2. applique les règles dans l'ordre de priorité défini ;
3. calcule les parts et répartit les centimes résiduels de manière déterministe ;
4. conserve les revenus de référence, règles appliquées, sources et résultats dans les snapshots ;
5. crée un seul calcul définitif pour le foyer et la période.

Une contrainte d'unicité empêche de créer un deuxième calcul définitif. Si le calcul existe déjà, l'API répond 409 `ALLOCATION_ALREADY_FINALIZED` et fournit l'identifiant du calcul existant si l'utilisateur est autorisé à le consulter.

Un calcul incomplet (revenu non admissible, règle absente ou ambiguë, charge non résolue) ne peut pas être finalisé. Il retourne une liste d'anomalies exploitable par le frontend. Une fois finalisé, le calcul est immuable ; toute correction suit un processus explicite, autorisé et audité.

Réponse simplifiée :

```json
{
  "id": "8a75e5d0-31ec-4b27-98a5-36e6dfd2a94d",
  "household_id": "e07b53c6-3e45-4f34-99b9-6f6a0f60c2d8",
  "period": "2026-11",
  "status": "finalized",
  "total_income_cents": 400000,
  "total_charges_cents": 210000,
  "created_at": "2026-11-05T08:30:00Z",
  "members": [
    {
      "user_id": "0d5c5f25-82d2-4db6-a17b-9b6e16b9a2b3",
      "percentage": 45.0,
      "allocated_amount_cents": 94500
    },
    {
      "user_id": "4b22d8f5-58bd-4a6a-93c4-b25d33acb4f1",
      "percentage": 55.0,
      "allocated_amount_cents": 115500
    }
  ]
}
```

Les champs `members.percentage` et `members.allocated_amount_cents` sont filtrés selon les préférences de confidentialité de chaque membre.

## 11. Import et export

### 11.1 Import

| Méthode | Route | Description |
|---|---|---|
| POST | `/imports` | Téléverser un CSV/XLSX et créer un lot |
| GET | `/imports/{batch_id}` | Lire le statut et le résultat |
| POST | `/imports/{batch_id}/preview` | Analyser et prévisualiser |
| POST | `/imports/{batch_id}/validate` | Valider et exécuter l'import |

Le téléversement utilise `multipart/form-data`. L'import passe par une prévisualisation et une validation explicite. Aucun enregistrement n'est créé avant validation. Les lignes rejetées comportent un numéro de ligne et un motif ; les valeurs sensibles ne sont pas écrites dans les logs.

### 11.2 Export

| Méthode | Route | Description |
|---|---|---|
| POST | `/exports` | Créer un export asynchrone |
| GET | `/exports/{export_id}` | Lire le statut et le lien de téléchargement |
| GET | `/exports/{export_id}/download` | Télécharger le fichier |

Contrat :

```json
{
  "export_type": "transactions",
  "file_type": "csv",
  "filters": {
    "scope": "shared",
    "date_from": "2026-01-01",
    "date_to": "2026-11-30"
  }
}
```

Les exports appliquent exactement les mêmes règles d'accès et de confidentialité que les endpoints de lecture. Les liens de téléchargement sont temporaires et protégés.

## 12. Notifications

| Méthode | Route | Description |
|---|---|---|
| GET | `/notifications` | Lister les notifications de l'utilisateur |
| PATCH | `/notifications/{notification_id}` | Marquer comme lue |
| POST | `/notifications/read-all` | Tout marquer comme lu |
| GET | `/users/me/notification-preferences` | Lire les préférences |
| PUT | `/users/me/notification-preferences` | Remplacer les préférences |

Les notifications sont personnelles. Une notification liée au foyer reste visible uniquement par son destinataire. Le push est best-effort selon les capacités du navigateur et du système.

## 13. Synchronisation et fonctionnement hors ligne

La V1 ne propose aucune écriture hors ligne. Le frontend consulte le cache local des dernières réponses obtenues en ligne.

L'API n'expose pas de endpoint de synchronisation bidirectionnelle. Les clients doivent :
- conserver uniquement les réponses autorisées pour l'utilisateur connecté ;
- invalider le cache lors d'une déconnexion ou d'un changement de compte ;
- rafraîchir les données au retour en ligne ;
- afficher la date de dernière synchronisation.

Les réponses contenant des données financières personnelles doivent utiliser des directives de cache HTTP privées et adaptées ; aucune donnée privée ne doit être mise en cache dans un cache partagé.

## 14. Sécurité, intégrité et observabilité

- Chaque requête authentifiée est rattachée à un utilisateur côté serveur.
- Les autorisations sont vérifiées dans la couche service/repository, pas uniquement dans les routes.
- Les identifiants de foyer fournis par le client ne constituent jamais une preuve d'appartenance.
- Les réponses ne doivent jamais divulguer l'existence de ressources personnelles inaccessibles.
- Les écritures financières utilisent des transactions SQL.
- Les opérations sensibles (paiement d'occurrence, finalisation d'allocation, import validé) sont atomiques.
- Les endpoints de création sensibles acceptent une clé `Idempotency-Key` afin d'éviter les doublons lors des retries.
- Les montants sont validés comme entiers strictement positifs ; les pourcentages sont bornés et validés.
- Les erreurs ne contiennent ni secrets, ni mots de passe, ni montants privés non autorisés.
- Chaque réponse porte un `request_id` corrélable aux logs.
- Les logs d'audit enregistrent l'acteur, l'entité, l'action et l'horodatage, sans contenu financier sensible inutile.

## 15. Endpoints hors périmètre V1

Ne sont pas prévus :
- connexion bancaire ou agrégation de comptes ;
- OCR de tickets ;
- catégorisation automatique par IA ;
- transferts entre comptes ;
- synchronisation d'écritures hors ligne ;
- gestion multi-devises.

## 16. Décisions techniques validées

1. **Session :** authentification par cookies de session sécurisés (`HttpOnly`, `Secure`, `SameSite` adapté) avec protection CSRF sur les requêtes d'écriture. Aucun jeton de session n'est stocké dans le stockage JavaScript.
2. **Inscription :** création des comptes par invitation uniquement. L'inscription publique est désactivée en V1. Le flux d'invitation devra prévoir un jeton aléatoire à usage unique, expirant, stocké sous forme hachée et invalidé après acceptation.
3. **Correction d'un calcul définitif :** une correction est une opération explicite, autorisée et auditée, avec motif obligatoire. Elle met à jour le résultat définitif courant sans permettre de modification silencieuse. L'audit conserve l'acteur, la date, le motif et l'identifiant du calcul concerné. Le fonctionnement doit rester cohérent avec la règle d'une seule version définitive courante par période.
4. **Prévisions :** les prévisions manuelles sont persistées comme ressources dédiées, modifiables et supprimables avant finalisation du calcul. Les prévisions issues de récurrences restent reliées à leurs occurrences. Les charges sont ensuite figées dans le snapshot du calcul définitif. Le modèle de données et l'ERD devront intégrer cette ressource dédiée.
5. **Solde personnel :** la définition métier du solde disponible reste hors contrat V1 tant qu'elle n'est pas précisément définie. L'API ne doit pas exposer un indicateur de solde calculé sur une hypothèse implicite. Le tableau de bord peut afficher les revenus et dépenses réels séparément.

---

**Fin — API_SPEC.md v0.2**
