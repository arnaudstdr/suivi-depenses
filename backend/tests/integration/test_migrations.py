import uuid

import pytest
from sqlalchemy import create_engine, inspect, text

from tests.helpers import downgrade_database, temporary_database, upgrade_database

EXPECTED_TABLES = {
    "users",
    "households",
    "household_members",
    "sessions",
    "invitations",
    "audit_logs",
    "personal_balance_entries",
    "categories",
    "transactions",
    "budgets",
    "budget_periods",
    "planned_expenses",
    "recurring_expenses",
    "recurring_occurrences",
    "allocation_rules",
    "allocation_rule_members",
    "household_contributions",
    "import_batches",
    "notifications",
    "notification_preferences",
}


@pytest.mark.integration
def test_initial_migration_is_reversible(test_database_url: str) -> None:
    with temporary_database(test_database_url) as database_url:
        engine = create_engine(database_url)

        upgrade_database(database_url)
        table_names = set(inspect(engine).get_table_names())
        assert table_names >= EXPECTED_TABLES

        downgrade_database(database_url)
        table_names = set(inspect(engine).get_table_names())
        assert EXPECTED_TABLES.isdisjoint(table_names)

        upgrade_database(database_url)
        table_names = set(inspect(engine).get_table_names())
        assert table_names >= EXPECTED_TABLES

        engine.dispose()


@pytest.mark.integration
def test_secure_auth_migration_upgrades_previous_schema(test_database_url: str) -> None:
    with temporary_database(test_database_url) as database_url:
        engine = create_engine(database_url)

        upgrade_database(database_url, "0001_identity_core")
        table_names = set(inspect(engine).get_table_names())
        assert {"users", "households", "household_members"} <= table_names
        assert {"sessions", "invitations", "audit_logs"}.isdisjoint(table_names)

        upgrade_database(database_url, "head")
        table_names = set(inspect(engine).get_table_names())
        assert table_names >= EXPECTED_TABLES

        with engine.connect() as connection:
            category_count = connection.scalar(text("SELECT count(*) FROM categories"))
        assert category_count == 9

        engine.dispose()


@pytest.mark.integration
def test_financial_core_migration_upgrades_previous_schema(test_database_url: str) -> None:
    with temporary_database(test_database_url) as database_url:
        engine = create_engine(database_url)

        upgrade_database(database_url, "0002_secure_auth")
        table_names = set(inspect(engine).get_table_names())
        assert {"users", "sessions", "invitations", "audit_logs"} <= table_names
        assert {
            "personal_balance_entries",
            "categories",
            "transactions",
            "budgets",
            "budget_periods",
        }.isdisjoint(table_names)

        upgrade_database(database_url, "head")
        table_names = set(inspect(engine).get_table_names())
        assert table_names >= EXPECTED_TABLES

        with engine.connect() as connection:
            category_count = connection.scalar(text("SELECT count(*) FROM categories"))
        assert category_count == 9

        engine.dispose()


@pytest.mark.integration
def test_forecast_migration_upgrades_previous_schema(test_database_url: str) -> None:
    with temporary_database(test_database_url) as database_url:
        engine = create_engine(database_url)

        upgrade_database(database_url, "0003_financial_core")
        table_names = set(inspect(engine).get_table_names())
        assert {"transactions", "budgets", "budget_periods"} <= table_names
        assert {
            "planned_expenses",
            "recurring_expenses",
            "recurring_occurrences",
        }.isdisjoint(table_names)
        transaction_columns = {
            column["name"] for column in inspect(engine).get_columns("transactions")
        }
        assert "recurring_occurrence_id" not in transaction_columns

        upgrade_database(database_url, "head")
        table_names = set(inspect(engine).get_table_names())
        assert table_names >= EXPECTED_TABLES
        transaction_columns = {
            column["name"] for column in inspect(engine).get_columns("transactions")
        }
        assert "recurring_occurrence_id" in transaction_columns

        engine.dispose()


