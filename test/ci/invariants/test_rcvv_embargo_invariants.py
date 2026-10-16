"""Case-ledger invariant tests for the RCVV embargo scenario.

Reads JSONL case-ledger replica files from ``devlogs/rcvv-embargo/`` and
asserts universal invariants (via the shared ``common`` library) plus
RCVV-embargo-specific checks.

Actor set: ``reporter``, ``coordinator``, ``vendor``, ``vendor2``,
``case-actor``.

RCVV-embargo-specific invariants (DEMOMA-21-007):

- the ledger records, in order, the embargo proposal, the owner's activation,
  the revision proposal and the owner's activation of the revision, under the
  event types the CASE_MANAGER's commit path emits.  The strings are imported
  from that code, never hand-listed here, so the check cannot drift from what
  the manager writes.  A proposal and a revision proposal share one event type,
  as do both of the owner's activations, so the order is checked on the
  entries of each type.
- the embargo is torn down exactly once, by the CS.P collapse (DEMOMA-21-004).
- ``invite_actor_to_case`` appears exactly twice (the two vendors; the Reporter
  is seated when the case is created and is never invited).
- ``close_case`` is present and the Vendor2 replica holds the whole log from
  genesis (it joined late).

All tests are tagged ``@pytest.mark.case_ledger_invariants``.  They skip
automatically when ``devlogs/rcvv-embargo/`` is absent.

Spec: DEMOMA-21, CLP-07.
"""

from __future__ import annotations

import pytest

from test.ci.invariants.common import (
    auth_entries,
    check_event_type_count,
    check_event_type_present,
    check_late_joiner_has_full_history,
    event_type,
    load_devlogs,
    log_index,
)
from test.ci.invariants.universal_harness import make_universal_invariant_tests
from vultron.core.behaviors.embargo.nodes import (
    EMBARGO_ACTIVATION_EVENT_TYPE,
    EMBARGO_INVITE_EVENT_TYPE,
    EMBARGO_TEARDOWN_EVENT_TYPE,
)
from vultron.core.models.events.base import MessageSemantics

_DEMO_NAME = "rcvv-embargo"

_ACCEPT_EVENT_TYPE = MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE.value
_ACTIVATE_EVENT_TYPE = EMBARGO_ACTIVATION_EVENT_TYPE

#: Expected protocol eventTypes in a complete RCVV-embargo run.
_RCVV_EMBARGO_EXPECTED_EVENT_TYPES = [
    pytest.param("validate_report", id="validate_report"),
    pytest.param(
        "add_participant_status_to_participant",
        id="add_participant_status_to_participant",
    ),
    pytest.param("close_case", id="close_case"),
    pytest.param("add_note_to_case", id="add_note_to_case"),
    # DEMOMA-16-001: universal — the shared RM-triage helpers engage the case.
    pytest.param("engage_case", id="engage_case"),
    pytest.param("invite_actor_to_case", id="invite_actor_to_case"),
    pytest.param(
        "accept_invite_actor_to_case", id="accept_invite_actor_to_case"
    ),
    # DEMOMA-21-007: the embargo lifecycle.  Spelled out because the notes
    # tables are ratcheted against this literal (ISSUE-3505);
    # test_rcvv_embargo_event_type_literals_match_the_commit_path pins each
    # string to the constant the CASE_MANAGER's commit path emits.
    pytest.param("invite_to_embargo_on_case", id="invite_to_embargo_on_case"),
    pytest.param(
        "accept_invite_to_embargo_on_case",
        id="accept_invite_to_embargo_on_case",
    ),
    pytest.param("activate_embargo_on_case", id="activate_embargo_on_case"),
    pytest.param(
        "remove_embargo_event_from_case", id="remove_embargo_event_from_case"
    ),
]

#: Actors with per-actor chain / contiguity / completeness checks.
_CHAIN_ACTORS = [
    pytest.param("case-actor"),
    pytest.param("coordinator"),
    pytest.param("vendor"),
    pytest.param("vendor2"),
    pytest.param("reporter"),
]


@pytest.fixture(scope="module")
def rcvv_embargo_replicas() -> dict[str, list[dict]]:
    """Load RCVV-embargo scenario JSONL files grouped by actor name."""
    return load_devlogs(demo_name=_DEMO_NAME)


globals().update(
    make_universal_invariant_tests(
        replicas_fixture="rcvv_embargo_replicas",
        chain_actors=_CHAIN_ACTORS,
        expected_event_types=_RCVV_EMBARGO_EXPECTED_EVENT_TYPES,
        narrative_path="docs/topics/scenarios/rcvv-embargo.md",
        joined_invitees=2,
    )
)


def test_rcvv_embargo_event_type_literals_match_the_commit_path() -> None:
    """The literals in the expected list are the strings the manager commits.

    DEMOMA-21-007 requires the invariant check to use the event types the
    CASE_MANAGER's commit path emits, read from the code.  The expected list
    must be a literal for the notes ratchet, so this pins it to the code.
    """
    listed = {p.values[0] for p in _RCVV_EMBARGO_EXPECTED_EVENT_TYPES}
    assert {
        EMBARGO_INVITE_EVENT_TYPE,
        _ACCEPT_EVENT_TYPE,
        _ACTIVATE_EVENT_TYPE,
        EMBARGO_TEARDOWN_EVENT_TYPE,
    } <= listed


