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
  helper that extracts the latest ``(RM, CS_vf | None, CS_d | None)`` triple from
  a participant record.
- ``CreateParticipantStatusNode`` BT node (BT-15-001: status record creation
  must live inside the BT, not directly in ``execute()``).
- ``SvcAddParticipantStatusUseCase.execute()`` full integration path.
"""

from typing import cast

import pytest
from py_trees.common import Status

from vultron.core.models.dimensions import DDimension, RmDimension, VfDimension
from vultron.core.states.cs import CS_d, CS_pxa, CS_vf
from vultron.core.states.rm import RM
from vultron.errors import VultronValidationError

# ---------------------------------------------------------------------------
# Test stubs
# ---------------------------------------------------------------------------


class _FakeParticipantStatus:
    """Minimal stand-in for ParticipantStatus (core shape)."""

    def __init__(
        self,
        rm_state: RM,
        vf_state: CS_vf | None,
        d_state: CS_d | None,
    ) -> None:
        self.rm = RmDimension(state=rm_state)
        self.vf = VfDimension(state=vf_state) if vf_state is not None else None
        self.d = DDimension(state=d_state) if d_state is not None else None


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


def test_resolve_participant_state_returns_tuple_of_rm_cs_vf_cs_d():
    """Return type is tuple[RM, CS_vf | None, CS_d | None]."""
    status = _FakeParticipantStatus(
        RM.ACCEPTED, vf_state=CS_vf.Vf, d_state=CS_d.D
    )
    participant = _FakeParticipantWithStatuses([status])
    dl = _FakeDL(stored=participant)
    use_case = _make_use_case(dl)

    rm, vf, d = use_case._resolve_current_participant_state(
        _as_persistence(dl), "any-id"
    )

    assert isinstance(rm, RM)
    assert isinstance(vf, CS_vf)
    assert isinstance(d, CS_d)


def test_resolve_participant_state_returns_latest_statuses():
    """Returns RM, CS_vf, CS_d values from the last entry in participant_statuses."""
    earlier = _FakeParticipantStatus(RM.RECEIVED, vf_state=None, d_state=None)
    later = _FakeParticipantStatus(RM.ACCEPTED, vf_state=None, d_state=CS_d.D)
    participant = _FakeParticipantWithStatuses([earlier, later])
    dl = _FakeDL(stored=participant)
    use_case = _make_use_case(dl)

    rm, vf, d = use_case._resolve_current_participant_state(
        _as_persistence(dl), "any-id"
    )

    assert rm == RM.ACCEPTED
    assert vf is None
    assert d == CS_d.D


def test_resolve_participant_state_defaults_when_no_statuses():
    """Returns (RM.START, None, None) when participant_statuses is empty."""
    participant = _FakeParticipantNoStatuses()
    dl = _FakeDL(stored=participant)
    use_case = _make_use_case(dl)

    rm, vf, d = use_case._resolve_current_participant_state(
        _as_persistence(dl), "any-id"
    )

    assert rm == RM.START
    assert vf is None
    assert d is None


def test_resolve_participant_state_defaults_when_participant_not_found():
    """Returns (RM.START, None, None) when dl.read() returns None."""
    dl = _FakeDL(stored=None)
    use_case = _make_use_case(dl)

    rm, vf, d = use_case._resolve_current_participant_state(
        _as_persistence(dl), "missing-id"
    )

    assert rm == RM.START
    assert vf is None
    assert d is None


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
        vf = VfDimension(state=CS_vf.VF)

    participant = _FakeParticipantWithStatuses([_BadStatus()])
    dl = _FakeDL(stored=participant)
    use_case = _make_use_case(dl)

    with pytest.raises(VultronValidationError, match="no valid RM state"):
        use_case._resolve_current_participant_state(
            _as_persistence(dl), "any-id"
        )


def test_resolve_participant_state_raises_when_invalid_vf_type():
    """Raises when the latest status carries an unusable VF state.

    The VF counterpart of
    ``test_resolve_participant_state_raises_when_invalid_rm_type``: this
    previously fell back to ``CS_vfd.vfd``, resetting the participant's
    vendor-fix ladder to its initial state the same way ``RM.START`` reset the
    RM ladder (#2264, a symptom of #2232).  Absence — an empty
    ``participant_statuses`` list — still returns ``None``; see
    ``test_resolve_participant_state_defaults_when_no_statuses``.
    """

    class _BadVfAttr:
        state = "not-a-cs-vf"

    class _BadStatus:
        rm = RmDimension(state=RM.VALID)
        vf = _BadVfAttr()

    participant = _FakeParticipantWithStatuses([_BadStatus()])
    dl = _FakeDL(stored=participant)
    use_case = _make_use_case(dl)

    with pytest.raises(VultronValidationError, match="'vf' dimension"):
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

    @pytest.mark.spec("PCR-08-001")
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
        before = set(self.dl.outbox_list())
        SvcAddParticipantStatusUseCase(
            self.dl, request, trigger_activity=self.trigger_activity
        ).execute()
        after = set(self.dl.outbox_list())
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
        initial seed (RM.START), causing subsequent calls to report
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
        rm, *_ = use_case._resolve_current_participant_state(
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

    def _seed_participant_vf_state(self, vf_target: CS_vf) -> None:
        """Directly persist a ParticipantStatus to advance the actor to vf_target."""
        from vultron.core.models.case_participant import CaseParticipant
        from vultron.core.models.participant_status import ParticipantStatus

        seed = ParticipantStatus(
            context=self.case.id_,
            attributed_to=self.actor.id_,
            rm=RmDimension(state=RM.START),
            vf=VfDimension(state=vf_target),
        )
        self.dl.create(seed)
        participant = self.dl.read(self.actor_participant.id_)
        if isinstance(participant, CaseParticipant):
            participant.add_participant_status(seed)
            self.dl.save(participant)

    def _seed_participant_pxa_state(self, pxa_target: CS_pxa) -> None:
        """Directly persist a ParticipantStatus with an embedded CaseStatus."""
        from vultron.core.models.case_participant import CaseParticipant
        from vultron.core.models.case_status import (
            CaseStatus as CoreCaseStatus,
        )
        from vultron.core.models.dimensions import EmDimension, PxaDimension
        from vultron.core.models.participant_status import ParticipantStatus
        from vultron.core.states.em import EM as _EM

        case_status = CoreCaseStatus(
            context=self.case.id_,
            attributed_to=self.actor.id_,
            em=EmDimension(state=_EM.NONE),
            pxa=PxaDimension(state=pxa_target),
        )
        seed = ParticipantStatus(
            context=self.case.id_,
            attributed_to=self.actor.id_,
            rm=RmDimension(state=RM.START),
            case_status=case_status,
        )
        self.dl.create(seed)
        participant = self.dl.read(self.actor_participant.id_)
        if isinstance(participant, CaseParticipant):
            participant.add_participant_status(seed)
            self.dl.save(participant)

    def test_node_succeeds_and_populates_result_out(self):
        """CreateParticipantStatusNode returns SUCCESS and sets result_out keys."""
        from py_trees.common import Status

        bt_result, result_out = self._run_node(
            rm_state=None, vf_state=None, d_state=None, pxa_state=None
        )

        assert bt_result.status == Status.SUCCESS
        assert "status_id" in result_out
        assert isinstance(result_out["status_id"], str)
        assert "participant_id" in result_out
        assert result_out["participant_id"] == self.actor_participant.id_

    def test_node_persists_status_with_explicit_rm_state(self):
        """CreateParticipantStatusNode persists ParticipantStatus with given RM.

        ``RM.RECEIVED`` is the only legal step from the participant's baseline
        ``RM.START``: since #3050 the write node validates the RM rung too, so
        an ``RM.ACCEPTED`` jump here would be refused rather than persisted.
        """
        from vultron.core.models.participant_status import ParticipantStatus
        from vultron.core.states.rm import RM

        bt_result, result_out = self._run_node(
            rm_state=RM.RECEIVED, vf_state=None, d_state=None, pxa_state=None
        )

        assert bt_result.status == Status.SUCCESS, bt_result.feedback_message
        status_id = result_out.get("status_id")
        assert isinstance(status_id, str), "result_out must contain status_id"
        stored = self.dl.read(status_id)
        assert isinstance(stored, ParticipantStatus)
        assert stored.rm.state == RM.RECEIVED

    def test_node_appends_status_to_participant(self):
        """CreateParticipantStatusNode appends the status to participant_statuses."""
        from vultron.core.states.rm import RM

        _, result_out = self._run_node(
            rm_state=RM.RECEIVED, vf_state=None, d_state=None, pxa_state=None
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
            vf_state=None,
            d_state=None,
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
            rm_state=None, vf_state=None, d_state=None, pxa_state=None
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

    def test_vf_transition_logged_at_info(self, caplog):
        """A VF advance emits the SL-04-006 CS narrative line at INFO."""
        import logging

        self._seed_participant_vf_state(CS_vf.vf)
        with caplog.at_level(logging.INFO):
            self._run_node(
                rm_state=None, vf_state=CS_vf.Vf, d_state=None, pxa_state=None
            )

        records = self._cs_narrative_records(caplog)
        assert records, "Expected a CS narrative line at INFO for VF advance"
        message = records[0].getMessage()
        assert f"Actor '{self.actor.id_}' CS: vf → Vf" in message
        assert "(vendor aware)" in message
        assert f"for case '{self.case.id_}'" in message

    def test_pxa_transition_logged_at_info(self, caplog):
        """A PXA advance emits the SL-04-006 CS narrative line at INFO."""
        import logging

        from vultron.core.states.cs import CS_pxa

        with caplog.at_level(logging.INFO):
            self._run_node(
                rm_state=None,
                vf_state=None,
                d_state=None,
                pxa_state=CS_pxa.Pxa,
            )

        records = self._cs_narrative_records(caplog)
        assert records, "Expected a CS narrative line at INFO for PXA advance"
        # vP promotion may fire a VF narrative first; search all records for PXA
        pxa_records = [r for r in records if "pxa → Pxa" in r.getMessage()]
        assert (
            pxa_records
        ), "Expected CS narrative containing 'pxa → Pxa'; got: " + str(
            [r.getMessage() for r in records]
        )
        message = pxa_records[0].getMessage()
        assert f"Actor '{self.actor.id_}' CS: pxa → Pxa" in message
        assert "(publicly known)" in message

    def test_no_cs_line_when_no_cs_dimension_changes(self, caplog):
        """An RM-only snapshot emits no CS narrative line (SL-04-007)."""
        import logging

        from vultron.core.states.rm import RM

        with caplog.at_level(logging.INFO):
            bt_result, _ = self._run_node(
                rm_state=RM.RECEIVED,
                vf_state=None,
                d_state=None,
                pxa_state=None,
            )

        # Assert the write actually happened: a refused write emits no CS line
        # either, which would make this test pass vacuously.
        assert bt_result.status == Status.SUCCESS, bt_result.feedback_message
        assert not self._cs_narrative_records(caplog)

    def test_no_cs_line_when_vf_state_unchanged(self, caplog):
        """Re-asserting the current VF state is not a transition."""
        import logging

        self._seed_participant_vf_state(CS_vf.vf)
        with caplog.at_level(logging.INFO):
            self._run_node(
                rm_state=None,
                vf_state=CS_vf.vf,
                d_state=None,
                pxa_state=None,
            )

        assert not self._cs_narrative_records(caplog)

    def test_created_participantstatus_line_is_debug(self, caplog):
        """The "Created ParticipantStatus" bookkeeping line is DEBUG."""
        import logging

        with caplog.at_level(logging.DEBUG):
            self._run_node(
                rm_state=None, vf_state=None, d_state=None, pxa_state=None
            )

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

        self._run_node(
            rm_state=None, vf_state=None, d_state=None, pxa_state=CS_pxa.Pxa
        )

        caplog.clear()
        with caplog.at_level(logging.INFO):
            self._run_node(
                rm_state=None,
                vf_state=None,
                d_state=None,
                pxa_state=CS_pxa.Pxa,
            )

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
                rm_state=RM.RECEIVED,
                vf_state=None,
                d_state=None,
                pxa_state=None,
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
            self._run_node(
                rm_state=RM.START,
                vf_state=None,
                d_state=None,
                pxa_state=None,
            )

        assert not self._rm_narrative_records(caplog)

    def test_no_rm_line_when_rm_state_not_requested(self, caplog):
        """A CS-only snapshot emits no RM narrative line."""
        import logging

        self._seed_participant_vf_state(CS_vf.vf)
        with caplog.at_level(logging.INFO):
            self._run_node(
                rm_state=None,
                vf_state=CS_vf.Vf,
                d_state=None,
                pxa_state=None,
            )

        assert not self._rm_narrative_records(caplog)

    # ------------------------------------------------------------------
    # AC-4: write-boundary validation (CSB-16-001) — these tests call
    # _run_node() directly, bypassing ValidateTriggerTransitionsNode
    # ------------------------------------------------------------------

    def test_invalid_vf_jump_blocked_at_write_node(self):
        """CSB-16-001: illegal multi-step VF jump is rejected at the write boundary.

        vf → VF skips Vf; CreateParticipantStatusNode must return FAILURE
        without writing, independent of upstream guard coverage (AC-4).
        """
        from py_trees.common import Status

        # Seed current_vf=CS_vf.vf so the precondition check has something to
        # validate against.
        self._seed_participant_vf_state(CS_vf.vf)

        bt_result, result_out = self._run_node(
            rm_state=None, vf_state=CS_vf.VF, d_state=None, pxa_state=None
        )

        assert bt_result.status == Status.FAILURE
        assert "status_id" not in result_out

    def test_same_state_vf_write_allowed_at_write_node(self):
        """CSB-16-001: same-state VF write (no actual transition) is allowed.

        Uses CS_vf.Vf because VENDOR participants cannot hold CS_vf.vf
        (Vendor-implies-V, PRM-06-002, ADR-0084).
        """
        from py_trees.common import Status

        self._seed_participant_vf_state(CS_vf.Vf)

        bt_result, result_out = self._run_node(
            rm_state=None, vf_state=CS_vf.Vf, d_state=None, pxa_state=None
        )

        assert bt_result.status == Status.SUCCESS
        assert "status_id" in result_out

    def test_vendor_aware_vf_requires_vendor_role_at_write_node(self):
        """ADR-0075 / #2862: Vf target is blocked when the actor has no VENDOR role.

        The adjacent transition vf → Vf is structurally valid; the node must
        still refuse it when the actor lacks VENDOR role.  This tests the
        write-boundary defense-in-depth check the write node performs through
        participant_transition_violations() (BTND-10-003), bypassing
        ValidateTriggerTransitionsNode.
        """
        from py_trees.common import Status
        from vultron.core.models.case_participant import CaseParticipant
        from vultron.enums.roles import CVDRole

        # Temporarily set actor to non-VENDOR so the role guard fires.
        participant = self.dl.read(self.actor_participant.id_)
        assert isinstance(participant, CaseParticipant)
        participant.case_roles = [CVDRole.FINDER]
        self.dl.save(participant)

        bt_result, result_out = self._run_node(
            rm_state=None, vf_state=CS_vf.Vf, d_state=None, pxa_state=None
        )

        assert bt_result.status == Status.FAILURE
        assert "status_id" not in result_out
        assert "ADR-0075" in bt_result.feedback_message

    def test_deploy_requires_deployer_role_at_write_node(self):
        """CSB-15-002: D target is blocked when the actor has no DEPLOYER role.

        The actor holds VENDOR but not DEPLOYER; attempting d → D must be
        refused by the write-boundary defense-in-depth in _check_d_precondition.
        """
        from py_trees.common import Status

        bt_result, result_out = self._run_node(
            rm_state=None, vf_state=None, d_state=CS_d.D, pxa_state=None
        )

        assert bt_result.status == Status.FAILURE
        assert "status_id" not in result_out
        assert "CSB-15-002" in bt_result.feedback_message

    def test_d_not_deployed_requires_deployer_role_at_write_node(self):
        """#2963: d=d (not deployed) target is blocked when the actor has no DEPLOYER role.

        The bug: `if self._d_state == CS_d.D:` only guards the deployed state.
        A non-DEPLOYER actor asserting d=d (the initial d-unset state) bypasses
        the role guard.  The fix changes the condition to `if self._d_state is not None:`
        so any D-dimension write requires DEPLOYER role.
        """
        from py_trees.common import Status

        bt_result, result_out = self._run_node(
            rm_state=None, vf_state=None, d_state=CS_d.d, pxa_state=None
        )

        assert bt_result.status == Status.FAILURE
        assert "status_id" not in result_out
        assert "CSB-15-002" in bt_result.feedback_message

    # ------------------------------------------------------------------
    # AC-1: ephemeral-state promotion at write boundary (SM-09-001)
    # ------------------------------------------------------------------

    def test_ephemeral_pxa_pXa_promoted_before_write(self):
        """AC-1 / SM-09-001: pXa is promoted to PXa before writing."""
        from py_trees.common import Status
        from vultron.core.models.participant_status import ParticipantStatus
        from vultron.core.states.cs import CS_pxa

        bt_result, result_out = self._run_node(
            rm_state=None, vf_state=None, d_state=None, pxa_state=CS_pxa.pXa
        )

        assert bt_result.status == Status.SUCCESS
        stored = self.dl.read(result_out["status_id"])
        assert isinstance(stored, ParticipantStatus)
        assert stored.case_status is not None
        assert stored.case_status.pxa.state is CS_pxa.PXa

    def test_ephemeral_pxa_pXA_promoted_before_write(self):
        """AC-1 / SM-09-001: pXA is promoted to PXA before writing.

        pXA is reachable from pxA via the X event.  The test seeds pxA as the
        prior PXA state so the per-dimension precondition passes, then verifies
        the ephemeral pXA is promoted to PXA at the write boundary.
        """
        from py_trees.common import Status
        from vultron.core.models.participant_status import ParticipantStatus
        from vultron.core.states.cs import CS_pxa

        # pxA (attacks observed) is a valid non-ephemeral prior state.
        # From pxA, X fires → pXA (exploit public, attacks, but public unaware).
        self._seed_participant_pxa_state(CS_pxa.pxA)

        bt_result, result_out = self._run_node(
            rm_state=None, vf_state=None, d_state=None, pxa_state=CS_pxa.pXA
        )

        assert bt_result.status == Status.SUCCESS
        stored = self.dl.read(result_out["status_id"])
        assert isinstance(stored, ParticipantStatus)
        assert stored.case_status is not None
        assert stored.case_status.pxa.state is CS_pxa.PXA

    def test_ephemeral_vP_promotes_vf_when_writing_pxa(self):
        """AC-1 / SM-09-001: vP compound state forces VF promotion to Vf.

        When writing PXA=Pxa (P fires) while VF is still vf, the resulting
        vP compound state is ephemeral (vendor unaware, public aware).
        The write boundary must auto-promote VF to Vf before persisting.
        """
        from py_trees.common import Status
        from vultron.core.models.participant_status import ParticipantStatus
        from vultron.core.states.cs import CS_pxa, CS_vf

        self._seed_participant_vf_state(CS_vf.vf)

        bt_result, result_out = self._run_node(
            rm_state=None, vf_state=None, d_state=None, pxa_state=CS_pxa.Pxa
        )

        assert bt_result.status == Status.SUCCESS
        stored = self.dl.read(result_out["status_id"])
        assert isinstance(stored, ParticipantStatus)
        assert stored.vf is not None
        assert stored.vf.state is CS_vf.Vf
        assert stored.case_status is not None
        assert stored.case_status.pxa.state is CS_pxa.Pxa

    # ------------------------------------------------------------------
    # AC-3: compound CS transition validation at write boundary (SM-09-002)
    # ------------------------------------------------------------------

    def test_compound_transition_rejected_when_two_dims_change(self):
        """AC-3 / SM-09-002: simultaneous VF+PXA change is rejected.

        A single CS event changes exactly one of the six dimensions.
        Attempting to advance both VF (vf→Vf) and PXA (pxa→Pxa) in one
        write must be refused at the persistence boundary.
        """
        from py_trees.common import Status
        from vultron.core.states.cs import CS_pxa, CS_vf

        self._seed_participant_vf_state(CS_vf.vf)

        bt_result, result_out = self._run_node(
            rm_state=None,
            vf_state=CS_vf.Vf,
            d_state=None,
            pxa_state=CS_pxa.Pxa,
        )

        assert bt_result.status == Status.FAILURE
        assert "status_id" not in result_out

    def test_single_vf_step_passes_compound_check(self):
        """AC-3 / SM-09-002: a valid single-dimension VF advance is accepted."""
        from py_trees.common import Status
        from vultron.core.states.cs import CS_vf

        self._seed_participant_vf_state(CS_vf.vf)

        bt_result, result_out = self._run_node(
            rm_state=None, vf_state=CS_vf.Vf, d_state=None, pxa_state=None
        )

        assert bt_result.status == Status.SUCCESS
        assert "status_id" in result_out

    def test_validate_transitions_reports_all_dimension_errors(self):
        """#2112: the write node collects all dimension failures.

        When VF and D are simultaneously invalid (actor lacks both VENDOR and
        DEPLOYER roles), both error messages must appear in feedback_message.
        Regression test for the first-error-only bug.
        """
        from py_trees.common import Status
        from vultron.core.models.case_participant import CaseParticipant
        from vultron.core.states.cs import CS_d, CS_vf
        from vultron.enums.roles import CVDRole

        # Actor has neither VENDOR nor DEPLOYER role → both role guards fire.
        participant = self.dl.read(self.actor_participant.id_)
        assert isinstance(participant, CaseParticipant)
        participant.case_roles = [CVDRole.REPORTER]
        self.dl.save(participant)

        bt_result, result_out = self._run_node(
            rm_state=None,
            vf_state=CS_vf.Vf,  # requires VENDOR (ADR-0075)
            d_state=CS_d.D,  # requires DEPLOYER (CSB-15-002)
            pxa_state=None,
        )

        assert bt_result.status == Status.FAILURE
        assert "status_id" not in result_out
        assert "ADR-0075" in bt_result.feedback_message, (
            f"Expected VF role error (ADR-0075) in feedback_message;"
            f" got: {bt_result.feedback_message!r}"
        )
        assert "CSB-15-002" in bt_result.feedback_message, (
            f"Expected D role error (CSB-15-002) in feedback_message;"
            f" got: {bt_result.feedback_message!r}"
        )

    # ------------------------------------------------------------------
    # #3050 AC-3: the write node does not assume the guard ran (BTND-10-003)
    # ------------------------------------------------------------------

    def test_write_node_validates_without_the_trigger_guard(self):
        """AC-3: constructed directly, the write node still refuses and reports.

        Five production call sites reach this node without passing through
        ``ValidateTriggerTransitionsNode`` (``develop_fix.py``,
        ``deploy_fix.py``, ``close_case_effect.py``, two in ``leave.py``), so
        for those its check is the only validation.  ``_run_node()`` builds the
        node alone, reproducing that shape.
        """
        bt_result, result_out = self._run_node(
            rm_state=RM.CLOSED,  # START → CLOSED skips the RM ladder
            vf_state=None,
            d_state=None,
            pxa_state=CS_pxa.PXA,  # pxa → PXA is not an adjacent step
        )

        assert bt_result.status == Status.FAILURE
        assert "status_id" not in result_out, "nothing may be persisted"
        assert "Invalid RM transition" in bt_result.feedback_message
        assert "Invalid PXA transition" in bt_result.feedback_message

    def test_write_node_publishes_structured_violations_to_result_out(self):
        """AC-4/AC-6: the aggregate error is data, not just a message string."""
        bt_result, result_out = self._run_node(
            rm_state=RM.CLOSED,
            vf_state=None,
            d_state=None,
            pxa_state=CS_pxa.PXA,
        )

        assert bt_result.status == Status.FAILURE
        error = result_out.get("error")
        assert isinstance(error, VultronValidationError)

        roots = [v for v in error.violations if v.classification == "root"]
        assert [v.dimensions for v in roots] == [("rm",), ("pxa",)], (
            "both independently-broken dimensions must arrive as structured"
            f" root violations: {[v.message for v in error.violations]}"
        )

    def test_force_rm_state_exempts_only_the_rm_rule(self):
        """The case-closure override advances RM past the ladder.

        This is the behaviour ``close_case_effect.py`` and ``leave.py`` rely on
        to advance a departing participant to ``RM.CLOSED``.  It is a sanctioned
        self-declared-Leave override (CM-23-012, resolving #3106): the RM
        adjacency rule is legitimately suppressed for the single departing actor.
        The point of the test is that the exemption is narrow — every other rule
        still applies.
        """
        from vultron.core.behaviors.case.nodes.participant import (
            CreateParticipantStatusNode,
        )

        result_out: dict = {}
        node = CreateParticipantStatusNode(
            case_id=self.case.id_,
            actor_id=self.actor.id_,
            rm_state=RM.CLOSED,  # START → CLOSED, illegal but exempted
            vf_state=None,
            d_state=None,
            pxa_state=CS_pxa.PXA,  # still an illegal PXA step
            result_out=result_out,
            force_rm_state=True,
        )
        bt_result = self.bridge.execute_with_setup(
            node, actor_id=self.actor.id_
        )

        assert bt_result.status == Status.FAILURE
        assert "Invalid RM transition" not in bt_result.feedback_message
        assert "Invalid PXA transition" in bt_result.feedback_message, (
            "force_rm_state exempts the RM rule only; it is not a validation"
            f" bypass. Got: {bt_result.feedback_message!r}"
        )

    def test_force_rm_state_permits_the_closure_stamp(self):
        """The exempted write itself succeeds — today's closure behaviour."""
        from vultron.core.behaviors.case.nodes.participant import (
            CreateParticipantStatusNode,
        )
        from vultron.core.models.participant_status import ParticipantStatus

        result_out: dict = {}
        node = CreateParticipantStatusNode(
            case_id=self.case.id_,
            actor_id=self.actor.id_,
            rm_state=RM.CLOSED,
            vf_state=None,
            d_state=None,
            pxa_state=None,
            result_out=result_out,
            force_rm_state=True,
        )
        bt_result = self.bridge.execute_with_setup(
            node, actor_id=self.actor.id_
        )

        assert bt_result.status == Status.SUCCESS, bt_result.feedback_message
        stored = self.dl.read(result_out["status_id"])
        assert isinstance(stored, ParticipantStatus)
        assert stored.rm.state == RM.CLOSED


# ---------------------------------------------------------------------------
# ValidateTriggerTransitionsNode — AC-1 through AC-6 (issues #2081, #1903)
# ---------------------------------------------------------------------------


class TestValidateTriggerTransitions:
    """Trigger-path transition guard: fail-closed for invalid state jumps.

    AC-1: Invalid VF jump → VultronValidationError, no record persisted.
    AC-2: Invalid RM transition → VultronValidationError, no record persisted.
    AC-3: Backward PXA → VultronValidationError, no record persisted.
    AC-4: Same-state write → SUCCESS, record persisted.
    AC-5: None target → SUCCESS, record persisted.
    AC-6: Trigger path (end-to-end through use case) rejects invalid VF jump.

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

        self.actor = as_Service(name="Vendor")
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

    def _execute(
        self, rm_state=None, vf_state=None, d_state=None, pxa_state=None
    ):
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
            vf_state=vf_state,
            d_state=d_state,
            pxa_state=pxa_state,
        )
        return SvcAddParticipantStatusUseCase(
            self.dl, request, trigger_activity=self.trigger_activity
        ).execute()

    def _status_count(self):
        participant = self.dl.read(self.actor_participant.id_)
        return len(getattr(participant, "participant_statuses", []))

    def test_ac1_invalid_vf_jump_raises_and_persists_nothing(self):
        """AC-1: vf → VF (skips Vf) raises VultronValidationError; no record written.

        First write is RM-only; the VENDOR validator auto-seeds vf=CS_vf.vf on
        the status, establishing current_vf so the VF adjacency check fires.
        """
        from vultron.errors import VultronValidationError

        # Establish current_vf=CS_vf.vf via the VENDOR auto-seed.
        self._execute(rm_state=RM.START)
        before = self._status_count()
        with pytest.raises(VultronValidationError):
            self._execute(vf_state=CS_vf.VF)
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
        self._execute(
            rm_state=None, vf_state=None, d_state=None, pxa_state=None
        )
        assert self._status_count() == before + 1

    def test_ac6_trigger_path_rejects_invalid_vf_end_to_end(self):
        """AC-6: The add-participant-status trigger path rejects invalid VF via use case.

        Confirms the guard is wired into add_participant_status_trigger_bt
        and therefore fires for every HTTP-trigger invocation.
        """
        from vultron.errors import VultronValidationError

        # Establish current_vf via first write so the adjacency check can fire.
        self._execute(rm_state=RM.START)
        # vf → VF skips Vf — invalid.
        with pytest.raises(VultronValidationError, match="VF"):
            self._execute(vf_state=CS_vf.VF)

    def test_valid_adjacent_vf_step_succeeds(self):
        """Valid adjacent VF step (vf → Vf) is accepted and record persisted."""
        before = self._status_count()
        self._execute(vf_state=CS_vf.Vf)
        assert self._status_count() == before + 1

    def test_valid_adjacent_rm_step_succeeds(self):
        """Valid adjacent RM step (START → RECEIVED) is accepted and record persisted."""
        before = self._status_count()
        self._execute(rm_state=RM.RECEIVED)
        assert self._status_count() == before + 1

    # ------------------------------------------------------------------
    # #3050 — report every violation, reject the batch (ADR-0086)
    # ------------------------------------------------------------------

    def test_trigger_path_reports_every_violation_and_persists_nothing(self):
        """AC-4/AC-10: two illegal dimensions, both reported, nothing written.

        The fix-one-resubmit loop ISSUE-2112 reported: the caller used to be
        told about RM, fix it, resubmit, and only then hear about PXA.  Since
        the rejection is atomic nothing partial landed either, so the round trip
        bought no progress (EH-07-001).
        """
        before = self._status_count()

        with pytest.raises(VultronValidationError) as exc_info:
            self._execute(rm_state=RM.CLOSED, pxa_state=CS_pxa.PXA)

        rendered = str(exc_info.value)
        assert "Invalid RM transition" in rendered, rendered
        assert "Invalid PXA transition" in rendered, rendered
        assert self._status_count() == before, "the batch must be rejected"

    def test_trigger_path_error_carries_structured_violations(self):
        """AC-6/AC-7: the aggregate error reaches the caller as data.

        ``ValidateTriggerTransitionsNode`` writes it to ``result_out['error']``
        and ``SvcBTTriggerBase.execute()`` re-raises it, so the violation list
        survives the BT boundary without anyone parsing a joined string.
        """
        with pytest.raises(VultronValidationError) as exc_info:
            self._execute(rm_state=RM.CLOSED, pxa_state=CS_pxa.PXA)

        violations = exc_info.value.violations
        roots = [v for v in violations if v.classification == "root"]
        assert [v.dimensions for v in roots] == [("rm",), ("pxa",)], (
            "both single-dimension violations must arrive as structured data:"
            f" {[v.message for v in violations]}"
        )
        # The compound CS rule also trips (a 3-bit PXA jump is not one CS
        # event) but reads pxa, so it is reported as a consequence.
        assert any(v.classification == "derived" for v in violations)

    def test_trigger_path_labels_a_derived_violation(self):
        """AC-5/AC-10: the entailment is derived once vf itself is faulted.

        ``vf → VF`` skips ``Vf``, and the RM↔VF entailment it also trips reads
        ``vf``, so one fix clears both and only the VF step is a root cause
        (EH-07-002).
        """
        # Establish current_vf=CS_vf.vf via the VENDOR auto-seed.
        self._execute(rm_state=RM.START)

        with pytest.raises(VultronValidationError) as exc_info:
            self._execute(vf_state=CS_vf.VF)

        by_dimensions = {v.dimensions: v for v in exc_info.value.violations}
        assert by_dimensions[("vf",)].classification == "root"
        assert by_dimensions[("rm", "vf")].classification == "derived", (
            "the RM↔VF entailment is a consequence of the illegal VF step,"
            f" not an independent problem: {exc_info.value.violations}"
        )


# ---------------------------------------------------------------------------
# CheckNotSoleObserverVfdNode — CM-25-005 end-to-end guard (#2192)
# ---------------------------------------------------------------------------


class TestSoleObserverVfdGuard:
    """End-to-end guard: sole-OBSERVER actor MUST NOT emit v→V (CM-25-005).

    Uses the full use-case stack (SqliteDataLayer → SvcAddParticipantStatusUseCase)
    to prove CheckNotSoleObserverVfdNode is wired into add_participant_status_trigger_bt
    and fires for every trigger invocation.

    AC: a sole-OBSERVER actor calling execute(vf_state=CS_vf.Vf) raises
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

    def _execute(
        self, rm_state=None, vf_state=None, d_state=None, pxa_state=None
    ):
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
            vf_state=vf_state,
            d_state=d_state,
            pxa_state=pxa_state,
        )
        return SvcAddParticipantStatusUseCase(
            self.dl, request, trigger_activity=self.trigger_activity
        ).execute()

    def _status_count(self):
        participant = self.dl.read(self.actor_participant.id_)
        return len(getattr(participant, "participant_statuses", []))

    @pytest.mark.spec("CM-25-005")
    def test_sole_observer_vf_transition_blocked_end_to_end(self):
        """CM-25-005: sole-OBSERVER actor attempting v→V raises VultronValidationError."""
        from vultron.errors import VultronValidationError

        before = self._status_count()
        with pytest.raises(VultronValidationError):
            self._execute(vf_state=CS_vf.Vf)
        assert self._status_count() == before

    def test_sole_observer_none_vf_request_succeeds(self):
        """Sole-OBSERVER actor with no VF override bypasses guard; record persisted."""
        before = self._status_count()
        self._execute(
            rm_state=None, vf_state=None, d_state=None, pxa_state=None
        )
        assert self._status_count() == before + 1


# ---------------------------------------------------------------------------
# ValidateTriggerTransitionsNode — VFD role guard for VENDOR-aware states (#2862)
# ---------------------------------------------------------------------------


class TestVendorVfdRoleGuard:
    """End-to-end guard: only VENDOR actors may emit vendor-aware VF states (ADR-0075).

    V transitions (vf_state ∈ {Vf, VF}) are VENDOR-specific per ADR-0075.
    ValidateTriggerTransitionsNode MUST block any non-VENDOR actor requesting
    a vendor-aware state.

    CM-25-005 (sole-OBSERVER blocks v→V) is a weaker rule that covers
    observers-without-other-roles; this class tests the stronger VENDOR
    requirement (Closes #2862).
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

        self.vendor_actor = as_Service(name="Vendor")
        vendor_id = self.vendor_actor.id_
        reset_datalayer(vendor_id)
        self.dl = SqliteDataLayer("sqlite:///:memory:", actor_id=vendor_id)
        self.dl.clear_all()
        self.dl.create(self.vendor_actor)

        self.coord_actor = as_Service(name="Coordinator")
        reset_datalayer(self.coord_actor.id_)
        self.dl.create(self.coord_actor)

        self.case_manager_actor = as_Service(name="Case Manager")
        reset_datalayer(self.case_manager_actor.id_)
        self.dl.create(self.case_manager_actor)

        self.case = as_VulnerabilityCase(name="Test Case #2862")
        self.vendor_participant = as_CaseParticipant(
            attributed_to=vendor_id,
            context=self.case.id_,
            case_roles=[CVDRole.VENDOR],
        )
        self.coord_participant = as_CaseParticipant(
            attributed_to=self.coord_actor.id_,
            context=self.case.id_,
            case_roles=[CVDRole.COORDINATOR],
        )
        self.case_manager_participant = as_CaseParticipant(
            attributed_to=self.case_manager_actor.id_,
            context=self.case.id_,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        self.case.actor_participant_index[vendor_id] = (
            self.vendor_participant.id_
        )
        self.case.actor_participant_index[self.coord_actor.id_] = (
            self.coord_participant.id_
        )
        self.case.actor_participant_index[self.case_manager_actor.id_] = (
            self.case_manager_participant.id_
        )
        self.dl.create(self.case)
        self.dl.create(self.vendor_participant)
        self.dl.create(self.coord_participant)
        self.dl.create(self.case_manager_participant)
        self.trigger_activity = TriggerActivityAdapter(self.dl)
        yield
        try:
            self.dl.clear_all()
        finally:
            self.dl.close()
            reset_datalayer(vendor_id)
            reset_datalayer(self.coord_actor.id_)
            reset_datalayer(self.case_manager_actor.id_)

    def _execute_as(
        self, actor, rm_state=None, vf_state=None, d_state=None, pxa_state=None
    ):
        from vultron.core.use_cases.triggers.case import (
            SvcAddParticipantStatusUseCase,
        )
        from vultron.core.use_cases.triggers.requests import (
            AddParticipantStatusTriggerRequest,
        )

        request = AddParticipantStatusTriggerRequest(
            actor_id=actor.id_,
            case_id=self.case.id_,
            rm_state=rm_state,
            vf_state=vf_state,
            d_state=d_state,
            pxa_state=pxa_state,
        )
        return SvcAddParticipantStatusUseCase(
            self.dl, request, trigger_activity=self.trigger_activity
        ).execute()

    def _status_count(self, participant_id):
        participant = self.dl.read(participant_id)
        return len(getattr(participant, "participant_statuses", []))

    def test_vendor_actor_can_emit_vendor_aware_vf(self):
        """VENDOR actor submitting vf_state=Vf (v→V) succeeds (ADR-0075)."""
        before = self._status_count(self.vendor_participant.id_)
        self._execute_as(self.vendor_actor, vf_state=CS_vf.Vf)
        assert self._status_count(self.vendor_participant.id_) == before + 1

    def test_non_vendor_coordinator_blocked_for_vendor_aware_vf(self):
        """COORDINATOR (non-VENDOR) submitting vf_state=Vf is blocked (ADR-0075, #2862)."""
        from vultron.errors import VultronValidationError

        before = self._status_count(self.coord_participant.id_)
        with pytest.raises(VultronValidationError):
            self._execute_as(self.coord_actor, vf_state=CS_vf.Vf)
        assert self._status_count(self.coord_participant.id_) == before


# ---------------------------------------------------------------------------
# ValidateTriggerTransitionsNode — cross-machine entailments (#2236)
# ---------------------------------------------------------------------------


class TestCrossMachineEntailments:
    """Trigger-path cross-machine entailment guard (#2236).

    CSB-18-001: VF F bit (CS_vf.VF) requires RM ∈ {ACCEPTED, DEFERRED, CLOSED}.
    Both RM and VF are per-actor attributes; a contradictory combination is
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

    def _execute(
        self, rm_state=None, vf_state=None, d_state=None, pxa_state=None
    ):
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
            vf_state=vf_state,
            d_state=d_state,
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

    # --- CSB-18-001: RM ↔ VF entailment ---

    def test_csb18_001_vf_fix_ready_with_rm_received_raises(self):
        """CSB-18-001: Vf → VF while RM is RECEIVED raises (FCV motivating case).

        The actor advances to vendor-aware (Vf) while still at RM.RECEIVED,
        then tries to assert fix-ready (VF). This is the FCV failure pattern:
        fix readiness requires RM.ACCEPTED.
        """
        from vultron.errors import VultronValidationError

        # Valid combined step: vendor becomes aware while reporting received.
        self._execute(rm_state=RM.RECEIVED, vf_state=CS_vf.Vf)
        before = self._status_count()
        # Cross-machine violation: VF requires RM ≥ ACCEPTED; current is RECEIVED.
        with pytest.raises(VultronValidationError, match="Cross-machine"):
            self._execute(vf_state=CS_vf.VF)
        assert self._status_count() == before

    def test_csb18_001_vf_fix_ready_with_current_rm_valid_raises(self):
        """CSB-18-001: Vf → VF when actor is at RM.VALID raises.

        After advancing to RM.VALID and Vf, the actor must not assert VF
        because fix readiness requires RM.ACCEPTED.
        """
        from vultron.errors import VultronValidationError

        self._execute(rm_state=RM.RECEIVED)
        self._execute(rm_state=RM.VALID)
        self._execute(vf_state=CS_vf.Vf)
        before = self._status_count()
        with pytest.raises(VultronValidationError, match="Cross-machine"):
            self._execute(vf_state=CS_vf.VF)
        assert self._status_count() == before

    def test_csb18_001_vf_fix_ready_with_rm_accepted_succeeds(self):
        """CSB-18-001: Vf → VF when actor is at RM.ACCEPTED is valid."""
        self._advance_rm_to_accepted()
        self._execute(vf_state=CS_vf.Vf)
        before = self._status_count()
        self._execute(vf_state=CS_vf.VF)
        assert self._status_count() == before + 1

    def test_csb18_001_vf_fix_deployed_with_rm_accepted_succeeds(self):
        """CSB-18-001: VF + d→D when actor is at RM.ACCEPTED is valid.

        DEPLOYER role is required for the d→D dimension; the participant is
        re-registered with CVDRole.VENDOR+DEPLOYER before the test.
        """
        from vultron.enums.roles import CVDRole
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )

        # Re-register the participant as VENDOR+DEPLOYER so the d dimension is active.
        deployer_participant = as_CaseParticipant(
            id_=self.actor_participant.id_,
            attributed_to=self.actor.id_,
            context=self.case.id_,
            case_roles=[CVDRole.VENDOR, CVDRole.DEPLOYER],
        )
        self.dl.save(deployer_participant)

        self._advance_rm_to_accepted()
        self._execute(vf_state=CS_vf.Vf)
        self._execute(vf_state=CS_vf.VF)
        before = self._status_count()
        self._execute(d_state=CS_d.D)
        assert self._status_count() == before + 1

    def test_csb18_001_vf_vendor_aware_with_rm_received_succeeds(self):
        """CSB-18-001: vf → Vf when actor is at RM.RECEIVED is valid.

        The V bit (vendor aware) has no RM constraint; only F/D bits do.
        """
        before = self._status_count()
        self._execute(rm_state=RM.RECEIVED, vf_state=CS_vf.Vf)
        assert self._status_count() == before + 1

    def test_pxa_public_aware_succeeds(self):
        """Asserting Pxa (P bit) is valid — PXA is an actor-level attribute."""
        from vultron.core.states.cs import CS_pxa

        before = self._status_count()
        self._execute(pxa_state=CS_pxa.Pxa)
        assert self._status_count() == before + 1

    def test_csb17_001_vf_not_ready_and_d_deployed_rejected(self):
        """CSB-17-001: vf != VF with d=D is structurally impossible — trigger rejects it.

        The compound *fD* state (fix deployed but fix not ready) is forbidden.
        The trigger path must refuse it even when RM and individual VF/D
        transitions are valid in isolation (#2893).
        """
        from vultron.errors import VultronValidationError

        # Register participant as VENDOR+DEPLOYER so the D dimension guard passes.
        from vultron.enums.roles import CVDRole
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )

        deployer_participant = as_CaseParticipant(
            id_=self.actor_participant.id_,
            attributed_to=self.actor.id_,
            context=self.case.id_,
            case_roles=[CVDRole.VENDOR, CVDRole.DEPLOYER],
        )
        self.dl.save(deployer_participant)

        # Advance to RM.ACCEPTED so the RM↔D entailment is satisfied.
        self._advance_rm_to_accepted()
        # Move VF to Vf (vendor aware, fix NOT ready).
        self._execute(vf_state=CS_vf.Vf)
        # Now try to assert d=D without vf=VF — must be refused.
        before = self._status_count()
        with pytest.raises(VultronValidationError, match="Cross-machine"):
            self._execute(d_state=CS_d.D)
        assert (
            self._status_count() == before
        ), "Status count must not increase when vf≠VF + d=D (CSB-17-001)"


class TestViolationPxaEmEntailment:
    """Unit tests for violation_pxa_em_entailment() (CSB-18-002..004).

    These rules are provided for future receive-path enforcement and are NOT
    wired into the emit path.  Tests document the expected semantics so future
    maintainers have a baseline when adding the receive-path guard.
    """

    def _check(self, pxa, em):
        from vultron.core.states.composite_state_invariants import (
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


class TestCreateParticipantStatusNodeCrossMachineOnBypassPath:
    """CreateParticipantStatusNode enforces cross-machine entailments (#3100).

    Bypass callers (DevelopFixNode, DeployFixNode, etc.) reach
    CreateParticipantStatusNode without going through
    ValidateTriggerTransitionsNode.  The write node must reject a
    CSB-18-001/CSB-17-001 violation so those callers cannot persist an
    impossible RM+VF or VF+D combination.
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

        self.actor = as_Service(name="Vendor Bypass")
        actor_id = self.actor.id_
        reset_datalayer(actor_id)
        self.dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor_id)
        self.dl.clear_all()
        self.dl.create(self.actor)

        self.case_actor = as_Service(name="Case Actor Bypass")
        reset_datalayer(self.case_actor.id_)
        self.dl.create(self.case_actor)

        self.case = as_VulnerabilityCase(name="Test Case #3100")
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

    def test_vf_fix_ready_with_rm_start_rejected_by_write_node(self):
        """CSB-18-001 bypass guard (#3100): write node refuses VF=VF when RM=START.

        CreateParticipantStatusNode now calls composite_state_violations() so a
        caller that bypasses ValidateTriggerTransitionsNode cannot persist a
        state that the trigger guard would have refused.
        """
        from py_trees.common import Status

        bt_result, result_out = self._run_node(
            rm_state=None, vf_state=CS_vf.VF, d_state=None, pxa_state=None
        )

        assert bt_result.status == Status.FAILURE
        assert "status_id" not in result_out


def test_validate_trigger_returns_failure_on_corrupt_participant_status():
    """#3103: VultronValidationError from resolve_participant_state_from_dl is caught.

    Before the fix, a participant with a non-core-shaped status let
    VultronValidationError escape update(), producing a 500.  After the fix the
    node returns Status.FAILURE with a descriptive feedback_message.

    Uses a stubbed DataLayer so the bad RM state bypasses the SQLite adapter's
    rehydration path — matching the test pattern at line 176 in this file.
    """
    from py_trees.common import Status
    from vultron.core.behaviors.case.nodes.participant.trigger_validation import (
        ValidateTriggerTransitionsNode,
    )

    ACTOR_ID = "https://example.org/corrupt-vendor"
    CASE_ID = "https://example.org/case-3103"
    PARTICIPANT_ID = "https://example.org/participant-3103"

    class _BadRmDim:
        state = "not-an-rm"

    class _CorruptStatus:
        rm = _BadRmDim()
        vf = None
        d = None

    class _CorruptParticipant:
        participant_statuses = [_CorruptStatus()]

    class _StubCase:
        actor_participant_index = {ACTOR_ID: PARTICIPANT_ID}
        case_participants: list = []

    class _StubDL:
        def read_case(self, case_id: str):
            return _StubCase()

        def read(self, id_: str):
            return _CorruptParticipant()

    node = ValidateTriggerTransitionsNode(
        case_id=CASE_ID,
        actor_id=ACTOR_ID,
        rm_state=RM.RECEIVED,
        vf_state=None,
        d_state=None,
        pxa_state=None,
        result_out={},
    )
    node.datalayer = _StubDL()  # type: ignore[assignment]

    result = node.update()

    assert result == Status.FAILURE
    assert "core-shaped" in node.feedback_message
