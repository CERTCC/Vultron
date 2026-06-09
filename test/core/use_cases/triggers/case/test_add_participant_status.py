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

"""Unit tests for SvcAddParticipantStatusUseCase.

Focused on ``_resolve_current_participant_state()`` — the private helper
that extracts the latest ``(RM, CS_vfd)`` pair from a participant record.
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
