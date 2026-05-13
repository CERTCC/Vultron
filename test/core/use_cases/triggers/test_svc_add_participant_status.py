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

from vultron.core.states.cs import CS_vfd
from vultron.core.states.rm import RM

# ---------------------------------------------------------------------------
# Test stubs
# ---------------------------------------------------------------------------


class _FakeParticipantStatus:
    """Minimal stand-in for VultronParticipantStatus."""

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
