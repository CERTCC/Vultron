"""Tree-level tests for the received ``Create(VulnerabilityCase)`` bootstrap.

The handler-level dispositions are covered in
``test/core/use_cases/received/case/test_create.py``; these tests pin what is
specific to the tree (#3874, CLP-10-005, CLP-10-007): the route is chosen once,
a refusal is reported with the chosen route's own reason, and intake archives
the Create whatever the verdict (CLP-10-018).
"""

from typing import cast

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
from vultron.core.behaviors.sender_entitlement import (
    SenderIsExpectedCaseCreatorNode,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.embargo_register import carry_embargo_inline
from vultron.core.models.events.case import CreateCaseReceivedEvent
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.core.models.report import VulnerabilityReport
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.use_cases.received._bt_verdict import find_node, node_failed
from vultron.core.use_cases.received.case.create import (
    CreateCaseReceivedUseCase,
)
from vultron.enums.roles import CVDRole
from vultron.semantic_registry import extract_event
from vultron.wire.as2.factories import create_case_activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Create,
)
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
        id_=_CASE_ID,
        name="tree test",
        case_participants=[participant],
        vulnerability_reports=[_REPORT_ID],
    )


def _run(dl, make_payload, sender: str, case: as_VulnerabilityCase):
    activity = create_case_activity(case, actor=sender, to=[_RECEIVER])
    event = make_payload(activity)
    tree = create_create_case_received_tree(
        event.case,
        _CASE_ID,
        sender,
        sender_rule=CreateCaseReceivedUseCase.sender_entitlement,
    )
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


@pytest.mark.spec("CBT-01-005")
def test_a_sender_id_differing_by_a_trailing_slash_is_the_anchored_creator(
    dl, make_payload
):
    """The guard and the route compare actor ids the same way, so the one
    actor written two ways takes the trusted route (#4522)."""
    dl.save(_link())

    _, result, route, _ = _run(dl, make_payload, f"{_CREATOR}/", _case())

    assert result.status == Status.SUCCESS
    assert route.name == "trusted"
    assert isinstance(dl.read(_CASE_ID), VulnerabilityCase)


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


@pytest.mark.spec("CBT-01-011")
@pytest.mark.spec("HP-01-008")
def test_no_anchor_is_refused_though_the_snapshot_names_the_sender_manager(
    dl, make_payload
):
    """#4472: the sender's own roster is not an anchor, so nothing is stored.

    The composed sender guard refuses it before any route is chosen.
    """
    tree, result, route, _ = _run(dl, make_payload, _CREATOR, _case())

    assert result.status == Status.FAILURE
    assert node_failed(tree, SenderIsExpectedCaseCreatorNode)
    assert route.name is None
    assert route.replica_stored is False
    assert dl.read(_CASE_ID) is None


@pytest.mark.spec("CBT-01-011")
def test_a_link_bound_to_another_case_does_not_vouch_for_this_one(
    dl, make_payload
):
    """A creator anchored for one case is not trusted to bootstrap another."""
    dl.save(
        VultronReportCaseLink(
            report_id=_REPORT_ID,
            case_id="https://example.org/cases/another",
            case_creator_id=_CREATOR,
        )
    )

    tree, result, route, _ = _run(dl, make_payload, _CREATOR, _case())

    assert result.status == Status.FAILURE
    assert node_failed(tree, SenderIsExpectedCaseCreatorNode)
    assert route.name is None
    assert dl.read(_CASE_ID) is None


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


@pytest.mark.spec("CBT-01-011")
def test_unanchored_refusal_names_the_untrusted_sender(dl, make_payload):
    tree, result, route, _ = _run(dl, make_payload, _IMPOSTER, _case())

    assert result.status == Status.FAILURE
    assert route.name is None
    reason = BTBridge.get_failure_reason(tree)
    assert _IMPOSTER in reason
    assert "CBT-01-011" in reason
    assert dl.read(_CASE_ID) is None


def test_intake_archives_the_create_even_when_refused(dl, make_payload):
    _, result, _, activity = _run(dl, make_payload, _IMPOSTER, _case())

    assert result.status == Status.FAILURE
    assert isinstance(
        dl.read(ReceivedActivityRecord.build_id(activity.id_)),
        ReceivedActivityRecord,
    )


def test_bare_participant_refusal_leaves_the_link_unbound(dl, make_payload):
    """CBT-01-012: a bare-URI participant is refused before anything is written."""
    link = _link()
    dl.save(link)
    case = as_VulnerabilityCase.model_construct(
        id_=_CASE_ID,
        name="bare",
        case_participants=["urn:x:bare-participant"],
        vulnerability_reports=[_REPORT_ID],
    )

    tree, result, route, _ = _run(dl, make_payload, _CREATOR, case)

    assert result.status == Status.FAILURE
    assert route.name == "trusted"
    assert "CBT-01-012" in BTBridge.get_failure_reason(tree)
    assert dl.read(_CASE_ID) is None
    unbound = dl.read(link.id_)
    assert isinstance(unbound, VultronReportCaseLink)
    assert unbound.case_id is None


