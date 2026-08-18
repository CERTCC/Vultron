#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""Regression guard for issue #2241.

Several demo assertion helpers overclaimed: they passed vacuously on
empty/unfetchable participant sets, used unreliable proxies for presence,
or produced misleading diagnostics when they timed out.  This file
documents each defect with a failing-before/passing-after test.

Defects covered:

1. ``notes.py:participant_adds_note_to_case`` — ``result`` assigned inside
   ``demo_step``, dereferenced outside → ``UnboundLocalError`` when the
   trigger is swallowed.

2. ``verification.py:_all_fetchable_participants_rm_closed`` — when every
   participant fetch returns 404, builds an empty list and calls
   ``all_participants_rm_closed([])`` → ``True`` (vacuous convergence).

3. ``polling.py:wait_for_case_participants`` — compares
   ``len(case.case_participants) >= expected_count``; ``case_participants``
   is ``list[as_CaseParticipantRef]`` which can hold bare string IDs, so
   the count is satisfied even when no real ``CaseParticipant`` objects
   exist.

4. ``polling.py:_wait_for_participant_status_field`` — timeout
   ``AssertionError`` message includes only the actor URI; the container
   that was polled (``client.base_url``) is absent, making it impossible
   to tell which container was checked.

5. ``milestones.py:verify_fix_ready`` — checks only ``vfd_state``; does
   not verify the required cross-state invariant that CS.F entails RM in
   {ACCEPTED, DEFERRED, CLOSED}.
