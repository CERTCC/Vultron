"""
Fixtures for test/core/use_cases/triggers tests.

Import VulnerabilityCase so the vocabulary registry is populated before tests
run, preventing TinyDB from falling back to raw Documents.
"""

# noqa: F401 — imported for vocabulary registration side-effect
from vultron.wire.as2.vocab.objects.vulnerability_case import (  # noqa: F401
    VulnerabilityCase,
)