@pytest.mark.case_ledger_invariants
def test_rcvv_embargo_proposal_then_revision_then_teardown_in_order(
    rcvv_embargo_replicas: dict[str, list[dict]],
) -> None:
    """Proposal, its activation, the revision, its activation, then teardown.

    A proposal and a revision proposal are both committed as the embargo
    Invite, so the order is read off the entries of each type: an Invite
    precedes the owner's first activation, a later Invite (the revision)
    follows it, a later activation (of the revision) follows that, and the
    teardown comes last.  The owner's activation has its own type,
    ``Accept(EmbargoEvent, target=Case)`` (ADR-0122), so this is the owner's
    decision, not a participant's consent; the participants' consent is
    asserted by the scenario (DEMOMA-21-002, DEMOMA-21-012).

    Spec: DEMOMA-21-007.
    """
    auth = auth_entries(rcvv_embargo_replicas)
    if not auth:
        pytest.skip("no authoritative log; cannot check embargo ordering")

    def indices(kind: str) -> list[int]:
        return sorted(log_index(e) for e in auth if event_type(e) == kind)

    invites = indices(EMBARGO_INVITE_EVENT_TYPE)
    accepts = indices(_ACTIVATE_EVENT_TYPE)
    teardowns = indices(EMBARGO_TEARDOWN_EVENT_TYPE)
    missing = [
        kind
        for kind, found in (
            (EMBARGO_INVITE_EVENT_TYPE, invites),
            (_ACTIVATE_EVENT_TYPE, accepts),
            (EMBARGO_TEARDOWN_EVENT_TYPE, teardowns),
        )
        if not found
    ]
    assert not missing, f"embargo event types never committed: {missing}"

    violations = []
    if not invites[0] < accepts[0]:
        violations.append(
            f"first proposal {invites[0]} does not precede the first"
            f" activation {accepts[0]}"
        )
    if not accepts[0] < invites[-1]:
        violations.append(
            f"no revision proposal after the first activation {accepts[0]}"
            f" (last proposal at {invites[-1]})"
        )
    if not invites[-1] < accepts[-1]:
        violations.append(
            f"the revision proposal {invites[-1]} is not followed by an"
            f" activation (last activation at {accepts[-1]})"
        )
    if not accepts[-1] < teardowns[0]:
        violations.append(
            f"teardown {teardowns[0]} does not follow the last activation"
            f" {accepts[-1]}"
        )
    assert not violations, "\n".join(violations)


@pytest.mark.case_ledger_invariants
def test_rcvv_embargo_torn_down_exactly_once(
    rcvv_embargo_replicas: dict[str, list[dict]],
) -> None:
    """The embargo collapses once, at CS.P, and is never ended deliberately.

    The Reporter's publication is the only thing that ends the embargo, so
    exactly one teardown is committed.

    Spec: DEMOMA-21-004, DEMOMA-21-014.
    """
    violations = check_event_type_count(
        rcvv_embargo_replicas,
        EMBARGO_TEARDOWN_EVENT_TYPE,
        min_count=1,
        max_count=1,
    )
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_rcvv_embargo_invite_actor_to_case_exactly_twice(
    rcvv_embargo_replicas: dict[str, list[dict]],
) -> None:
    """``invite_actor_to_case`` appears exactly twice (Vendor1 and Vendor2).

    The Reporter is seated as a participant when the case is created
    (CM-22-002), so only the two vendors are invited.

    Spec: DEMOMA-21-008 (phases 1 and 4).
    """
    violations = check_event_type_count(
        rcvv_embargo_replicas, "invite_actor_to_case", min_count=2, max_count=2
    )
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_rcvv_embargo_close_case_present(
    rcvv_embargo_replicas: dict[str, list[dict]],
) -> None:
    """``close_case`` event type is present in the log.

    Spec: DEMOMA-21-008 (phase 7).
    """
    violations = check_event_type_present(rcvv_embargo_replicas, "close_case")
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
@pytest.mark.parametrize("late_actor", ["vendor", "vendor2"])
def test_rcvv_embargo_vendor_late_joiner_has_full_history(
    rcvv_embargo_replicas: dict[str, list[dict]], late_actor: str
) -> None:
    """Each vendor replica contains every logIndex in the coordinator replica.

    Both vendors are invited after the case exists (Vendor2 only after the
    embargo revision) and must receive the full ledger backfill.

    Spec: DEMOMA-21-008 (phases 1 and 4).
    """
    if not rcvv_embargo_replicas.get(
        "coordinator"
    ) or not rcvv_embargo_replicas.get(late_actor):
        pytest.skip(
            f"coordinator or {late_actor} replica absent;"
            " cannot check late-joiner invariant"
        )
    violations = check_late_joiner_has_full_history(
        rcvv_embargo_replicas, early_actor="coordinator", late_actor=late_actor
    )
    assert not violations, "\n".join(violations)