@pytest.mark.integration
def test_allocations_migration_upgrades_previous_schema(test_database_url: str) -> None:
    with temporary_database(test_database_url) as database_url:
        engine = create_engine(database_url)

        upgrade_database(database_url, "0004_forecast")
        table_names = set(inspect(engine).get_table_names())
        assert {
            "allocation_rules",
            "allocation_rule_members",
            "household_contributions",
        }.isdisjoint(table_names)
        recurring_columns = {
            column["name"] for column in inspect(engine).get_columns("recurring_expenses")
        }
        assert "allocation_rule_id" not in recurring_columns

        upgrade_database(database_url, "head")
        table_names = set(inspect(engine).get_table_names())
        assert table_names >= EXPECTED_TABLES
        recurring_columns = {
            column["name"] for column in inspect(engine).get_columns("recurring_expenses")
        }
        assert "allocation_rule_id" in recurring_columns

        with engine.connect() as connection:
            category_count = connection.scalar(text("SELECT count(*) FROM categories"))
        assert category_count == 9

        engine.dispose()


@pytest.mark.integration
def test_allocations_migration_backfills_default_rule(test_database_url: str) -> None:
    with temporary_database(test_database_url) as database_url:
        engine = create_engine(database_url)

        upgrade_database(database_url, "0004_forecast")

        household_id = uuid.uuid4()
        first_user_id = uuid.uuid4()
        second_user_id = uuid.uuid4()
        with engine.begin() as connection:
            for user_id, email in (
                (first_user_id, "first@example.com"),
                (second_user_id, "second@example.com"),
            ):
                connection.execute(
                    text(
                        """
                        INSERT INTO users (id, email, password_hash, first_name)
                        VALUES (CAST(:id AS uuid), :email, 'hash', 'Member')
                        """
                    ),
                    {"id": str(user_id), "email": email},
                )
            connection.execute(
                text(
                    """
                    INSERT INTO households (id, name)
                    VALUES (CAST(:id AS uuid), 'Foyer existant')
                    """
                ),
                {"id": str(household_id)},
            )
            for user_id in (first_user_id, second_user_id):
                connection.execute(
                    text(
                        """
                        INSERT INTO household_members (
                            id, household_id, user_id, role
                        )
                        VALUES (
                            CAST(:id AS uuid), CAST(:household_id AS uuid),
                            CAST(:user_id AS uuid), 'member'
                        )
                        """
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "household_id": str(household_id),
                        "user_id": str(user_id),
                    },
                )

        upgrade_database(database_url, "head")

        with engine.connect() as connection:
            percentages = [
                float(row.percentage)
                for row in connection.execute(
                    text(
                        """
                        SELECT arm.percentage
                        FROM allocation_rule_members arm
                        JOIN allocation_rules ar ON ar.id = arm.allocation_rule_id
                        WHERE ar.household_id = CAST(:household_id AS uuid)
                          AND ar.is_default
                        ORDER BY arm.percentage DESC
                        """
                    ),
                    {"household_id": str(household_id)},
                ).all()
            ]

        assert percentages == [55.0, 45.0]

        engine.dispose()


@pytest.mark.integration
def test_financial_migration_backfills_grocery_budget(test_database_url: str) -> None:
    with temporary_database(test_database_url) as database_url:
        engine = create_engine(database_url)

        upgrade_database(database_url, "0002_secure_auth")

        user_id = uuid.uuid4()
        household_id = uuid.uuid4()
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO users (id, email, password_hash, first_name)
                    VALUES (CAST(:id AS uuid), 'legacy@example.com', 'hash', 'Legacy')
                    """
                ),
                {"id": str(user_id)},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO households (id, name)
                    VALUES (CAST(:id AS uuid), 'Foyer existant')
                    """
                ),
                {"id": str(household_id)},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO household_members (id, household_id, user_id, role)
                    VALUES (CAST(:id AS uuid), CAST(:household_id AS uuid),
                            CAST(:user_id AS uuid), 'owner')
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "household_id": str(household_id),
                    "user_id": str(user_id),
                },
            )

        upgrade_database(database_url, "head")

        with engine.connect() as connection:
            budget = connection.execute(
                text(
                    """
                    SELECT default_amount_cents, category_id
                    FROM budgets
                    WHERE household_id = CAST(:household_id AS uuid)
                    """
                ),
                {"household_id": str(household_id)},
            ).one()

        assert budget.default_amount_cents == 49000
        assert str(budget.category_id) == "00000000-0000-4000-8000-000000000001"

        engine.dispose()
