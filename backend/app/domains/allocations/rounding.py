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
    if total_percentage > Decimal("100"):
        raise ValueError("La somme des pourcentages ne peut pas dépasser 100.")
    if total_percentage <= Decimal("0"):
        return {user_id: 0 for user_id in percentages}

    # La part non attribuée (par exemple 45 % avec un seul membre) n'est pas
    # répartie : seuls les pourcentages explicitement définis sont alloués.
    assigned_total = int(
        (Decimal(amount_cents) * total_percentage / Decimal("100")).to_integral_value(
            rounding=ROUND_FLOOR
        )
    )
    exact = {
        user_id: (Decimal(assigned_total) * percentage / total_percentage)
        for user_id, percentage in percentages.items()
    }
    shares = {
        user_id: int(value.to_integral_value(rounding=ROUND_FLOOR))
        for user_id, value in exact.items()
    }
    remainder = assigned_total - sum(shares.values())
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
