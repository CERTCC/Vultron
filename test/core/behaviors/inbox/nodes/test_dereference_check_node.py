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
"""The inbox's dereference step, through ``process_payload`` (AKM-05-007)."""

import json
import logging
from typing import Any

import py_trees
import pytest
from py_trees.ports import NoDataAvailable

from vultron.core.behaviors.inbox import InboxOutcomeStatus, process_payload
from vultron.core.behaviors.inbox.nodes import (
    KEY_DEREFERENCE,
    DereferenceCheckNode,
)
from vultron.core.models.actor import CoreActor, VultronOrganization
from vultron.core.models.base import CoreObject
from vultron.core.models.events import VultronEvent
from vultron.core.models.object_fetch import (
    ObjectFetchSource,
    ObjectFetchState,
    ObjectFetchUse,
    ObjectReference,
    PendingObjectFetch,
)
from vultron.core.models.use_case_result import HandlerResult
from vultron.errors import VultronValidationError
from vultron.wire.as2.parser import parse_activity

_PROPOSER = "https://example.org/actors/vendor"
_CASE_ACTOR = "https://example.org/actors/case-actor"

_PROFILE_REF = ObjectReference(
    object_id=_PROPOSER,
    source=ObjectFetchSource.ACTOR_PROFILE,
    host_actor_id=_PROPOSER,
    use=ObjectFetchUse.HAND_OFF,
)


def _proposal() -> Any:
    """A ``Create(CaseProposal)`` naming its proposer by id."""
    return parse_activity(
        {
            "type": "Create",
            "id": "https://example.org/activities/create-proposal",
            "published": "2026-10-26T12:00:00Z",
            "actor": _PROPOSER,
            "to": [_CASE_ACTOR],
            "object": {
                "type": "CaseProposal",
                "id": "https://example.org/proposals/p-1",
                "attributedTo": _PROPOSER,
                "object": {
                    "type": "VulnerabilityReport",
                    "id": "https://example.org/reports/r-1",
                    "name": "A report",
                    "content": "Details",
                    "attributedTo": _PROPOSER,
                },
                "target": _CASE_ACTOR,
            },
        }
    )


class _Ingress:
    def __init__(self, activity: Any) -> None:
        self._activity = activity

    def parse(self, payload: Any) -> Any:
        return self._activity

    def rehydrate(self, activity: Any) -> Any:
        return activity


class _Dispatch:
    def __init__(self) -> None:
        self.dispatched: list[VultronEvent] = []

    def dispatch(self, event: VultronEvent) -> HandlerResult:
        self.dispatched.append(event)
        return HandlerResult.applied()

    def emit_processing_fault(
        self, event: VultronEvent, failure_class: str
    ) -> None:
        raise AssertionError("no fault expected")


class _Port:
    """An ObjectDereferencePort answering from a fixed fetch record."""

    def __init__(
        self,
        references: list[ObjectReference],
        fetch: PendingObjectFetch | None = None,
        fetched: CoreObject | None = None,
    ) -> None:
        self._references = references
        self._fetch = fetch
        self._fetched = fetched
        self.awaited: list[tuple[str, list[ObjectReference]]] = []
        self.released: list[tuple[str, str]] = []

    def references_to_fetch(
        self, event: VultronEvent, context_id: str | None
    ) -> list[ObjectReference]:
        return self._references

    def fetch_of(self, object_id: str) -> PendingObjectFetch | None:
        return self._fetch

    def await_fetches(
        self, activity_id: str, references: list[ObjectReference]
    ) -> None:
        self.awaited.append((activity_id, references))

    def fetched_object(self, fetch: PendingObjectFetch) -> CoreObject:
        if self._fetched is None:
            raise VultronValidationError("the fetched body is unreadable")
        return self._fetched

    def release(self, object_id: str, activity_id: str) -> None:
        self.released.append((object_id, activity_id))