# ---------------------------------------------------------------------------
# CBT-01-001 / CM-12-003: the report receiver introduces the CASE_MANAGER to
# the reporter with its own Create(VulnerabilityCase) (ADR-0132).
# ---------------------------------------------------------------------------

_OWNER = "https://example.org/actors/vendor"
_REPORTER = "https://example.org/actors/finder-reporter"
_FINDER = "https://example.org/actors/inert-finder"


def _participant(
    actor_id: str,
    role: CVDRole,
    consents: list[EmbargoConsent] | None = None,
    also: CVDRole | None = None,
) -> as_CaseParticipant:
    return as_CaseParticipant(
        case_roles=[role] if also is None else [role, also],
        id_=f"{_CASE_ID}/participants/{actor_id.rsplit('/', 1)[-1]}",
        attributed_to=actor_id,
        context=_CASE_ID,
        embargo_consents=consents or [],
    )


def _owned_case(
    manager: str = _CREATOR,
    *,
    embargo_id: str | None = None,
    extra: tuple[as_CaseParticipant, ...] = (),
) -> as_VulnerabilityCase:
    """A case the CASE_MANAGER *manager* made for the owner's report."""
    seats = (
        [_participant(_OWNER, CVDRole.CASE_OWNER, also=CVDRole.CASE_MANAGER)]
        if manager == _OWNER
        else [
            _participant(manager, CVDRole.CASE_MANAGER),
            _participant(_OWNER, CVDRole.CASE_OWNER),
        ]
    )
    participants: list[as_CaseParticipant] = [*seats, *extra]
    if embargo_id:
        # A participant carries a row for every register entry (ADR-0122).
        for p in participants:
            if not p.embargo_consents:
                p.write_uninvited_rows([embargo_id])
    case = as_VulnerabilityCase(
        id_=_CASE_ID,
        name="introduction test",
        attributed_to=_OWNER,
        case_participants=list[str | as_CaseParticipant](participants),
        vulnerability_reports=[_REPORT_ID],
        embargo_register=register(active=embargo_id) if embargo_id else [],
    )
    for p in participants:
        case.actor_participant_index[str(p.attributed_to)] = p.id_
    return case


def _owner_store() -> SqliteDataLayer:
    """The owner's store, holding the report the reporter sent it."""
    owner_dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_OWNER)
    owner_dl.create(
        VulnerabilityReport(id_=_REPORT_ID, attributed_to=_REPORTER)
    )
    return owner_dl


def _run_at_owner(
    case: as_VulnerabilityCase,
    sender: str = _CREATOR,
    owner_dl: SqliteDataLayer | None = None,
    *,
    pending_link: bool = True,
) -> tuple[SqliteDataLayer, Status]:
    """Run the bootstrap tree at the owner, which expects *sender*'s Create.

    With *pending_link* the owner's link is reset to pending first, so the
    tree takes the trusted route; without it a link the first run bound
    stays bound, so the tree takes the redelivery route.
    """
    from vultron.adapters.driven.trigger_activity_adapter import (
        TriggerActivityAdapter,
    )

    if owner_dl is None:
        owner_dl = _owner_store()
    if pending_link:
        owner_dl.save(_link(creator=sender))
    activity = create_case_activity(case, actor=sender, to=[_OWNER])
    event = cast(CreateCaseReceivedEvent, extract_event(activity))
    tree = create_create_case_received_tree(
        event.case,
        _CASE_ID,
        sender,
        sender_rule=CreateCaseReceivedUseCase.sender_entitlement,
    )
    result = BTBridge(
        datalayer=owner_dl, trigger_activity=TriggerActivityAdapter(owner_dl)
    ).execute_with_setup(tree=tree, actor_id=_OWNER, activity=event)
    return owner_dl, result.status


def _introductions(owner_dl: SqliteDataLayer) -> list[as_Create]:
    return [
        create
        for create in owner_dl.list_objects("Create")
        if isinstance(create, as_Create) and _as_id(create.actor) == _OWNER
    ]


