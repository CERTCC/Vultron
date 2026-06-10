#!/usr/bin/env python

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

"""Unit tests for SvcAddParticipantStatusUseCase and CreateParticipantStatusNode.

Covers:
- ``_resolve_current_participant_state()`` / ``resolve_participant_state_from_dl``
  helper that extracts the latest ``(RM, CS_vfd)`` pair from a participant record.
- ``CreateParticipantStatusNode`` BT node (BT-15-001: status record creation
  must live inside the BT, not directly in ``execute()``).
- ``SvcAddParticipantStatusUseCase.execute()`` full integration path.
"""

from typing import cast

import pytest

from vultron.core.states.cs import CS_vfd
from vultron.core.states.rm import RM

# ---------------------------------------------------------------------------
# Test stubs
# ---------------------------------------------------------------------------


class _FakeParticipantStatus:
    """Minimal stand-in for ParticipantStatus."""

    def __init__(self, rm_state: RM, vfd_state: CS_vfd) -> None:
        self.rm_state = rm_state
        self.vfd_state = vfd_state


class _FakeParticipantWithStatuses:
    """Participant stub with a non-empty participant_statuses list."""

    def __init__(self, statuses: list) -> None:
        self.participant_statuses = statuses


class _FakeParticipantNoStatuses:
    """Participant stub with an empty participant_statuses list.

    Uses an instance-level list (initialised in ``__init__``) so each
    instance gets its own independent list and mutable state cannot leak
    between tests.
    """

    def __init__(self) -> None:
        self.participant_statuses: list = []


class _FakeDL:
    """Minimal DataLayer stub — only ``read()`` is needed here."""

    def __init__(self, stored=None) -> None:
        self._stored = stored

    def read(self, obj_id: str):
        return self._stored


def _as_persistence(dl: "_FakeDL"):
    """Cast the stub to CaseOutboxPersistence so pyright is satisfied."""
    from vultron.core.ports.case_persistence import CaseOutboxPersistence

    return cast(CaseOutboxPersistence, dl)


def _make_use_case(dl: "_FakeDL"):
    """Return a SvcAddParticipantStatusUseCase backed by the given stub DL."""
    from vultron.core.use_cases.triggers.case import (
        SvcAddParticipantStatusUseCase,
    )
    from vultron.core.use_cases.triggers.requests import (
        AddParticipantStatusTriggerRequest,
    )

    request = AddParticipantStatusTriggerRequest(
        actor_id="https://example.org/actor",
        case_id="https://example.org/case",
    )
    return SvcAddParticipantStatusUseCase(_as_persistence(dl), request)


# ---------------------------------------------------------------------------
# _resolve_current_participant_state tests
# ---------------------------------------------------------------------------


def test_resolve_participant_state_returns_tuple_of_rm_cs_vfd():
    """Return type is tuple[RM, CS_vfd] — not tuple[Any, Any]."""
    status = _FakeParticipantStatus(RM.ACCEPTED, CS_vfd.VFD)
    participant = _FakeParticipantWithStatuses([status])
    dl = _FakeDL(stored=participant)
    use_case = _make_use_case(dl)

    rm, vfd = use_case._resolve_current_participant_state(
        _as_persistence(dl), "any-id"
    )

    assert isinstance(rm, RM)
    assert isinstance(vfd, CS_vfd)


def test_resolve_participant_state_returns_latest_statuses():
    """Returns RM and CS_vfd values from the last entry in participant_statuses."""
    earlier = _FakeParticipantStatus(RM.RECEIVED, CS_vfd.vfd)
    later = _FakeParticipantStatus(RM.ACCEPTED, CS_vfd.VFD)
    participant = _FakeParticipantWithStatuses([earlier, later])
    dl = _FakeDL(stored=participant)
    use_case = _make_use_case(dl)

    rm, vfd = use_case._resolve_current_participant_state(
        _as_persistence(dl), "any-id"
    )

    assert rm == RM.ACCEPTED
    assert vfd == CS_vfd.VFD


def test_resolve_participant_state_defaults_when_no_statuses():
    """Returns (RM.START, CS_vfd.vfd) when participant_statuses is empty."""
    participant = _FakeParticipantNoStatuses()
    dl = _FakeDL(stored=participant)
    use_case = _make_use_case(dl)

    rm, vfd = use_case._resolve_current_participant_state(
        _as_persistence(dl), "any-id"
    )

    assert rm == RM.START
    assert vfd == CS_vfd.vfd


