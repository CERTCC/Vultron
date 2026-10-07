"""Case-ledger invariant tests for the RCV embargo scenario.

Reads JSONL case-ledger replica files from ``devlogs/rcv-embargo/`` and
asserts universal invariants (via the shared ``common`` library) plus
RCV-embargo-specific checks.

Actor set: ``reporter``, ``coordinator``, ``vendor``, ``case-actor``.

RCV-embargo-specific invariants (DEMOMA-20-006):

- the ledger records, in order, the proposal, the owner's acceptance and the
  termination of the embargo, under the event types the CASE_MANAGER's commit
  path emits.  The strings are imported from that code, never hand-listed
  here, so the check cannot drift from what the manager writes.
- ``invite_actor_to_case`` appears exactly once (the Vendor's invitation; the
  Reporter is seated when the case is created and is never invited).
- ``close_case`` is present and the Vendor replica holds the whole log from
  genesis (it joined late).

All tests are tagged ``@pytest.mark.case_ledger_invariants``.  They skip
automatically when ``devlogs/rcv-embargo/`` is absent.

Spec: DEMOMA-20, CLP-07.
"""

from __future__ import annotations

from itertools import pairwise
from pathlib import Path

import pytest
import yaml

from test.ci.invariants.common import (
    auth_entries,
    check_event_type_count,
    check_event_type_present,
    check_late_joiner_has_full_history,
    event_type,
    load_devlogs,
    log_index,
    payload,
)
from test.ci.invariants.universal_harness import make_universal_invariant_tests
from vultron.core.behaviors.embargo.nodes import (
    EMBARGO_INVITE_EVENT_TYPE,
    EMBARGO_TEARDOWN_EVENT_TYPE,
)
from vultron.core.models.events.base import MessageSemantics

_DEMO_NAME = "rcv-embargo"

#: The Coordinator is the case owner; the seed config fixes its actor id.
_COORDINATOR_SEED = (
    Path(__file__).parents[3]
    / "docker"
    / "seed-configs"
    / "seed-coordinator.yaml"
)
_COORDINATOR_ACTOR_ID: str = yaml.safe_load(_COORDINATOR_SEED.read_text())[
    "local_actor"
]["id"]

#: Event types the CASE_MANAGER commits for the embargo, in the order the
#: scenario drives them: the proposal (and the relayed invitations, which share
#: its type), the owner's acceptance, the termination (DEMOMA-20-006).
_EMBARGO_EVENT_TYPES_IN_ORDER = [
    EMBARGO_INVITE_EVENT_TYPE,
    MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE.value,
    EMBARGO_TEARDOWN_EVENT_TYPE,
]

#: Expected protocol eventTypes in a complete RCV-embargo run.
_RCV_EMBARGO_EXPECTED_EVENT_TYPES = [
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
    # DEMOMA-20-006: the embargo lifecycle.  Spelled out because the notes
    # tables are ratcheted against this literal (ISSUE-3505);
    # test_rcv_embargo_event_type_literals_match_the_commit_path pins each
    # string to the constant the CASE_MANAGER's commit path emits.
    pytest.param("invite_to_embargo_on_case", id="invite_to_embargo_on_case"),
    pytest.param(
        "accept_invite_to_embargo_on_case",
        id="accept_invite_to_embargo_on_case",
    ),
    pytest.param(
        "remove_embargo_event_from_case", id="remove_embargo_event_from_case"
    ),
]

#: Actors with per-actor chain / contiguity / completeness checks.
_CHAIN_ACTORS = [
    pytest.param("case-actor"),
    pytest.param("coordinator"),
    pytest.param("vendor"),
    pytest.param("reporter"),
]


@pytest.fixture(scope="module")
def rcv_embargo_replicas() -> dict[str, list[dict]]:
    """Load RCV-embargo scenario JSONL files grouped by actor name."""
    return load_devlogs(demo_name=_DEMO_NAME)


globals().update(
    make_universal_invariant_tests(
        replicas_fixture="rcv_embargo_replicas",
        chain_actors=_CHAIN_ACTORS,
        expected_event_types=_RCV_EMBARGO_EXPECTED_EVENT_TYPES,
        narrative_path="docs/topics/scenarios/rcv-embargo.md",
    )
)


def test_rcv_embargo_event_type_literals_match_the_commit_path() -> None:
    """The literals in the expected list are the strings the manager commits.

    DEMOMA-20-006 requires the invariant check to use the event types the
    CASE_MANAGER's commit path emits, read from the code.  The expected list
    must be a literal for the notes ratchet, so this pins it to the code.
    """
    listed = {p.values[0] for p in _RCV_EMBARGO_EXPECTED_EVENT_TYPES}
    assert set(_EMBARGO_EVENT_TYPES_IN_ORDER) <= listed


