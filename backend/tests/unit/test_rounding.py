from decimal import Decimal
from uuid import UUID

import pytest

from app.domains.allocations.rounding import split_amount, split_signed_amount

pytestmark = pytest.mark.unit

ALICE = UUID("00000000-0000-4000-8000-000000000001")
BOB = UUID("00000000-0000-4000-8000-000000000002")
PERCENTAGES = {
    ALICE: Decimal("55.000"),
    BOB: Decimal("45.000"),
}


def test_split_preserves_total_and_initial_ratio() -> None:
    shares = split_amount(10000, PERCENTAGES)

    assert shares == {ALICE: 5500, BOB: 4500}
    assert sum(shares.values()) == 10000


def test_split_uses_largest_remainder() -> None:
    shares = split_amount(10001, PERCENTAGES)

    assert sum(shares.values()) == 10001
    assert shares == {ALICE: 5501, BOB: 4500}


def test_split_one_cent() -> None:
    shares = split_amount(1, PERCENTAGES)

    assert sum(shares.values()) == 1
    assert shares == {ALICE: 1, BOB: 0}


def test_split_signed_amount() -> None:
    shares = split_signed_amount(-10001, PERCENTAGES)

    assert shares == {ALICE: -5501, BOB: -4500}


def test_split_with_three_members() -> None:
    percentages = {
        ALICE: Decimal("33.333"),
        BOB: Decimal("33.333"),
        UUID("00000000-0000-4000-8000-000000000003"): Decimal("33.334"),
    }

    shares = split_amount(100, percentages)

    assert sum(shares.values()) == 100


def test_split_rejects_total_above_hundred() -> None:
    with pytest.raises(ValueError):
        split_amount(1000, {ALICE: Decimal("80"), BOB: Decimal("40")})


def test_split_partial_single_member_leaves_remainder_unassigned() -> None:
    shares = split_amount(10000, {ALICE: Decimal("55")})

    assert shares == {ALICE: 5500}
    assert sum(shares.values()) == 5500


def test_split_partial_rounds_assigned_total_down() -> None:
    shares = split_amount(101, {ALICE: Decimal("55")})

    assert shares == {ALICE: 55}


def test_split_zero_percentage_assigns_nothing() -> None:
    assert split_amount(1000, {ALICE: Decimal("0")}) == {ALICE: 0}
