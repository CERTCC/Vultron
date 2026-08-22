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

from vultron.core.models.dimensions import RmDimension, VfdDimension
from vultron.core.states.cs import CS_vfd
from vultron.core.states.rm import RM
from vultron.errors import VultronValidationError

# ---------------------------------------------------------------------------
# Test stubs
# ---------------------------------------------------------------------------


class _FakeParticipantStatus:
    """Minimal stand-in for as_ParticipantStatus."""

    def __init__(self, rm_state: RM, vfd_state: CS_vfd) -> None:
        self.rm = RmDimension(state=rm_state)
        self.vfd = VfdDimension(state=vfd_state)


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


def test_resolve_participant_state_raises_when_invalid_rm_type():
    """Raises when the latest status carries an unusable RM state.

    This previously fell back to ``RM.START``, which silently reset the
    participant's RM ladder to its initial state and then rejected the next
    legitimate transition as backwards (#2264, a symptom of #2232).  A status
    that exists but exposes no usable ``rm`` is a shape mismatch, not an
    absence, so it must raise (ARCH-15-001..004).  Absence — an empty
    ``participant_statuses`` list — still returns ``RM.START``; see
    ``test_resolve_participant_state_defaults_when_no_statuses``.
    """

    class _BadRmAttr:
        state = "not-an-rm"

    class _BadStatus:
        rm = _BadRmAttr()
        vfd = VfdDimension(state=CS_vfd.VFd)

    participant = _FakeParticipantWithStatuses([_BadStatus()])
    dl = _FakeDL(stored=participant)
    use_case = _make_use_case(dl)

    with pytest.raises(VultronValidationError, match="no valid RM state"):
        use_case._resolve_current_participant_state(
            _as_persistence(dl), "any-id"
        )


def test_resolve_participant_state_raises_when_invalid_vfd_type():
    """Raises when the latest status carries an unusable VFD state.

    The VFD counterpart of
    ``test_resolve_participant_state_raises_when_invalid_rm_type``: this
    previously fell back to ``CS_vfd.vfd``, resetting the participant's
    vendor-fix ladder to its initial state the same way ``RM.START`` reset the
    RM ladder (#2264, a symptom of #2232).  Absence — an empty
    ``participant_statuses`` list — still returns ``CS_vfd.vfd``; see
    ``test_resolve_participant_state_defaults_when_no_statuses``.
    """

    class _BadVfdAttr:
        state = "not-a-cs-vfd"

    class _BadStatus:
        rm = RmDimension(state=RM.VALID)
        vfd = _BadVfdAttr()

    participant = _FakeParticipantWithStatuses([_BadStatus()])
    dl = _FakeDL(stored=participant)
    use_case = _make_use_case(dl)

    with pytest.raises(VultronValidationError, match="no valid VFD state"):
        use_case._resolve_current_participant_state(
            _as_persistence(dl), "any-id"
        )


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
        from vultron.enums.roles import CVDRole
        from vultron.wire.as2.vocab.base.objects.actors import as_Service
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
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
        self.case = as_VulnerabilityCase(name="Test Case #624")

        self.actor_participant = as_CaseParticipant(
            attributed_to=actor_id,
            context=self.case.id_,
            case_roles=[CVDRole.FINDER],
        )
        self.case_manager_participant = as_CaseParticipant(
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

    def _to_ids(self, activity) -> list[str]:
        to = getattr(activity, "to", None)
        if isinstance(to, list):
            return [
                (
                    item
                    if isinstance(item, str)
                    else getattr(item, "id_", str(item))
                )
                for item in to
            ]
        if isinstance(to, str):
            return [to]
        return []

    def test_outbox_activity_addressed_to_case_actor(self):
        """Activity queued by execute() is addressed to the Case Actor only (PCR-08-001)."""
        from vultron.core.use_cases.triggers.case import (
            SvcAddParticipantStatusUseCase,
        )
        from vultron.core.use_cases.triggers.requests import (
            AddParticipantStatusTriggerRequest,
        )

        request = AddParticipantStatusTriggerRequest(
            actor_id=self.actor.id_,
            case_id=self.case.id_,
            rm_state=RM.RECEIVED,
        )
        before = set(self.dl.outbox_list_for_actor(self.actor.id_))
        SvcAddParticipantStatusUseCase(
            self.dl, request, trigger_activity=self.trigger_activity
        ).execute()
        after = set(self.dl.outbox_list_for_actor(self.actor.id_))
        new_ids = after - before
        assert (
            new_ids
        ), "AddParticipantStatus must queue at least one outbox activity"
        activity_id = next(iter(new_ids))
        activity = self.dl.read(activity_id)
        assert activity is not None
        to_ids = self._to_ids(activity)
        assert (
            self.case_actor.id_ in to_ids
        ), f"PCR-08-001: activity must be addressed to CaseActor; to={to_ids!r}"
        assert (
            len(to_ids) == 1
        ), f"PCR-08-001: exactly one recipient expected, got {to_ids!r}"

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
            rm_state=RM.RECEIVED,
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
            rm_state=RM.RECEIVED,
        )
        use_case = SvcAddParticipantStatusUseCase(
            self.dl,
            request,
            trigger_activity=self.trigger_activity,
        )
        use_case.execute()

        # On a second call, _resolve_current_participant_state must return
        # RM.RECEIVED (the state we just emitted), not RM.START.
        rm, _ = use_case._resolve_current_participant_state(
            self.dl, self.actor_participant.id_
        )
        assert rm == RM.RECEIVED, (
            f"After execute() with rm_state=RM.RECEIVED, "
            f"_resolve_current_participant_state must return RM.RECEIVED; "
            f"got {rm!r} (#624)"
        )