"""

from typing import cast
from unittest.mock import MagicMock

import pytest

import vultron.demo.helpers.notes as notes_module
import vultron.demo.utils as demo_utils
from vultron.core.states.cs import CS_vfd
from vultron.core.states.rm import RM
from vultron.demo.helpers.notes import participant_adds_note_to_case
from vultron.demo.helpers.polling import wait_for_case_participants
from vultron.demo.helpers.verification import (
    _all_fetchable_participants_rm_closed,
)
from vultron.demo.utils import DataLayerClient, reset_demo_failures
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.case_status import as_ParticipantStatus
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

_CASE_ID = "urn:uuid:test-case-2241-0001"
_RECEIVER_ID = "http://vendor:7999/api/v2/actors/vendor"
_REPORTER_ID = "http://finder:7999/api/v2/actors/finder"
_PARTICIPANT_ID = "urn:uuid:p-vendor-2241"
_REPORTER_PARTICIPANT_ID = "urn:uuid:p-finder-2241"


# ===========================================================================
# Defect 1 — notes.py UnboundLocalError
# ===========================================================================


def test_participant_adds_note_no_unbound_on_trigger_failure(monkeypatch):
    """participant_adds_note_to_case must not raise UnboundLocalError when trigger fails.

    ``demo_step`` swallows exceptions by design (DEMOCI-01-003/004).  Before
    the fix, ``result`` was assigned inside the block but dereferenced after
    it, so a swallowed trigger failure left ``result`` unbound and the
    subsequent ``result.get(...)`` raised ``UnboundLocalError``, masking the
    real failure.  Regression for #2241 (notes.py site); pattern established
    by #2191 / PR #2196.
    """
    reset_demo_failures()

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated add-note-to-case trigger HTTP 500")

    monkeypatch.setattr(notes_module, "post_to_trigger", _boom)

    poster = MagicMock()
    poster.id_ = _REPORTER_ID
    case = MagicMock()
    case.id_ = _CASE_ID

    raised_unbound = False
    try:
        participant_adds_note_to_case(
            posting_client=cast(DataLayerClient, None),
            watching_client=cast(DataLayerClient, None),
            poster=poster,
            case=case,
            note_name="regression-note",
            note_content="regression test for #2241",
        )
    except UnboundLocalError:
        raised_unbound = True
    except Exception:
        # Any other exception (e.g. AssertionError from note_id is None)
        # is acceptable — it is not the UnboundLocalError that masked failures.
        pass

    assert not raised_unbound, (
        "demo_step swallowed the trigger error but post-block code "
        "dereferenced an unbound result variable (UnboundLocalError), "
        "masking the real failure (#2241)"
    )
    assert demo_utils._demo_failures, (
        "demo_step should have recorded the swallowed trigger failure on "
        "_demo_failures"
    )


# ===========================================================================
# Defect 2 — _all_fetchable_participants_rm_closed vacuously true
# ===========================================================================


def test_all_fetchable_participants_rm_closed_empty_is_false():
    """When every participant fetch returns 404, must return False, not True.

    ``_all_fetchable_participants_rm_closed`` skips 404 participants
    (remote containers) by design.  Before the fix, if ALL participants
    were unfetchable the inner list stayed empty and
    ``all_participants_rm_closed([])`` returned ``True`` — vacuous
    convergence that could not detect the #2233 defect.
    """
    case_data = {
        "id": _CASE_ID,
        "type": "VulnerabilityCase",
        "actorParticipantIndex": {
            _REPORTER_ID: _REPORTER_PARTICIPANT_ID,
            _RECEIVER_ID: _PARTICIPANT_ID,
        },
    }
    case = as_VulnerabilityCase(**case_data)

    # Every participant fetch raises AssertionError("404 Not Found") —
    # the test-client compat path inside _fetch_participant_data.
    client = MagicMock()
    client.get.side_effect = AssertionError("404 Not Found")

    result = _all_fetchable_participants_rm_closed(
        cast(DataLayerClient, client), case
    )

    assert result is False, (
        "_all_fetchable_participants_rm_closed returned True with no "
        "fetchable participants — vacuous convergence, cannot confirm "
        "RM.CLOSED (#2241)"
    )


# ===========================================================================
# Defect 3 — wait_for_case_participants counts ID strings
# ===========================================================================


def test_wait_for_case_participants_does_not_count_id_strings():
    """wait_for_case_participants must not be satisfied by bare string IDs.

    ``case_participants`` is ``list[as_CaseParticipantRef]``, which can hold
    plain string IRIs.  Before the fix, ``len(case.case_participants)``
    counted those strings and satisfied the ``>= expected_count`` guard even
    when no real ``CaseParticipant`` objects existed — the bug the fix for
    #2233 was supposed to catch.

    After the fix the check uses ``len(case.actor_participant_index)``
    instead; that map is only populated when a participant record is actually
    created, so it cannot be fooled by bare string IDs.
    """
    case_payload = {
        "id": _CASE_ID,
        "type": "VulnerabilityCase",
        # Two bare string IDs — no real CaseParticipant objects
        "caseParticipants": [_REPORTER_PARTICIPANT_ID, _PARTICIPANT_ID],
        "actorParticipantIndex": {},
    }

    client = MagicMock()
    client.get.return_value = case_payload

    with pytest.raises(AssertionError, match="[Tt]imed out"):
        wait_for_case_participants(
            vendor_client=cast(DataLayerClient, client),
            case_id=_CASE_ID,
            expected_count=2,
            timeout_seconds=0.1,
            poll_interval=0.01,
        )


# ===========================================================================
# Defect 4 — _wait_for_participant_status_field omits base_url
# ===========================================================================


def test_wait_participant_status_timeout_includes_base_url(monkeypatch):
    """Timeout error must identify which container was polled (client.base_url).

    Before the fix the message only included the actor URI; a caller could
    not tell whether vendor or coordinator was polled when the assertion
    fired.  The error must include ``client.base_url`` so the container is
    identifiable from the message alone.
    """
    import vultron.demo.helpers.verification as verification_module
    from vultron.demo.helpers.polling import _wait_for_participant_status_field

    ps = as_ParticipantStatus(
        context=_CASE_ID, rm_state=RM.RECEIVED, vfd_state=CS_vfd.vfd
    )
    participant = as_CaseParticipant(
        id_=_PARTICIPANT_ID,
        case_roles=[CVDRole.VENDOR],
        participant_statuses=[ps],
    )

    monkeypatch.setattr(
        verification_module,
        "_fetch_participant",
        lambda *a, **kw: participant,
    )

    client = DataLayerClient(base_url="http://test-container-2241:7999")

    with pytest.raises(AssertionError) as exc_info:
        _wait_for_participant_status_field(
            client=client,
            case_id=_CASE_ID,
            actor_id=_RECEIVER_ID,
            field_name="rm_state",
            expected_states={RM.ACCEPTED},
            timeout_seconds=0.05,
            poll_interval=0.01,
        )

    assert "http://test-container-2241:7999" in str(exc_info.value), (
        "Timeout AssertionError must identify the container that was polled "
        "via client.base_url; the message only contained the actor URI (#2241)"
    )


# ===========================================================================
# Defect 5 — verify_fix_ready missing RM-CS coupling invariant
# ===========================================================================


def _make_participant(vfd: CS_vfd, rm: RM) -> as_CaseParticipant:
    """Build a minimal CaseParticipant with given vfd and rm state."""
    ps = as_ParticipantStatus(context=_CASE_ID, vfd_state=vfd, rm_state=rm)
    return as_CaseParticipant(
        id_=_PARTICIPANT_ID,
        case_roles=[CVDRole.VENDOR],
        participant_statuses=[ps],
    )


def test_verify_fix_ready_fails_if_rm_not_engaged(monkeypatch):
    """verify_fix_ready must raise when vfd_state=VFd but rm_state=RECEIVED.

    CS.F entails RM in {ACCEPTED, DEFERRED, CLOSED}.  Before the fix,
    ``verify_fix_ready`` only checked ``vfd_state`` and did not verify the
    required RM invariant, so a participant at RM.RECEIVED with VFd CS state
    would pass the milestone check without having engaged with the report.
    """
    import vultron.demo.helpers.milestones as milestones_module
    import vultron.demo.helpers.verification as verification_module
    from vultron.demo.helpers.milestones import verify_fix_ready

    # Participant has fix-ready CS state (VFd) but has not yet engaged (RECEIVED)
    participant = _make_participant(vfd=CS_vfd.VFd, rm=RM.RECEIVED)

    # _check_participant_vfd_state_in and _check_participant_rm_state_in live
    # in verification.py and call _fetch_participant from that module's namespace.
    # _assert_vendor_role lives in milestones.py and calls it from milestones'
    # namespace.  Both must be patched so all callers return our participant.
    monkeypatch.setattr(
        verification_module,
        "_fetch_participant",
        lambda *a, **kw: participant,
    )
    monkeypatch.setattr(
        milestones_module,
        "_fetch_participant",
        lambda *a, **kw: participant,
    )

    receiver_client = MagicMock()
    reporter_client = MagicMock()

    with pytest.raises(AssertionError):
        verify_fix_ready(
            receiver_client=cast(DataLayerClient, receiver_client),
            reporter_client=cast(DataLayerClient, reporter_client),
            case_id=_CASE_ID,
            receiver_actor_id=_RECEIVER_ID,
        )


# ===========================================================================
# Defect 6 — run_invite_path_rm_triage polls only auth_client for RM state
# ===========================================================================


def test_run_invite_path_rm_triage_polls_invited_client_for_rm_state(
    monkeypatch,
):
    """run_invite_path_rm_triage must poll invited_client, not only auth_client.

    Before the fix, both RM state checks used ``auth_client`` (the
    authoritative coordinator view).  The invitee's own container — where the
    divergence in #2233/#2234 lives — was never queried.  After the fix, two
    additional ``wait_for_participant_rm_state`` calls explicitly use
    ``invited_client``: once for RM.VALID and once for RM.ACCEPTED.
    """
    import vultron.demo.helpers.workflow as workflow_module
    from vultron.demo.helpers.workflow import run_invite_path_rm_triage

    auth_client_ids = []
    invited_client_ids = []

    invited_client = MagicMock()
    invited_client.base_url = "http://vendor2:7999"
    auth_client = MagicMock()
    auth_client.base_url = "http://coordinator:7999"

    def _track_rm_state(client, case_id, actor_id, expected_states, **kw):
        if client is invited_client:
            invited_client_ids.append(frozenset(expected_states))
        elif client is auth_client:
            auth_client_ids.append(frozenset(expected_states))

    monkeypatch.setattr(
        workflow_module, "wait_for_participant_rm_state", _track_rm_state
    )
    monkeypatch.setattr(
        workflow_module,
        "wait_for_event_type_in_ledger",
        lambda *a, **kw: None,
    )
    monkeypatch.setattr(
        workflow_module,
        "receiver_validates_report",
        lambda *a, **kw: None,
    )
    monkeypatch.setattr(
        workflow_module,
        "receiver_engages_case",
        lambda *a, **kw: None,
    )

    invited_obj = MagicMock()
    invited_obj.id_ = "http://vendor2:7999/api/v2/actors/vendor2"

    case = MagicMock()
    case.id_ = _CASE_ID

    run_invite_path_rm_triage(
        invited_client=cast(DataLayerClient, invited_client),
        invited_actor=MagicMock(),
        offer=MagicMock(),
        report=MagicMock(),
        finder=MagicMock(),
        auth_client=cast(DataLayerClient, auth_client),
        case=case,
        invited_obj=invited_obj,
    )

    assert len(invited_client_ids) >= 2, (
        "run_invite_path_rm_triage must poll invited_client for RM state at "
        "least twice (RM.VALID and RM.ACCEPTED); before the fix only "
        "auth_client was polled, so failures on the invitee's container "
        "went undetected (#2241 defect 6)"
    )
    valid_calls = [s for s in invited_client_ids if RM.VALID in s]
    accepted_calls = [s for s in invited_client_ids if RM.ACCEPTED in s]
    assert (
        valid_calls
    ), "invited_client must be polled for RM.VALID (or {VALID,ACCEPTED})"
    assert accepted_calls, "invited_client must be polled for RM.ACCEPTED"