def test_resolve_participant_state_defaults_when_participant_not_found():
    """Returns (RM.START, CS_vfd.vfd) when dl.read() returns None."""
    dl = _FakeDL(stored=None)
    use_case = _make_use_case(dl)

    rm, vfd = use_case._resolve_current_participant_state(
        _as_persistence(dl), "missing-id"
    )

    assert rm == RM.START
    assert vfd == CS_vfd.vfd


def test_resolve_participant_state_defaults_when_invalid_rm_type():
    """Falls back to RM.START when rm_state is not an RM enum value."""

    class _BadStatus:
        rm_state = "not-an-rm"
        vfd_state = CS_vfd.VFd

    participant = _FakeParticipantWithStatuses([_BadStatus()])
    dl = _FakeDL(stored=participant)
    use_case = _make_use_case(dl)

    rm, vfd = use_case._resolve_current_participant_state(
        _as_persistence(dl), "any-id"
    )

    assert rm == RM.START
    assert isinstance(vfd, CS_vfd)


def test_resolve_participant_state_defaults_when_invalid_vfd_type():
    """Falls back to CS_vfd.vfd when vfd_state is not a CS_vfd enum value."""

    class _BadStatus:
        rm_state = RM.VALID
        vfd_state = "not-a-cs-vfd"

    participant = _FakeParticipantWithStatuses([_BadStatus()])
    dl = _FakeDL(stored=participant)
    use_case = _make_use_case(dl)

    rm, vfd = use_case._resolve_current_participant_state(
        _as_persistence(dl), "any-id"
    )

    assert isinstance(rm, RM)
    assert vfd == CS_vfd.vfd


# ---------------------------------------------------------------------------
# execute() — sender's participant record is updated after SvcAdd (#624)
# ---------------------------------------------------------------------------


