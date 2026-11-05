import pytest
from sqlalchemy import create_engine, inspect

from tests.helpers import downgrade_database, temporary_database, upgrade_database


@pytest.mark.integration
def test_initial_migration_is_reversible(test_database_url: str) -> None:
    with temporary_database(test_database_url) as database_url:
        engine = create_engine(database_url)

        upgrade_database(database_url)
        table_names = set(inspect(engine).get_table_names())
        assert {"users", "households", "household_members"} <= table_names

        downgrade_database(database_url)
        table_names = set(inspect(engine).get_table_names())
        assert "users" not in table_names
        assert "households" not in table_names
        assert "household_members" not in table_names

        upgrade_database(database_url)
        table_names = set(inspect(engine).get_table_names())
        assert {"users", "households", "household_members"} <= table_names

        engine.dispose()
