"""Tests for the withdraw-embargo trigger (EP-09-013)."""

import pytest

from vultron.core.use_cases.triggers import embargo as embargo_triggers


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason=(
        "EP-09-013: no trigger sends Leave(EmbargoEvent) to withdraw from the "
        "embargo in force yet. Tracked by #4388."
    ),
)
@pytest.mark.spec("EP-09-013")
def test_a_withdraw_embargo_trigger_exists() -> None:
    """A signatory has a trigger, separate from reject, that withdraws it."""
    assert hasattr(embargo_triggers, "SvcWithdrawEmbargoUseCase")