class TestSvcAddParticipantStatusExecuteUpdatesSenderRecord:
    """SvcAddParticipantStatusUseCase.execute() appends to sender's own record.

    Without this, ``_resolve_current_participant_state`` always reads the
    bootstrap seed (RM.START), never the actual latest state the sender
    has reported.  See issue #624.
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        from vultron.adapters.driven.datalayer_sqlite import (
            SqliteDataLayer,
            reset_datalayer,
        )
        from vultron.adapters.driven.trigger_activity_adapter import (
            TriggerActivityAdapter,
        )
        from vultron.core.states.roles import CVDRole
        from vultron.wire.as2.vocab.base.objects.actors import as_Service
        from vultron.wire.as2.vocab.objects.case_participant import (
            CaseParticipant,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        # Finder actor
        self.actor = as_Service(name="Finder Actor")
        actor_id = self.actor.id_
        reset_datalayer(actor_id)
        self.dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor_id)
        self.dl.clear_all()
        self.dl.create(self.actor)

        # Case Actor (CASE_MANAGER)
        self.case_actor = as_Service(name="Case Actor")
        reset_datalayer(self.case_actor.id_)
        self.dl.create(self.case_actor)

        # Case
        self.case = VulnerabilityCase(name="Test Case #624")

        self.actor_participant = CaseParticipant(
            attributed_to=actor_id,
            context=self.case.id_,
            case_roles=[CVDRole.FINDER],
        )
        self.case_manager_participant = CaseParticipant(
            attributed_to=self.case_actor.id_,
            context=self.case.id_,
            case_roles=[CVDRole.CASE_MANAGER],
        )

        self.case.actor_participant_index[actor_id] = (
            self.actor_participant.id_
        )
        self.case.actor_participant_index[self.case_actor.id_] = (
            self.case_manager_participant.id_
        )

        self.dl.create(self.case)
        self.dl.create(self.actor_participant)
        self.dl.create(self.case_manager_participant)

        self.trigger_activity = TriggerActivityAdapter(self.dl)
        yield
        try:
            self.dl.clear_all()
        finally:
            self.dl.close()
            reset_datalayer(actor_id)
            reset_datalayer(self.case_actor.id_)

    def test_execute_appends_status_to_sender_participant(self):
        """After execute(), sender's participant_statuses contains the new status.

        Without this, _resolve_current_participant_state would always read the
        initial seed (RM.START / CS_vfd.vfd), causing subsequent calls to report
        stale RM.START — the root cause of #624.
        """
        from vultron.core.states.rm import RM
        from vultron.core.use_cases.triggers.case import (
            SvcAddParticipantStatusUseCase,
        )
        from vultron.core.use_cases.triggers.requests import (
            AddParticipantStatusTriggerRequest,
        )

        request = AddParticipantStatusTriggerRequest(
            actor_id=self.actor.id_,
            case_id=self.case.id_,
            rm_state=RM.ACCEPTED,
        )
        result = SvcAddParticipantStatusUseCase(
            self.dl,
            request,
            trigger_activity=self.trigger_activity,
        ).execute()

        status_id = result.get("status_id")
        assert status_id is not None, "execute() must return a status_id"

        # The sender's own participant record must now contain the status.
        participant = self.dl.read(self.actor_participant.id_)
        assert participant is not None
        statuses = getattr(participant, "participant_statuses", [])
        status_ids = [getattr(s, "id_", s) for s in statuses]
        assert status_id in status_ids, (
            "Sender's participant_statuses must include the newly created "
            f"status '{status_id}' after execute() (#624). Got: {status_ids}"
        )

    def test_resolve_current_state_returns_emitted_rm_after_execute(self):
        """_resolve_current_participant_state returns the emitted RM after execute.

        This is the proxy check for the M6 bug: if execute() does NOT update the
        sender's record, _resolve_current_participant_state will still return
        RM.START on the next call, causing the next outbound status to carry
        RM.START and be rejected as a backwards transition by the vendor.
        """
        from vultron.core.states.rm import RM
        from vultron.core.use_cases.triggers.case import (
            SvcAddParticipantStatusUseCase,
        )
        from vultron.core.use_cases.triggers.requests import (
            AddParticipantStatusTriggerRequest,
        )

        request = AddParticipantStatusTriggerRequest(
            actor_id=self.actor.id_,
            case_id=self.case.id_,
            rm_state=RM.ACCEPTED,
        )
        use_case = SvcAddParticipantStatusUseCase(
            self.dl,
            request,
            trigger_activity=self.trigger_activity,
        )
        use_case.execute()

        # On a second call, _resolve_current_participant_state must return
        # RM.ACCEPTED (the state we just emitted), not RM.START.
        rm, _ = use_case._resolve_current_participant_state(
            self.dl, self.actor_participant.id_
        )
        assert rm == RM.ACCEPTED, (
            f"After execute() with rm_state=RM.ACCEPTED, "
            f"_resolve_current_participant_state must return RM.ACCEPTED; "
            f"got {rm!r} (#624)"
        )


# ---------------------------------------------------------------------------
# CreateParticipantStatusNode — BT node unit tests (BT-15-001)
# ---------------------------------------------------------------------------


class TestCreateParticipantStatusNode:
    """CreateParticipantStatusNode creates a status snapshot inside the BT.

    These tests verify the BT node that was extracted from the inline
    ParticipantStatus creation in SvcAddParticipantStatusUseCase.execute()
    as part of the BT-15-001 remediation (issue #850).
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        import py_trees

        from vultron.adapters.driven.datalayer_sqlite import (
            SqliteDataLayer,
            reset_datalayer,
        )
        from vultron.adapters.driven.trigger_activity_adapter import (
            TriggerActivityAdapter,
        )
        from vultron.core.behaviors.bridge import BTBridge
        from vultron.core.states.roles import CVDRole
        from vultron.wire.as2.vocab.base.objects.actors import as_Service
        from vultron.wire.as2.vocab.objects.case_participant import (
            CaseParticipant,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        py_trees.blackboard.Blackboard.enable_activity_stream()
        py_trees.blackboard.Blackboard.storage.clear()

        self.actor = as_Service(name="Reporter")
        actor_id = self.actor.id_
        reset_datalayer(actor_id)
        self.dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor_id)
        self.dl.clear_all()
        self.dl.create(self.actor)

        self.case_actor = as_Service(name="Case Actor")
        reset_datalayer(self.case_actor.id_)
        self.dl.create(self.case_actor)

        self.case = VulnerabilityCase(name="Test Case BT-15-001")

        self.actor_participant = CaseParticipant(
            attributed_to=actor_id,
            context=self.case.id_,
            case_roles=[CVDRole.FINDER],
        )
        self.case_manager_participant = CaseParticipant(
            attributed_to=self.case_actor.id_,
            context=self.case.id_,
            case_roles=[CVDRole.CASE_MANAGER],
        )

        self.case.actor_participant_index[actor_id] = (
            self.actor_participant.id_
        )
        self.case.actor_participant_index[self.case_actor.id_] = (
            self.case_manager_participant.id_
        )

        self.dl.create(self.case)
        self.dl.create(self.actor_participant)
        self.dl.create(self.case_manager_participant)

        self.bridge = BTBridge(
            datalayer=self.dl,
            trigger_activity=TriggerActivityAdapter(self.dl),
        )

        yield

        try:
            self.dl.clear_all()
        finally:
            self.dl.close()
            reset_datalayer(actor_id)
            reset_datalayer(self.case_actor.id_)
        py_trees.blackboard.Blackboard.storage.clear()

    def _run_node(self, **kwargs):
        """Build and execute a tree containing only CreateParticipantStatusNode."""
        from vultron.core.behaviors.case.nodes.participant import (
            CreateParticipantStatusNode,
        )

        result_out: dict = {}
        node = CreateParticipantStatusNode(
            case_id=self.case.id_,
            actor_id=self.actor.id_,
            result_out=result_out,
            **kwargs,
        )
        bt_result = self.bridge.execute_with_setup(
            node, actor_id=self.actor.id_
        )
        return bt_result, result_out

    def test_node_succeeds_and_populates_result_out(self):
        """CreateParticipantStatusNode returns SUCCESS and sets result_out keys."""
        from py_trees.common import Status

        bt_result, result_out = self._run_node(
            rm_state=None, vfd_state=None, pxa_state=None
        )

        assert bt_result.status == Status.SUCCESS
        assert "status_id" in result_out
        assert isinstance(result_out["status_id"], str)
        assert "participant_id" in result_out
        assert result_out["participant_id"] == self.actor_participant.id_

    def test_node_persists_status_with_explicit_rm_state(self):
        """CreateParticipantStatusNode persists ParticipantStatus with given RM."""
        from vultron.core.states.rm import RM
        from vultron.wire.as2.vocab.objects.case_status import (
            ParticipantStatus as WireParticipantStatus,
        )

        bt_result, result_out = self._run_node(
            rm_state=RM.ACCEPTED, vfd_state=None, pxa_state=None
        )

        status_id = result_out.get("status_id")
        assert isinstance(status_id, str), "result_out must contain status_id"
        stored = self.dl.read(status_id)
        # dl.read() reconstructs via find_in_vocabulary, which returns the
        # wire-layer ParticipantStatus (VultronAS2Object subclass).
        assert isinstance(stored, WireParticipantStatus)
        assert stored.rm_state == RM.ACCEPTED

    def test_node_appends_status_to_participant(self):
        """CreateParticipantStatusNode appends the status to participant_statuses."""
        from vultron.core.states.rm import RM

        _, result_out = self._run_node(
            rm_state=RM.ACCEPTED, vfd_state=None, pxa_state=None
        )

        status_id = result_out.get("status_id")
        participant = self.dl.read(self.actor_participant.id_)
        statuses = getattr(participant, "participant_statuses", [])
        status_ids = [getattr(s, "id_", s) for s in statuses]
        assert status_id in status_ids, (
            f"CreateParticipantStatusNode must append status '{status_id}'"
            f" to participant_statuses. Got: {status_ids}"
        )

    def test_node_fails_when_actor_not_in_case(self):
        """CreateParticipantStatusNode returns FAILURE for unknown actor."""
        from py_trees.common import Status

        from vultron.core.behaviors.case.nodes.participant import (
            CreateParticipantStatusNode,
        )

        result_out: dict = {}
        node = CreateParticipantStatusNode(
            case_id=self.case.id_,
            actor_id="https://example.org/unknown-actor",
            rm_state=None,
            vfd_state=None,
            pxa_state=None,
            result_out=result_out,
        )
        bt_result = self.bridge.execute_with_setup(
            node, actor_id=self.actor.id_
        )

        assert bt_result.status == Status.FAILURE
        assert "status_id" not in result_out

    def test_node_uses_current_state_when_rm_none(self):
        """CreateParticipantStatusNode uses existing RM state when rm_state=None."""
        from vultron.core.states.rm import RM
        from vultron.wire.as2.vocab.objects.case_status import (
            ParticipantStatus as WireParticipantStatus,
        )

        _, result_out = self._run_node(
            rm_state=None, vfd_state=None, pxa_state=None
        )

        status_id = result_out.get("status_id")
        assert isinstance(status_id, str), "result_out must contain status_id"
        stored = self.dl.read(status_id)
        # dl.read() reconstructs via find_in_vocabulary, which returns the
        # wire-layer ParticipantStatus (VultronAS2Object subclass).
        assert isinstance(stored, WireParticipantStatus)
        # No prior statuses → defaults to RM.START
        assert stored.rm_state == RM.START