@pytest.mark.spec("CBT-01-001")
@pytest.mark.spec("CBT-01-007")
@pytest.mark.spec("CM-12-003")
def test_report_receiver_introduces_the_case_manager_to_the_reporter():
    """The owner sends the reporter the whole case, naming the CASE_MANAGER."""
    owner_dl, status = _run_at_owner(
        _owned_case(extra=(_participant(_REPORTER, CVDRole.REPORTER),))
    )

    assert status == Status.SUCCESS
    [intro] = _introductions(owner_dl)
    assert intro.to == [_REPORTER]
    assert intro.id_ in owner_dl.outbox_list()
    from vultron.adapters.outbox_sealed_body import read_sealed_body_dict

    sealed = read_sealed_body_dict(owner_dl, intro.id_)
    assert sealed is not None
    case = sealed["object"]
    participants = case["caseParticipants"]
    assert all(isinstance(p, dict) for p in participants)
    managers = [
        p["attributedTo"]
        for p in participants
        if CVDRole.CASE_MANAGER.value in p["caseRoles"]
    ]
    assert managers == [_CREATOR]
    reports = case["vulnerabilityReports"]
    assert [r["id"] for r in reports] == [_REPORT_ID]


@pytest.mark.spec("CM-10-004")
@pytest.mark.spec("CM-12-003")
def test_bootstrap_addressees_withhold_an_inert_finder():
    """Under an active embargo only a signatory reporter is introduced.

    The introduction is case content, so its REPORTER/FINDER addressees come
    from the shared active selection (CM-10-007): a FINDER with no AGREED row
    for the embargo is left out.
    """
    from vultron.core.models._helpers import days_from_now_utc
    from vultron.core.models.embargo_event import EmbargoEvent
    from vultron.core.states.participant_embargo_consent import (
        EmbargoConsentState,
    )

    embargo = EmbargoEvent(
        id_=f"{_CASE_ID}/embargo",
        context=_CASE_ID,
        end_time=days_from_now_utc(45),
    )
    agreed = [
        EmbargoConsent(
            embargo_id=embargo.id_, state=EmbargoConsentState.AGREED
        )
    ]
    uninvited = [
        EmbargoConsent(
            embargo_id=embargo.id_, state=EmbargoConsentState.UNINVITED
        )
    ]
    case = _owned_case(
        embargo_id=embargo.id_,
        extra=(
            _participant(_REPORTER, CVDRole.REPORTER, agreed),
            _participant(_FINDER, CVDRole.REPORTER, uninvited),
        ),
    )
    case = case.model_copy(
        update={
            "embargo_register": carry_embargo_inline(
                case.embargo_register, embargo
            )
        }
    )

    owner_dl, status = _run_at_owner(case)

    assert status == Status.SUCCESS
    [intro] = _introductions(owner_dl)
    assert intro.to == [_REPORTER]


@pytest.mark.spec("CBT-02-001")
def test_receiver_that_is_the_case_manager_sends_no_second_create():
    """A receiver holding CASE_MANAGER is not introducing anyone (AC-4)."""
    owner_dl, status = _run_at_owner(
        _owned_case(
            manager=_OWNER,
            extra=(_participant(_REPORTER, CVDRole.REPORTER),),
        ),
        sender=_OWNER,
    )

    assert status == Status.SUCCESS
    assert _introductions(owner_dl) == []
    assert owner_dl.outbox_list() == []


def test_reporter_receiving_the_introduction_relays_nothing(dl, make_payload):
    """The reporter is not the case owner, so it introduces no one."""
    from vultron.adapters.driven.trigger_activity_adapter import (
        TriggerActivityAdapter,
    )

    dl.save(_link(creator=_OWNER))
    case = _owned_case(extra=(_participant(_RECEIVER, CVDRole.REPORTER),))
    activity = create_case_activity(case, actor=_OWNER, to=[_RECEIVER])
    event = make_payload(activity)
    tree = create_create_case_received_tree(
        event.case,
        _CASE_ID,
        _OWNER,
        sender_rule=CreateCaseReceivedUseCase.sender_entitlement,
    )
    result = BTBridge(
        datalayer=dl, trigger_activity=TriggerActivityAdapter(dl)
    ).execute_with_setup(tree=tree, actor_id=_RECEIVER, activity=event)

    assert result.status == Status.SUCCESS
    assert dl.list_objects("Create") == []
    assert dl.outbox_list() == []
    bound = dl.read(_link().id_)
    assert isinstance(bound, VultronReportCaseLink)
    assert bound.case_id == _CASE_ID
    assert bound.case_creator_id == _OWNER
    assert bound.case_manager_id == _CREATOR


def test_owner_without_an_active_reporter_sends_nothing():
    """No reporter on the roster: nothing to introduce, nothing queued."""
    owner_dl, status = _run_at_owner(_owned_case())

    assert status == Status.SUCCESS
    assert _introductions(owner_dl) == []


