"""
Fixtures for test/core/behaviors/report tests.

Imports as_VulnerabilityCase (and related wire-layer types) as a side effect so
that the global vocabulary registry is populated before any test in this
directory runs.  Without this import the registry may be empty when tests run
in isolation, causing TinyDB's record_to_object() to fall back to returning a
raw Document instead of a deserialized domain object.
"""

import pytest

# noqa: F401 — imported for vocabulary registration side-effect
from vultron.wire.as2.vocab.objects.vulnerability_case import (  # noqa: F401
    as_VulnerabilityCase,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from vultron.semantic_registry import extract_event


@pytest.fixture
def case_with_participant(bt_scenario, report, actor) -> VulnerabilityCase:
    """A VulnerabilityCase in which ``actor`` is a participant at RM.RECEIVED.

    This is the shape a real case replica has once ``Create(VulnerabilityCase)``
    has been delivered to this actor's own store (ADR-0041, CBT-01-002): the case
    is present *and* the actor appears in ``actor_participant_index``.  Both
    halves are required for the case-scoped ``RM.VALID`` transition, so nodes and
    trees that reach RM.VALID need this fixture rather than a bare case
    (ISSUE-2548).  ``RM.RECEIVED`` is the state a receiver holds before
    ``validate-report`` runs, making ``RECEIVED → VALID`` a legal move.
    """
    obj = VulnerabilityCase(
        name="Test Case for TEST-001",
        vulnerability_reports=[report.id_],
        attributed_to=actor.id_,
    )
    participant = CaseParticipant(
        id_=f"{obj.id_}/participants/vendor",
        attributed_to=actor.id_,
        context=obj.id_,
        case_roles=[CVDRole.VENDOR],
    )
    participant.append_rm_state(RM.RECEIVED, actor.id_, obj.id_)
    obj.add_participant(participant)
    bt_scenario.dl.create(participant)
    bt_scenario.dl.create(obj)
    return obj


@pytest.fixture
def make_payload():
    """Return a helper that extracts a VultronEvent from an AS2 activity."""

    def _make_payload(activity, **extra_fields):
        event = extract_event(activity)
        if extra_fields:
            return event.model_copy(update=extra_fields)
        return event

    return _make_payload
