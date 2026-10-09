"""Tree-level tests for the received ``Create(VulnerabilityCase)`` bootstrap.

The handler-level dispositions are covered in
``test/core/use_cases/received/case/test_create.py``; these tests pin what is
specific to the tree (#3874, CLP-10-005, CLP-10-007): the route is chosen once,
a refusal is reported with the chosen route's own reason, and intake archives
the Create whatever the verdict (CLP-10-018).
"""

import pytest
from py_trees.common import Status

from test.support.embargo_register import register
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.create_case_received_tree import (
    create_create_case_received_tree,
)
from vultron.core.behaviors.case.nodes.replica_bootstrap import (
    ClassifyBootstrapRouteNode,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.use_cases.received._bt_verdict import find_node
from vultron.enums.roles import CVDRole
from vultron.semantic_registry import extract_event
from vultron.wire.as2.factories import create_case_activity
from vultron.wire.as2.vocab.objects.case_participant import (
    as_CaseParticipant,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

_RECEIVER = "https://example.org/actors/reporter"
_CREATOR = "https://example.org/actors/creator"
_IMPOSTER = "https://example.org/actors/imposter"
_CASE_ID = "https://example.org/cases/tree-test"
_REPORT_ID = "https://example.org/reports/tree-test"


@pytest.fixture
def make_payload():
    """Extract the received event from an AS2 activity."""
    return extract_event


@pytest.fixture
def dl() -> SqliteDataLayer:
    return SqliteDataLayer("sqlite:///:memory:", actor_id=_RECEIVER)


def _case(manager: str = _CREATOR) -> as_VulnerabilityCase:
    participant = as_CaseParticipant(
        case_roles=[CVDRole.CASE_MANAGER],
        id_=f"{_CASE_ID}/participants/manager",
        attributed_to=manager,
        context=_CASE_ID,
        name="manager",
    )
    return as_VulnerabilityCase.model_construct(
        id_=_CASE_ID, name="tree test", case_participants=[participant]
    )


def _run(dl, make_payload, sender: str, case: as_VulnerabilityCase):
    activity = create_case_activity(case, actor=sender)
    event = make_payload(activity)
    tree = create_create_case_received_tree(event.case, _CASE_ID, sender)
    result = BTBridge(datalayer=dl).execute_with_setup(
        tree=tree, actor_id=_RECEIVER, activity=event
    )
    classify = find_node(tree, ClassifyBootstrapRouteNode)
    assert classify is not None
    return tree, result, classify.route, activity


def _link(creator: str | None = _CREATOR) -> VultronReportCaseLink:
    return VultronReportCaseLink(
        report_id=_REPORT_ID, case_id=None, case_creator_id=creator
    )


def test_pending_link_selects_the_trusted_route(dl, make_payload):
    link = _link()
    dl.save(link)

    _, result, route, _ = _run(dl, make_payload, _CREATOR, _case())

    assert result.status == Status.SUCCESS
    assert route.name == "trusted"
    assert route.replica_stored is True
    assert isinstance(dl.read(_CASE_ID), VulnerabilityCase)
    bound = dl.read(link.id_)
    assert isinstance(bound, VultronReportCaseLink)
    assert bound.case_id == _CASE_ID


def test_route_is_chosen_before_the_trusted_write_changes_the_answer(
    dl, make_payload
):
    """Binding the link makes a re-derived route read ``redelivery``."""
    dl.save(_link())

    _, _, route, _ = _run(dl, make_payload, _CREATOR, _case())

    assert route.name == "trusted"


def test_bound_link_selects_redelivery_and_writes_nothing(dl, make_payload):
    dl.save(
        VultronReportCaseLink(
            report_id=_REPORT_ID, case_id=_CASE_ID, case_creator_id=_CREATOR
        )
    )

    _, result, route, _ = _run(dl, make_payload, _CREATOR, _case())

    assert result.status == Status.SUCCESS
    assert route.name == "redelivery"
    assert route.replica_stored is False
    assert dl.read(_CASE_ID) is None


def test_no_link_and_manager_sender_selects_direct(dl, make_payload):
    _, result, route, _ = _run(dl, make_payload, _CREATOR, _case())

    assert result.status == Status.SUCCESS
    assert route.name == "direct"
    assert route.replica_stored is True


def test_refusal_carries_the_chosen_routes_reason(dl, make_payload):
    """A trusted-route refusal is that route's, not a later arm's gate."""
    dl.save(_link())
    unheld = f"{_CASE_ID}/embargo_events/unheld"
    case = _case().model_copy(
        update={"embargo_register": register(active=unheld)}
    )
    # A participant carries a row for every register entry (ADR-0122).
    for participant in case.case_participants:
        assert isinstance(participant, as_CaseParticipant)
        participant.write_uninvited_rows([unheld])

    tree, result, route, _ = _run(dl, make_payload, _CREATOR, case)

    assert result.status == Status.FAILURE
    assert route.name == "trusted"
    assert "EMB-18-003" in BTBridge.get_failure_reason(tree)
    assert dl.read(_CASE_ID) is None


def test_direct_refusal_names_the_untrusted_sender(dl, make_payload):
    tree, result, route, _ = _run(dl, make_payload, _IMPOSTER, _case())

    assert result.status == Status.FAILURE
    assert route.name == "direct"
    assert "ADR-0041" in BTBridge.get_failure_reason(tree)
    assert dl.read(_CASE_ID) is None


def test_intake_archives_the_create_even_when_refused(dl, make_payload):
    _, result, _, activity = _run(dl, make_payload, _IMPOSTER, _case())

    assert result.status == Status.FAILURE
    assert isinstance(
        dl.read(ReceivedActivityRecord.build_id(activity.id_)),
        ReceivedActivityRecord,
    )


def test_bare_participant_refusal_leaves_the_link_unbound(dl, make_payload):
    """CBT-01-007: a bare-URI participant is refused before anything is written."""
    link = _link()
    dl.save(link)
    case = as_VulnerabilityCase.model_construct(
        id_=_CASE_ID, name="bare", case_participants=["urn:x:bare-participant"]
    )

    tree, result, route, _ = _run(dl, make_payload, _CREATOR, case)

    assert result.status == Status.FAILURE
    assert route.name == "trusted"
    assert "CBT-01-007" in BTBridge.get_failure_reason(tree)
    assert dl.read(_CASE_ID) is None
    unbound = dl.read(link.id_)
    assert isinstance(unbound, VultronReportCaseLink)
    assert unbound.case_id is None
