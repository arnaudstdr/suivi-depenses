import pytest
from sqlalchemy import create_engine, inspect

from tests.helpers import downgrade_database, temporary_database, upgrade_database

EXPECTED_TABLES = {
    "users",
    "households",
    "household_members",
    "sessions",
    "invitations",
    "audit_logs",
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

        engine.dispose()
