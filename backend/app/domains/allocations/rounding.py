import uuid
from decimal import ROUND_FLOOR, Decimal


def split_amount(
    amount_cents: int,
    percentages: dict[uuid.UUID, Decimal],
) -> dict[uuid.UUID, int]:
    """Répartit un montant au centime avec la méthode du plus fort reste."""
    if not percentages:
        raise ValueError("Aucune répartition fournie.")
    total_percentage = sum(percentages.values(), Decimal("0"))
    if total_percentage != Decimal("100"):
        raise ValueError("La somme des pourcentages doit être égale à 100.")

    exact = {
        user_id: (Decimal(amount_cents) * percentage / Decimal("100"))
        for user_id, percentage in percentages.items()
    }
    shares = {
        user_id: int(value.to_integral_value(rounding=ROUND_FLOOR))
        for user_id, value in exact.items()
    }
    remainder = amount_cents - sum(shares.values())
    ranked = sorted(
        percentages,
        key=lambda user_id: (-(exact[user_id] - shares[user_id]), str(user_id)),
    )
    for user_id in ranked[:remainder]:
        shares[user_id] += 1
    return shares


def split_signed_amount(
    amount_cents: int,
    percentages: dict[uuid.UUID, Decimal],
) -> dict[uuid.UUID, int]:
    sign = 1 if amount_cents >= 0 else -1
    shares = split_amount(abs(amount_cents), percentages)
    return {user_id: sign * share for user_id, share in shares.items()}