def _record(state: ObjectFetchState) -> PendingObjectFetch:
    extra: dict[str, Any] = {"state": state}
    if state is ObjectFetchState.FETCHED:
        extra["fetched_body"] = json.dumps({"id": _PROPOSER})
    if state is ObjectFetchState.FAILED:
        extra["failure_reason"] = "unreachable"
    return PendingObjectFetch.for_reference(_PROFILE_REF).model_copy(
        update=extra
    )


def _run(port: _Port | None) -> tuple[Any, _Dispatch]:
    dispatch = _Dispatch()
    outcome = process_payload(
        {}, _Ingress(_proposal()), dispatch, dereference_port=port
    )
    return outcome, dispatch


@pytest.mark.spec("AKM-05-007")
def test_with_no_port_the_activity_goes_straight_to_dispatch():
    outcome, dispatch = _run(None)

    assert outcome.status is InboxOutcomeStatus.PROCESSED
    assert len(dispatch.dispatched) == 1


@pytest.mark.spec("AKM-05-007")
def test_an_activity_needing_nothing_goes_to_dispatch():
    port = _Port([])

    outcome, dispatch = _run(port)

    assert outcome.status is InboxOutcomeStatus.PROCESSED
    assert len(dispatch.dispatched) == 1
    assert port.awaited == []


@pytest.mark.spec("AKM-05-010")
@pytest.mark.spec("AKM-05-007")
@pytest.mark.parametrize("pending", [None, ObjectFetchState.PENDING])
def test_an_activity_waits_while_its_fetch_is_open(
    pending: ObjectFetchState | None,
):
    port = _Port([_PROFILE_REF], _record(pending) if pending else None)

    outcome, dispatch = _run(port)

    assert outcome.status is InboxOutcomeStatus.DEFERRED
    assert outcome.failure_reason is not None
    assert _PROPOSER in outcome.failure_reason
    assert dispatch.dispatched == []
    assert port.awaited == [
        ("https://example.org/activities/create-proposal", [_PROFILE_REF])
    ]


@pytest.mark.spec("CP-01-009")
def test_a_fetched_profile_is_handed_to_the_event_and_released():
    profile = VultronOrganization(id_=_PROPOSER, name="Vendor")
    port = _Port([_PROFILE_REF], _record(ObjectFetchState.FETCHED), profile)

    outcome, dispatch = _run(port)

    assert outcome.status is InboxOutcomeStatus.PROCESSED
    (event,) = dispatch.dispatched
    assert getattr(event, "proposer_profile", None) == profile
    assert port.released == [
        (_PROPOSER, "https://example.org/activities/create-proposal")
    ]


@pytest.mark.spec("AKM-05-015")
@pytest.mark.spec("AKM-05-008")
def test_a_failed_fetch_lets_the_activity_go_on_with_its_reference():
    port = _Port([_PROFILE_REF], _record(ObjectFetchState.FAILED))

    outcome, dispatch = _run(port)

    assert outcome.status is InboxOutcomeStatus.PROCESSED
    (event,) = dispatch.dispatched
    assert getattr(event, "proposer_profile", None) == _PROPOSER
    assert len(port.released) == 1


@pytest.mark.spec("AKM-05-014")
@pytest.mark.spec("AKM-05-008")
def test_an_unfit_fetched_object_is_a_warning_and_a_failed_fetch(
    caplog: pytest.LogCaptureFixture,
):
    port = _Port([_PROFILE_REF], _record(ObjectFetchState.FETCHED), None)

    with caplog.at_level(logging.WARNING):
        outcome, dispatch = _run(port)

    assert outcome.status is InboxOutcomeStatus.PROCESSED
    (event,) = dispatch.dispatched
    assert not isinstance(getattr(event, "proposer_profile", None), CoreActor)
    assert any(
        r.levelno == logging.WARNING and "unfit" in r.getMessage()
        for r in caplog.records
    )


def test_an_unwired_port_input_raises_no_data_available():
    py_trees.blackboard.Blackboard.clients.clear()
    node = DereferenceCheckNode(name="DereferenceCheckNode")
    node.setup_ports()

    with pytest.raises(NoDataAvailable):
        node.get_input(KEY_DEREFERENCE)