# ---------------------------------------------------------------------------
# CreateParticipantStatusNode — BT node unit tests (BT-15-001)
# ---------------------------------------------------------------------------


class TestCreateParticipantStatusNode:
    """CreateParticipantStatusNode creates a status snapshot inside the BT.

    These tests verify the BT node that was extracted from the inline
    as_ParticipantStatus creation in SvcAddParticipantStatusUseCase.execute()
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
        from vultron.enums.roles import CVDRole
        from vultron.wire.as2.vocab.base.objects.actors import as_Service
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
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

        self.case = as_VulnerabilityCase(name="Test Case BT-15-001")

        self.actor_participant = as_CaseParticipant(
            attributed_to=actor_id,
            context=self.case.id_,
            case_roles=[CVDRole.FINDER],
        )
        self.case_manager_participant = as_CaseParticipant(
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
        from vultron.core.models.participant_status import ParticipantStatus
        from vultron.core.states.rm import RM

        bt_result, result_out = self._run_node(
            rm_state=RM.ACCEPTED, vfd_state=None, pxa_state=None
        )

        status_id = result_out.get("status_id")
        assert isinstance(status_id, str), "result_out must contain status_id"
        stored = self.dl.read(status_id)
        assert isinstance(stored, ParticipantStatus)
        assert stored.rm.state == RM.ACCEPTED

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
        from vultron.core.models.participant_status import ParticipantStatus
        from vultron.core.states.rm import RM

        _, result_out = self._run_node(
            rm_state=None, vfd_state=None, pxa_state=None
        )

        status_id = result_out.get("status_id")
        assert isinstance(status_id, str), "result_out must contain status_id"
        stored = self.dl.read(status_id)
        assert isinstance(stored, ParticipantStatus)
        # No prior statuses → defaults to RM.START
        assert stored.rm.state == RM.START

    def _cs_narrative_records(self, caplog):
        """Return INFO-level CS narrative records emitted during the run."""
        import logging

        return [
            r
            for r in caplog.records
            if " CS: " in r.getMessage() and r.levelno == logging.INFO
        ]

    def test_vfd_transition_logged_at_info(self, caplog):
        """A VFD advance emits the SL-04-006 CS narrative line at INFO."""
        import logging

        with caplog.at_level(logging.INFO):
            self._run_node(rm_state=None, vfd_state=CS_vfd.Vfd, pxa_state=None)

        records = self._cs_narrative_records(caplog)
        assert records, "Expected a CS narrative line at INFO for VFD advance"
        message = records[0].getMessage()
        assert f"Actor '{self.actor.id_}' CS: vfd → Vfd" in message
        assert "(vendor aware)" in message
        assert f"for case '{self.case.id_}'" in message

    def test_pxa_transition_logged_at_info(self, caplog):
        """A PXA advance emits the SL-04-006 CS narrative line at INFO."""
        import logging

        from vultron.core.states.cs import CS_pxa

        with caplog.at_level(logging.INFO):
            self._run_node(rm_state=None, vfd_state=None, pxa_state=CS_pxa.Pxa)

        records = self._cs_narrative_records(caplog)
        assert records, "Expected a CS narrative line at INFO for PXA advance"
        message = records[0].getMessage()
        assert f"Actor '{self.actor.id_}' CS: pxa → Pxa" in message
        assert "(publicly known)" in message

    def test_no_cs_line_when_no_cs_dimension_changes(self, caplog):
        """An RM-only snapshot emits no CS narrative line (SL-04-007)."""
        import logging

        from vultron.core.states.rm import RM

        with caplog.at_level(logging.INFO):
            self._run_node(
                rm_state=RM.ACCEPTED, vfd_state=None, pxa_state=None
            )

        assert not self._cs_narrative_records(caplog)

    def test_no_cs_line_when_vfd_state_unchanged(self, caplog):
        """Re-asserting the current VFD state is not a transition."""
        import logging

        with caplog.at_level(logging.INFO):
            self._run_node(rm_state=None, vfd_state=CS_vfd.vfd, pxa_state=None)

        assert not self._cs_narrative_records(caplog)

    def test_created_participantstatus_line_is_debug(self, caplog):
        """The "Created ParticipantStatus" bookkeeping line is DEBUG."""
        import logging

        with caplog.at_level(logging.DEBUG):
            self._run_node(rm_state=None, vfd_state=None, pxa_state=None)

        created = [
            r
            for r in caplog.records
            if "Created ParticipantStatus" in r.getMessage()
        ]
        assert created, "Expected the ParticipantStatus creation line"
        assert all(r.levelno == logging.DEBUG for r in created)

    def test_repeat_pxa_write_emits_no_second_cs_line(self, caplog):
        """The same public-disclosure milestone is not re-logged.

        The before-state must come from the participant's own latest
        ``case_status.pxa``: this node never appends to ``case.case_statuses``,
        so reading ``case.current_status`` reported a stale ``pxa`` and made
        every repeat write look like a fresh disclosure event.
        """
        import logging

        from vultron.core.states.cs import CS_pxa

        self._run_node(rm_state=None, vfd_state=None, pxa_state=CS_pxa.Pxa)

        caplog.clear()
        with caplog.at_level(logging.INFO):
            self._run_node(rm_state=None, vfd_state=None, pxa_state=CS_pxa.Pxa)

        assert not self._cs_narrative_records(caplog), (
            "A repeat PXA write is a no-op and must not re-announce the"
            " public-disclosure milestone"
        )

    def _rm_narrative_records(self, caplog):
        import logging

        return [
            r
            for r in caplog.records
            if " RM: " in r.getMessage() and r.levelno == logging.INFO
        ]

    def test_rm_transition_logged_at_info(self, caplog):
        """AC-12: this node is a second per-participant RM write path.

        ``update_participant_rm_state()`` is not the only RM writer — this node
        appends a ``ParticipantStatus`` with an explicit ``rm_state`` directly
        (used by e.g. the leave-case RM → CLOSED nodes), so it must emit the
        narrative RM line itself.
        """
        import logging

        from vultron.core.states.rm import RM

        with caplog.at_level(logging.INFO):
            self._run_node(
                rm_state=RM.RECEIVED, vfd_state=None, pxa_state=None
            )

        records = self._rm_narrative_records(caplog)
        assert records, "Expected a narrative RM line at INFO"
        message = records[0].getMessage()
        assert f"Actor '{self.actor.id_}' RM: START → RECEIVED" in message
        assert f"for case '{self.case.id_}'" in message

    def test_no_rm_line_when_rm_state_unchanged(self, caplog):
        """Re-asserting the current RM state is not a transition."""
        import logging

        from vultron.core.states.rm import RM

        with caplog.at_level(logging.INFO):
            self._run_node(rm_state=RM.START, vfd_state=None, pxa_state=None)

        assert not self._rm_narrative_records(caplog)

    def test_no_rm_line_when_rm_state_not_requested(self, caplog):
        """A CS-only snapshot emits no RM narrative line."""
        import logging

        with caplog.at_level(logging.INFO):
            self._run_node(rm_state=None, vfd_state=CS_vfd.Vfd, pxa_state=None)

        assert not self._rm_narrative_records(caplog)


# ---------------------------------------------------------------------------
# ValidateTriggerTransitionsNode — AC-1 through AC-6 (issues #2081, #1903)
# ---------------------------------------------------------------------------


class TestValidateTriggerTransitions:
    """Trigger-path transition guard: fail-closed for invalid state jumps.

    AC-1: Invalid VFD jump → VultronValidationError, no record persisted.
    AC-2: Invalid RM transition → VultronValidationError, no record persisted.
    AC-3: Backward PXA → VultronValidationError, no record persisted.
    AC-4: Same-state write → SUCCESS, record persisted.
    AC-5: None target → SUCCESS, record persisted.
    AC-6: Trigger path (end-to-end through use case) rejects invalid VFD jump.

    Per BTND-10-001, SDO-02-004, CSB-16-001, CSB-16-002.
    Closes #2081, #1903.
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
        from vultron.enums.roles import CVDRole
        from vultron.wire.as2.vocab.base.objects.actors import as_Service
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        self.actor = as_Service(name="Finder")
        actor_id = self.actor.id_
        reset_datalayer(actor_id)
        self.dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor_id)
        self.dl.clear_all()
        self.dl.create(self.actor)

        self.case_actor = as_Service(name="Case Actor")
        reset_datalayer(self.case_actor.id_)
        self.dl.create(self.case_actor)

        self.case = as_VulnerabilityCase(name="Test Case AC-1..6")
        self.actor_participant = as_CaseParticipant(
            attributed_to=actor_id,
            context=self.case.id_,
            case_roles=[CVDRole.FINDER],
        )
        self.case_manager_participant = as_CaseParticipant(
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

    def _execute(self, rm_state=None, vfd_state=None, pxa_state=None):
        from vultron.core.use_cases.triggers.case import (
            SvcAddParticipantStatusUseCase,
        )
        from vultron.core.use_cases.triggers.requests import (
            AddParticipantStatusTriggerRequest,
        )

        request = AddParticipantStatusTriggerRequest(
            actor_id=self.actor.id_,
            case_id=self.case.id_,
            rm_state=rm_state,
            vfd_state=vfd_state,
            pxa_state=pxa_state,
        )
        return SvcAddParticipantStatusUseCase(
            self.dl, request, trigger_activity=self.trigger_activity
        ).execute()

    def _status_count(self):
        participant = self.dl.read(self.actor_participant.id_)
        return len(getattr(participant, "participant_statuses", []))

    def test_ac1_invalid_vfd_jump_raises_and_persists_nothing(self):
        """AC-1: vfd → VFD (skips Vfd) raises VultronValidationError; no record written."""
        from vultron.errors import VultronValidationError

        before = self._status_count()
        with pytest.raises(VultronValidationError):
            self._execute(vfd_state=CS_vfd.VFD)
        assert self._status_count() == before

    def test_ac2_invalid_rm_transition_raises_and_persists_nothing(self):
        """AC-2: START → CLOSED (non-adjacent) raises VultronValidationError; no record written."""
        from vultron.errors import VultronValidationError

        before = self._status_count()
        with pytest.raises(VultronValidationError):
            self._execute(rm_state=RM.CLOSED)
        assert self._status_count() == before

    def test_ac3_backward_pxa_raises_and_persists_nothing(self):
        """AC-3: Pxa → pxa (backward) raises VultronValidationError; no record written.

        First advances to Pxa via a valid write, then attempts a backward
        move to pxa to confirm the guard rejects it.
        """
        from vultron.core.states.cs import CS_pxa
        from vultron.errors import VultronValidationError

        # Valid forward step: pxa → Pxa.
        self._execute(pxa_state=CS_pxa.Pxa)
        before = self._status_count()

        # Backward step: Pxa → pxa must be rejected.
        with pytest.raises(VultronValidationError):
            self._execute(pxa_state=CS_pxa.pxa)
        assert self._status_count() == before

    def test_ac4_same_state_write_succeeds(self):
        """AC-4: Same-state write (target == current) is a valid confirmation; record persisted."""
        before = self._status_count()
        # START → START is a same-state write (initial RM state).
        self._execute(rm_state=RM.START)
        assert self._status_count() == before + 1

    def test_ac5_none_target_skips_validation_and_succeeds(self):
        """AC-5: All-None request skips all validation and persists a snapshot."""
        before = self._status_count()
        self._execute(rm_state=None, vfd_state=None, pxa_state=None)
        assert self._status_count() == before + 1

    def test_ac6_trigger_path_rejects_invalid_vfd_end_to_end(self):
        """AC-6: The add-participant-status trigger path rejects invalid VFD via use case.

        Confirms the guard is wired into add_participant_status_trigger_bt
        and therefore fires for every HTTP-trigger invocation.
        """
        from vultron.errors import VultronValidationError

        # Participant starts at vfd (initial). Jumping to VFD skips Vfd.
        with pytest.raises(VultronValidationError, match="VFD"):
            self._execute(vfd_state=CS_vfd.VFD)

    def test_valid_adjacent_vfd_step_succeeds(self):
        """Valid adjacent VFD step (vfd → Vfd) is accepted and record persisted."""
        before = self._status_count()
        self._execute(vfd_state=CS_vfd.Vfd)
        assert self._status_count() == before + 1

    def test_valid_adjacent_rm_step_succeeds(self):
        """Valid adjacent RM step (START → RECEIVED) is accepted and record persisted."""
        before = self._status_count()
        self._execute(rm_state=RM.RECEIVED)
        assert self._status_count() == before + 1


# ---------------------------------------------------------------------------
# CheckNotSoleObserverVfdNode — CM-25-005 end-to-end guard (#2192)
# ---------------------------------------------------------------------------


class TestSoleObserverVfdGuard:
    """End-to-end guard: sole-OBSERVER actor MUST NOT emit v→V (CM-25-005).

    Uses the full use-case stack (SqliteDataLayer → SvcAddParticipantStatusUseCase)
    to prove CheckNotSoleObserverVfdNode is wired into add_participant_status_trigger_bt
    and fires for every trigger invocation.

    AC: a sole-OBSERVER actor calling execute(vfd_state=CS_vfd.Vfd) raises
    VultronValidationError and writes no record (CM-25-005).

    CM-26-001 union-of-permissions: an OBSERVER+VENDOR actor CAN emit v→V.
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
        from vultron.enums.roles import CVDRole
        from vultron.wire.as2.vocab.base.objects.actors import as_Service
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        self.actor = as_Service(name="Observer")
        actor_id = self.actor.id_
        reset_datalayer(actor_id)
        self.dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor_id)
        self.dl.clear_all()
        self.dl.create(self.actor)

        self.case_actor = as_Service(name="Case Manager")
        reset_datalayer(self.case_actor.id_)
        self.dl.create(self.case_actor)

        self.case = as_VulnerabilityCase(name="Test Case CM-25-005")
        self.actor_participant = as_CaseParticipant(
            attributed_to=actor_id,
            context=self.case.id_,
            case_roles=[CVDRole.OBSERVER],
        )
        self.case_manager_participant = as_CaseParticipant(
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

    def _execute(self, rm_state=None, vfd_state=None, pxa_state=None):
        from vultron.core.use_cases.triggers.case import (
            SvcAddParticipantStatusUseCase,
        )
        from vultron.core.use_cases.triggers.requests import (
            AddParticipantStatusTriggerRequest,
        )

        request = AddParticipantStatusTriggerRequest(
            actor_id=self.actor.id_,
            case_id=self.case.id_,
            rm_state=rm_state,
            vfd_state=vfd_state,
            pxa_state=pxa_state,
        )
        return SvcAddParticipantStatusUseCase(
            self.dl, request, trigger_activity=self.trigger_activity
        ).execute()

    def _status_count(self):
        participant = self.dl.read(self.actor_participant.id_)
        return len(getattr(participant, "participant_statuses", []))

    def test_sole_observer_vfd_transition_blocked_end_to_end(self):
        """CM-25-005: sole-OBSERVER actor attempting v→V raises VultronValidationError."""
        from vultron.errors import VultronValidationError

        before = self._status_count()
        with pytest.raises(VultronValidationError):
            self._execute(vfd_state=CS_vfd.Vfd)
        assert self._status_count() == before

    def test_sole_observer_none_vfd_request_succeeds(self):
        """Sole-OBSERVER actor with no VFD override bypasses guard; record persisted."""
        before = self._status_count()
        self._execute(rm_state=None, vfd_state=None, pxa_state=None)
        assert self._status_count() == before + 1


# ---------------------------------------------------------------------------
# ValidateTriggerTransitionsNode — cross-machine entailments (#2236)
# ---------------------------------------------------------------------------


class TestCrossMachineEntailments:
    """Trigger-path cross-machine entailment guard (#2236).

    CSB-18-001: VFD F bit (VFd/VFD) requires RM ∈ {ACCEPTED, DEFERRED, CLOSED}.
    Both RM and VFD are per-actor attributes; a contradictory combination is
    rejected at emit time.

    Motivating case: FCV failure shipped VFd + RM.RECEIVED — an impossible
    combination because fix readiness entails RM.ACCEPTED.

    Note: PXA→EM entailments (CSB-18-002..004) are causal, not contradictory
    from the emitter's perspective: asserting P CAUSES EM to terminate. Those
    constraints are enforced on the receive path.
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
        from vultron.enums.roles import CVDRole
        from vultron.wire.as2.vocab.base.objects.actors import as_Service
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        self.actor = as_Service(name="Vendor")
        actor_id = self.actor.id_
        reset_datalayer(actor_id)
        self.dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor_id)
        self.dl.clear_all()
        self.dl.create(self.actor)

        self.case_actor = as_Service(name="Case Actor")
        reset_datalayer(self.case_actor.id_)
        self.dl.create(self.case_actor)

        self.case = as_VulnerabilityCase(name="Test Case #2236")
        self.actor_participant = as_CaseParticipant(
            attributed_to=actor_id,
            context=self.case.id_,
            case_roles=[CVDRole.VENDOR],
        )
        self.case_manager_participant = as_CaseParticipant(
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

    def _execute(self, rm_state=None, vfd_state=None, pxa_state=None):
        from vultron.core.use_cases.triggers.case import (
            SvcAddParticipantStatusUseCase,
        )
        from vultron.core.use_cases.triggers.requests import (
            AddParticipantStatusTriggerRequest,
        )

        request = AddParticipantStatusTriggerRequest(
            actor_id=self.actor.id_,
            case_id=self.case.id_,
            rm_state=rm_state,
            vfd_state=vfd_state,
            pxa_state=pxa_state,
        )
        return SvcAddParticipantStatusUseCase(
            self.dl, request, trigger_activity=self.trigger_activity
        ).execute()

    def _status_count(self):
        participant = self.dl.read(self.actor_participant.id_)
        return len(getattr(participant, "participant_statuses", []))

    def _advance_rm_to_accepted(self):
        """Step the actor through RM.START → RECEIVED → VALID → ACCEPTED."""
        self._execute(rm_state=RM.RECEIVED)
        self._execute(rm_state=RM.VALID)
        self._execute(rm_state=RM.ACCEPTED)

    # --- CSB-18-001: RM ↔ VFD entailment ---

    def test_csb18_001_vfd_fix_ready_with_rm_received_raises(self):
        """CSB-18-001: Vfd → VFd while RM is RECEIVED raises (FCV motivating case).

        The actor advances to vendor-aware (Vfd) while still at RM.RECEIVED,
        then tries to assert fix-ready (VFd). This is the FCV failure pattern:
        fix readiness requires RM.ACCEPTED.
        """
        from vultron.errors import VultronValidationError

        # Valid combined step: vendor becomes aware while reporting received.
        self._execute(rm_state=RM.RECEIVED, vfd_state=CS_vfd.Vfd)
        before = self._status_count()
        # Cross-machine violation: VFd requires RM ≥ ACCEPTED; current is RECEIVED.
        with pytest.raises(VultronValidationError, match="Cross-machine"):
            self._execute(vfd_state=CS_vfd.VFd)
        assert self._status_count() == before

    def test_csb18_001_vfd_fix_ready_with_current_rm_valid_raises(self):
        """CSB-18-001: Vfd → VFd when actor is at RM.VALID raises.

        After advancing to RM.VALID and Vfd, the actor must not assert VFd
        because fix readiness requires RM.ACCEPTED.
        """
        from vultron.errors import VultronValidationError

        self._execute(rm_state=RM.RECEIVED)
        self._execute(rm_state=RM.VALID)
        self._execute(vfd_state=CS_vfd.Vfd)
        before = self._status_count()
        with pytest.raises(VultronValidationError, match="Cross-machine"):
            self._execute(vfd_state=CS_vfd.VFd)
        assert self._status_count() == before

    def test_csb18_001_vfd_fix_ready_with_rm_accepted_succeeds(self):
        """CSB-18-001: Vfd → VFd when actor is at RM.ACCEPTED is valid."""
        self._advance_rm_to_accepted()
        self._execute(vfd_state=CS_vfd.Vfd)
        before = self._status_count()
        self._execute(vfd_state=CS_vfd.VFd)
        assert self._status_count() == before + 1

    def test_csb18_001_vfd_fix_deployed_with_rm_accepted_succeeds(self):
        """CSB-18-001: VFd → VFD when actor is at RM.ACCEPTED is valid.

        DEPLOYER role is required for the d→D transition (CSB-15-002); the
        participant is re-registered with CVDRole.DEPLOYER before the test.
        """
        from vultron.enums.roles import CVDRole
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )

        # Re-register the participant as DEPLOYER so the role guard passes.
        deployer_participant = as_CaseParticipant(
            id_=self.actor_participant.id_,
            attributed_to=self.actor.id_,
            context=self.case.id_,
            case_roles=[CVDRole.VENDOR, CVDRole.DEPLOYER],
        )
        self.dl.save(deployer_participant)

        self._advance_rm_to_accepted()
        self._execute(vfd_state=CS_vfd.Vfd)
        self._execute(vfd_state=CS_vfd.VFd)
        before = self._status_count()
        self._execute(vfd_state=CS_vfd.VFD)
        assert self._status_count() == before + 1

    def test_csb18_001_vfd_vendor_aware_with_rm_received_succeeds(self):
        """CSB-18-001: vfd → Vfd when actor is at RM.RECEIVED is valid.

        The V bit (vendor aware) has no RM constraint; only F/D bits do.
        """
        before = self._status_count()
        self._execute(rm_state=RM.RECEIVED, vfd_state=CS_vfd.Vfd)
        assert self._status_count() == before + 1

    def test_pxa_public_aware_succeeds(self):
        """Asserting Pxa (P bit) is valid — PXA is an actor-level attribute."""
        from vultron.core.states.cs import CS_pxa

        before = self._status_count()
        self._execute(pxa_state=CS_pxa.Pxa)
        assert self._status_count() == before + 1


class TestViolationPxaEmEntailment:
    """Unit tests for violation_pxa_em_entailment() (CSB-18-002..004).

    These rules are provided for future receive-path enforcement and are NOT
    wired into the emit path.  Tests document the expected semantics so future
    maintainers have a baseline when adding the receive-path guard.
    """

    def _check(self, pxa, em):
        from vultron.core.states.cross_machine_invariants import (
            violation_pxa_em_entailment,
        )

        return violation_pxa_em_entailment(pxa, em)

    def test_p_bit_with_active_embargo_returns_error(self):
        """CSB-18-002: P bit (public aware) with EM.ACTIVE is a violation."""
        from vultron.core.states.cs import CS_pxa
        from vultron.core.states.em import EM

        result = self._check(CS_pxa.Pxa, EM.ACTIVE)
        assert result is not None
        assert "P bit" in result

    def test_x_bit_with_active_embargo_returns_error(self):
        """CSB-18-003: X bit (exploit public) with EM.ACTIVE is a violation.

        Uses pXa (X set, P not set) to isolate the X-bit check from the P-bit
        check (P is tested first in violation_pxa_em_entailment).
        """
        from vultron.core.states.cs import CS_pxa
        from vultron.core.states.em import EM

        result = self._check(CS_pxa.pXa, EM.ACTIVE)
        assert result is not None
        assert "X bit" in result

    def test_a_bit_with_active_embargo_returns_error(self):
        """CSB-18-004: A bit (attacks observed) with EM.ACTIVE is a violation."""
        from vultron.core.states.cs import CS_pxa
        from vultron.core.states.em import EM

        result = self._check(CS_pxa.pxA, EM.ACTIVE)
        assert result is not None
        assert "A bit" in result

    def test_p_bit_with_revise_embargo_returns_error(self):
        """CSB-18-002: P bit with EM.REVISE (also active) is a violation."""
        from vultron.core.states.cs import CS_pxa
        from vultron.core.states.em import EM

        result = self._check(CS_pxa.Pxa, EM.REVISE)
        assert result is not None

    def test_pxa_no_bits_with_active_embargo_returns_none(self):
        """No bit set with EM.ACTIVE — no entailment violated."""
        from vultron.core.states.cs import CS_pxa
        from vultron.core.states.em import EM

        assert self._check(CS_pxa.pxa, EM.ACTIVE) is None

    def test_p_bit_without_active_embargo_returns_none(self):
        """P bit with EM.NONE — no embargo, no constraint."""
        from vultron.core.states.cs import CS_pxa
        from vultron.core.states.em import EM

        assert self._check(CS_pxa.Pxa, EM.NONE) is None
