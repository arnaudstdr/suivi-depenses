import uuid

import pytest
from pydantic import ValidationError

from app.domains.balances.schemas import PersonalBalanceCreate
from app.domains.budgets.schemas import GroceryBudgetUpdate
from app.domains.transactions.schemas import TransactionCreate

pytestmark = pytest.mark.unit


def test_balance_rejects_float_amount() -> None:
    with pytest.raises(ValidationError):
        PersonalBalanceCreate(balance_cents=10.5)


def test_transaction_rejects_float_amount() -> None:
    with pytest.raises(ValidationError):
        TransactionCreate(
            label="Test",
            amount_cents=10.5,
            transaction_date="2026-11-05",
            category_id=uuid.uuid4(),
            scope="personal",
        )


def test_budget_rejects_float_amount() -> None:
    with pytest.raises(ValidationError):
        GroceryBudgetUpdate(default_amount_cents=49000.5)
