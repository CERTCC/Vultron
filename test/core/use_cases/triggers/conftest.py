"""
Fixtures for test/core/use_cases/triggers tests.

Import VulnerabilityCase so the vocabulary registry is populated before tests
run, preventing TinyDB from falling back to raw Documents.
"""

import pytest

# noqa: F401 — imported for vocabulary registration side-effect
from vultron.wire.as2.vocab.objects.vulnerability_case import (  # noqa: F401
    VulnerabilityCase,
)


@pytest.fixture
def datalayer():
    from vultron.adapters.driven.datalayer import (
        get_datalayer,
        reset_datalayer,
    )

    reset_datalayer()
    datalayer = get_datalayer(db_url="sqlite:///:memory:")
    datalayer.clear_all()
    yield datalayer
    datalayer.clear_all()
    reset_datalayer()