def test_owner_introduces_the_reporter_once():
    """A second trusted bootstrap of the same case sends no second Create."""
    case = _owned_case(extra=(_participant(_REPORTER, CVDRole.REPORTER),))
    owner_dl, status = _run_at_owner(case)
    assert status == Status.SUCCESS
    [first] = _introductions(owner_dl)

    # The link is pending again, so the bootstrap takes the trusted route.
    _, status = _run_at_owner(case, owner_dl=owner_dl)

    assert status == Status.SUCCESS
    assert [i.id_ for i in _introductions(owner_dl)] == [first.id_]
    assert owner_dl.outbox_list() == [first.id_]


@pytest.mark.spec("CBT-01-001")
def test_redelivery_retries_an_introduction_that_failed_to_queue(monkeypatch):
    """A first delivery that stored but could not queue the introduction.

    The CASE_MANAGER's redelivery of its Create takes the redelivery route,
    which queues the stored introduction: the reporter still gets exactly
    one, under the first attempt's id.
    """
    case = _owned_case(extra=(_participant(_REPORTER, CVDRole.REPORTER),))
    owner_dl = _owner_store()
    queue = owner_dl.outbox_append

    def _outbox_down(activity_id: str) -> bool:
        raise RuntimeError("outbox unavailable")

    monkeypatch.setattr(owner_dl, "outbox_append", _outbox_down)
    _, status = _run_at_owner(case, owner_dl=owner_dl)
    assert status == Status.FAILURE
    [stored] = _introductions(owner_dl)
    assert owner_dl.outbox_list() == []

    monkeypatch.setattr(owner_dl, "outbox_append", queue)
    _, status = _run_at_owner(case, owner_dl=owner_dl, pending_link=False)

    assert status == Status.SUCCESS
    assert [i.id_ for i in _introductions(owner_dl)] == [stored.id_]
    assert owner_dl.outbox_list() == [stored.id_]


@pytest.mark.spec("CBT-01-005")
@pytest.mark.spec("CBT-05-002")
def test_bootstrap_not_naming_the_submitted_report_is_refused(
    dl, make_payload
):
    """The right sender is not enough: the case must name the report."""
    link = _link()
    dl.save(link)
    case = _case().model_copy(
        update={"vulnerability_reports": ["https://example.org/reports/other"]}
    )

    tree, result, route, _ = _run(dl, make_payload, _CREATOR, case)

    assert result.status == Status.FAILURE
    assert route.name == "trusted"
    assert "CBT-01-005" in BTBridge.get_failure_reason(tree)
    assert dl.read(_CASE_ID) is None
    unbound = dl.read(link.id_)
    assert isinstance(unbound, VultronReportCaseLink)
    assert unbound.case_id is None


@pytest.mark.spec("CBT-01-005")
@pytest.mark.spec("CBT-01-006")
def test_the_link_for_the_named_report_is_bound(dl, make_payload):
    """Two reports sent to one actor: the case binds its own report's link."""
    other = VultronReportCaseLink(
        report_id="https://example.org/reports/first",
        case_id=None,
        case_creator_id=_CREATOR,
    )
    dl.save(other)
    dl.save(_link())

    _, result, route, _ = _run(dl, make_payload, _CREATOR, _case())

    assert result.status == Status.SUCCESS
    assert route.link is not None and route.link.report_id == _REPORT_ID
    still_pending = dl.read(other.id_)
    assert isinstance(still_pending, VultronReportCaseLink)
    assert still_pending.case_id is None


@pytest.mark.spec("CBT-02-001")
@pytest.mark.spec("CM-02-010")
def test_reporter_trusts_a_receiver_that_is_its_own_case_manager(
    dl, make_payload
):
    """Owner and CASE_MANAGER are one actor: its Create is the only one.

    The reporter accepts it on the trusted route, records the receiver as
    the CASE_MANAGER too, and sends nothing on (AC-4 of #4511).
    """
    from vultron.adapters.driven.trigger_activity_adapter import (
        TriggerActivityAdapter,
    )

    dl.save(_link(creator=_OWNER))
    case = _owned_case(
        manager=_OWNER, extra=(_participant(_RECEIVER, CVDRole.REPORTER),)
    )
    activity = create_case_activity(case, actor=_OWNER, to=[_RECEIVER])
    event = make_payload(activity)
    tree = create_create_case_received_tree(
        event.case,
        _CASE_ID,
        _OWNER,
        sender_rule=CreateCaseReceivedUseCase.sender_entitlement,
    )
    result = BTBridge(
        datalayer=dl, trigger_activity=TriggerActivityAdapter(dl)
    ).execute_with_setup(tree=tree, actor_id=_RECEIVER, activity=event)

    assert result.status == Status.SUCCESS
    bound = dl.read(_link().id_)
    assert isinstance(bound, VultronReportCaseLink)
    assert bound.case_creator_id == _OWNER
    assert bound.case_manager_id == _OWNER
    assert dl.outbox_list() == []