@pytest.mark.case_ledger_invariants
def test_rcv_embargo_events_recorded_in_order(
    rcv_embargo_replicas: dict[str, list[dict]],
) -> None:
    """Proposal, owner's acceptance and termination appear in that order.

    The earliest entry of each type must precede the latest entry of the next:
    the proposal and its relayed invitations share one type, as do the
    participants' acceptances, so the check is on the first and last of each
    rather than on a single entry.  The Vendor's acceptance shares the type
    with the owner's, so the owner's own acceptance is then pinned separately:
    the owner is the Coordinator, whose actor id the demo's seed config fixes,
    and their acceptance must precede the termination.

    Spec: DEMOMA-20-006.
    """
    auth = auth_entries(rcv_embargo_replicas)
    if not auth:
        pytest.skip("no authoritative log; cannot check embargo ordering")

    indices = {
        t: [log_index(e) for e in auth if event_type(e) == t]
        for t in _EMBARGO_EVENT_TYPES_IN_ORDER
    }
    missing = [t for t, found in indices.items() if not found]
    assert not missing, f"embargo event types never committed: {missing}"

    violations = [
        f"{earlier!r} {sorted(indices[earlier])} does not precede "
        f"{later!r} {sorted(indices[later])}"
        for earlier, later in pairwise(_EMBARGO_EVENT_TYPES_IN_ORDER)
        if min(indices[earlier]) >= max(indices[later])
    ]
    assert not violations, "\n".join(violations)

    accept_type = MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE.value
    owner = _COORDINATOR_ACTOR_ID
    owner_accepts = [
        log_index(e)
        for e in auth
        if event_type(e) == accept_type and payload(e).get("actor") == owner
    ]
    assert owner_accepts, f"case owner {owner!r} never accepted the embargo"
    teardown = min(indices[EMBARGO_TEARDOWN_EVENT_TYPE])
    assert min(owner_accepts) < teardown, (
        f"owner's acceptance {sorted(owner_accepts)} does not precede the"
        f" termination at {teardown}"
    )


@pytest.mark.case_ledger_invariants
def test_rcv_embargo_termination_committed_exactly_once(
    rcv_embargo_replicas: dict[str, list[dict]],
) -> None:
    """The embargo is terminated once: by the Coordinator, not again at CS.P.

    Publication follows the termination, so the P-transition finds no active
    embargo and must commit no second teardown.

    Spec: DEMOMA-20-006, DEMOMA-20-007 (phases 4 and 5).
    """
    violations = check_event_type_count(
        rcv_embargo_replicas,
        EMBARGO_TEARDOWN_EVENT_TYPE,
        min_count=1,
        max_count=1,
    )
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_rcv_embargo_invite_actor_to_case_exactly_once(
    rcv_embargo_replicas: dict[str, list[dict]],
) -> None:
    """``invite_actor_to_case`` appears exactly once (the Vendor's invitation).

    The Reporter is seated as a participant when the case is created
    (CM-22-002), so only the Vendor is invited.

    Spec: DEMOMA-20-007 (phase 1).
    """
    violations = check_event_type_count(
        rcv_embargo_replicas, "invite_actor_to_case", min_count=1, max_count=1
    )
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_rcv_embargo_close_case_present(
    rcv_embargo_replicas: dict[str, list[dict]],
) -> None:
    """``close_case`` event type is present in the log.

    Spec: DEMOMA-20-007 (phase 6).
    """
    violations = check_event_type_present(rcv_embargo_replicas, "close_case")
    assert not violations, violations[0] if violations else ""


@pytest.mark.case_ledger_invariants
def test_rcv_embargo_vendor_late_joiner_has_full_history(
    rcv_embargo_replicas: dict[str, list[dict]],
) -> None:
    """Vendor replica contains every logIndex present in the coordinator replica.

    The Vendor is invited after the case exists and must receive the full
    ledger backfill.

    Spec: DEMOMA-20-007 (phase 1).
    """
    if not rcv_embargo_replicas.get(
        "coordinator"
    ) or not rcv_embargo_replicas.get("vendor"):
        pytest.skip(
            "coordinator or vendor replica absent; cannot check late-joiner invariant"
        )
    violations = check_late_joiner_has_full_history(
        rcv_embargo_replicas, early_actor="coordinator", late_actor="vendor"
    )
    assert not violations, "\n".join(violations)
