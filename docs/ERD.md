# Diagramme entité-association — Suivi des dépenses

**Version :** 0.5  
**Référence :** DATA_MODEL.md v0.4  
**Statut :** Diagramme conceptuel aligné sur le périmètre fonctionnel

## Diagramme

```mermaid
erDiagram
    USERS ||--o{ HOUSEHOLD_MEMBERS : belongs
    HOUSEHOLDS ||--o{ HOUSEHOLD_MEMBERS : contains
    USERS ||--o{ PERSONAL_BALANCE_ENTRIES : records
    USERS ||--o{ HOUSEHOLD_CONTRIBUTIONS : pays
    HOUSEHOLDS ||--o{ HOUSEHOLD_CONTRIBUTIONS : receives
    USERS ||--o{ TRANSACTIONS : creates
    HOUSEHOLDS ||--o{ TRANSACTIONS : owns_shared
    CATEGORIES ||--o{ TRANSACTIONS : classifies
    CATEGORIES ||--o{ RECURRING_EXPENSES : classifies
    USERS ||--o{ RECURRING_EXPENSES : owns
    HOUSEHOLDS o|--o{ RECURRING_EXPENSES : shared
    RECURRING_EXPENSES ||--o{ RECURRING_OCCURRENCES : schedules
    RECURRING_OCCURRENCES o|--o| TRANSACTIONS : paid_by
    USERS ||--o{ PLANNED_EXPENSES : creates
    HOUSEHOLDS o|--o{ PLANNED_EXPENSES : shared
    BUDGETS ||--o{ BUDGET_PERIODS : periods
    BUDGETS o|--o{ TRANSACTIONS : consumes
    HOUSEHOLDS ||--o{ BUDGETS : owns
    HOUSEHOLDS ||--o{ ALLOCATION_RULES : configures
    ALLOCATION_RULES ||--|{ ALLOCATION_RULE_MEMBERS : splits
    USERS ||--o{ ALLOCATION_RULE_MEMBERS : participates

    USERS {
      uuid id PK
      varchar email UK
    }
    HOUSEHOLDS {
      uuid id PK
      varchar name
      varchar currency
      varchar timezone
    }
    HOUSEHOLD_MEMBERS {
      uuid id PK
      uuid household_id FK
      uuid user_id FK
      varchar role
    }
    HOUSEHOLD_CONTRIBUTIONS {
      uuid id PK
      uuid household_id FK
      uuid user_id FK
      date period_start
      bigint amount_cents
      numeric allocation_percentage
      varchar status
      timestamptz transferred_at
    }
    PERSONAL_BALANCE_ENTRIES {
      uuid id PK
      uuid user_id FK
      bigint balance_cents
      timestamptz recorded_at
    }
    CATEGORIES {
      uuid id PK
      uuid household_id FK
      varchar name
      boolean is_grocery
    }
    TRANSACTIONS {
      uuid id PK
      uuid household_id FK
      uuid user_id FK
      uuid category_id FK
      uuid budget_id FK
      bigint amount_cents
      varchar scope
      varchar transaction_type
      date transaction_date
      timestamptz paid_at
    }
    RECURRING_EXPENSES {
      uuid id PK
      uuid household_id FK
      uuid owner_user_id FK
      uuid category_id FK
      bigint amount_cents
      varchar scope
      varchar frequency
    }
    RECURRING_OCCURRENCES {
      uuid id PK
      uuid recurring_expense_id FK
      uuid transaction_id FK
      date due_date
      varchar status
    }
    PLANNED_EXPENSES {
      uuid id PK
      uuid household_id FK
      uuid user_id FK
      uuid category_id FK
      bigint amount_cents
      varchar scope
      date planned_date
      varchar status
    }
    BUDGETS {
      uuid id PK
      uuid household_id FK
      varchar name
      bigint default_amount_cents
    }
    BUDGET_PERIODS {
      uuid id PK
      uuid budget_id FK
      bigint allocated_amount_cents
      date period_start
      date period_end
    }
    ALLOCATION_RULES {
      uuid id PK
      uuid household_id FK
      varchar name
      boolean is_default
    }
    ALLOCATION_RULE_MEMBERS {
      uuid id PK
      uuid allocation_rule_id FK
      uuid user_id FK
      numeric percentage
    }
```

## Contraintes métier structurantes

1. Le foyer possède deux membres distincts.
2. Le solde suivi est personnel, manuel et historisé ; aucun compte joint n'est modélisé.
3. Une charge récurrente est personnelle ou commune.
4. Une charge commune est répartie par règle par défaut 55/45, ou par règle spécifique totalisant 100 %.
5. La participation au foyer inclut les charges communes et la contribution au budget courses ; son virement est suivi par mois et par membre.
6. Le solde manuel est un instantané daté : toute sortie postérieure reste déduite, même si elle est marquée payée, jusqu'à une nouvelle saisie du solde.
7. Les achats de courses communes sont imputés au budget courses du foyer (490 € par défaut), jamais au disponible personnel.
8. Une occurrence récurrente payée référence une transaction ; une échéance ne peut être générée deux fois.
9. Le disponible prévisionnel ne prend aucun revenu futur en compte.
10. Les sommes sont en centimes entiers et les périodes budgétaires sont mensuelles sans report.
