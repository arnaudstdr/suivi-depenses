import os
from collections.abc import Iterator

import pytest

from tests.helpers import temporary_database, upgrade_database


@pytest.fixture(scope="session")
def test_database_url() -> str:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL non défini : tests PostgreSQL ignorés")
    return database_url


@pytest.fixture(scope="session")
def migrated_database_url(test_database_url: str) -> Iterator[str]:
    with temporary_database(test_database_url) as database_url:
        upgrade_database(database_url)
        yield database_url
