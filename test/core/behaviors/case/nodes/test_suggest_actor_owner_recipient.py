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

"""The CaseActor's Case Owner DMs must reach the owner, not the CaseActor.

``EmitOfferCaseParticipantToOwnerNode`` and
``EmitNoteDuplicateRecommendationToOwnerNode`` run *as the CaseActor*, in the
CaseActor's own store (ADR-0072 decision 5).  There, ``VulnerabilityCase.
attributed_to`` names the **CaseActor** — it authored that case (CM-22-001,
CP-05-003, ADR-0041/ADR-0023).  Both nodes used to read ``attributed_to`` and
call the result "the Case Owner", so the CaseActor addressed the
``Offer(CaseParticipant)`` to itself and the owner never saw it.

That is invisible in a single-store test — the owner and the CaseActor share
``attributed_to`` there — and it only surfaced in the fcvcv Docker scenario as a
chain of five failures starting at "Offer(CaseParticipant) for V2 arrived in
C1's DataLayer" and ending with a 422 from ``accept-actor-recommendation``.
These tests seed the CaseActor's store the way ``_CreateCaseFromProposalNode``
actually leaves it, so the mis-addressing fails here instead.
"""

import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.suggest_actor.emit import (
    EmitNoteDuplicateRecommendationToOwnerNode,
    EmitOfferCaseParticipantToOwnerNode,
)
from vultron.core.models.case_participant import CaseParticipant
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

CASE_ACTOR_ID = "https://example.org/actors/case-actor"
OWNER_ID = "https://example.org/actors/owner"
RECOMMENDER_ID = "https://example.org/actors/recommender"
RECOMMENDED_ID = "https://example.org/actors/recommended"
CASE_ID = "https://example.org/cases/suggest-actor-owner-01"
RECOMMENDATION_ID = "https://example.org/activities/offer-actor-01"


@pytest.fixture
def case_actor_dl():
    """The CaseActor's own store, closed explicitly.

    An unclosed sqlite3 connection is collected at an unpredictable moment and
    pytest promotes the resulting ResourceWarning to a failure.
    """
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=CASE_ACTOR_ID)
    yield dl
    dl.close()


def _seed_case_actor_store(
    dl: SqliteDataLayer,
    *,
    with_owner_participant: bool = True,
    attributed_to: str = CASE_ACTOR_ID,
) -> None:
    """Seed the case as the CaseActor's own store actually holds it.

    ``_CreateCaseFromProposalNode`` sets ``attributed_to`` to the CaseActor
    (CM-22-001), and ``_AddVendorOwnerParticipantNode`` adds the report
    receiver as the ``CASE_OWNER`` participant.  The CASE_OWNER participant is
    therefore the only record of who owns the case in this store.
    """
    case = as_VulnerabilityCase(
        id_=CASE_ID,
        name="Suggest-actor owner routing",
        attributed_to=attributed_to,
    )
    case_actor_p = CaseParticipant(
        id_=f"{CASE_ID}/participants/case-actor",
        attributed_to=CASE_ACTOR_ID,
        context=CASE_ID,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    case.actor_participant_index[CASE_ACTOR_ID] = case_actor_p.id_
    case.case_participants.append(case_actor_p.id_)
    to_create = [case_actor_p]

    if with_owner_participant:
        owner_p = CaseParticipant(
            id_=f"{CASE_ID}/participants/owner",
            attributed_to=OWNER_ID,
            context=CASE_ID,
            case_roles=[CVDRole.CASE_OWNER, CVDRole.COORDINATOR],
        )
        case.actor_participant_index[OWNER_ID] = owner_p.id_
        case.case_participants.append(owner_p.id_)
        to_create.append(owner_p)

    dl.create(case)
    for participant in to_create:
        dl.create(participant)


def _run(dl: SqliteDataLayer, node) -> Status:
    """Execute *node* as the CaseActor against its own store."""
    bridge = BTBridge(
        datalayer=dl,
        trigger_activity=TriggerActivityAdapter(dl),
    )
    return bridge.execute_with_setup(tree=node, actor_id=CASE_ACTOR_ID).status


def _queued_recipients(dl: SqliteDataLayer, type_: str) -> list[str]:
    """Return the ``to`` recipients of every queued activity of *type_*.

    Reads the outbox rather than spying on the factory: the outbox is what the
    delivery loop actually walks, so a node that builds a correctly-addressed
    activity and then queues something else cannot pass.
    """
    recipients: list[str] = []
    for activity_id in dl.outbox_list():
        activity = dl.read(activity_id)
        if getattr(activity, "type_", None) != type_:
            continue
        recipients.extend(getattr(activity, "to", None) or [])
    return recipients


def _offer_node() -> EmitOfferCaseParticipantToOwnerNode:
    return EmitOfferCaseParticipantToOwnerNode(
        recommendation_id=RECOMMENDATION_ID,
        recommender_id=RECOMMENDER_ID,
        recommended_id=RECOMMENDED_ID,
        case_id=CASE_ID,
    )


def _note_node() -> EmitNoteDuplicateRecommendationToOwnerNode:
    return EmitNoteDuplicateRecommendationToOwnerNode(
        recommendation_id=RECOMMENDATION_ID,
        recommender_id=RECOMMENDER_ID,
        recommended_id=RECOMMENDED_ID,
        case_id=CASE_ID,
    )


class TestOfferCaseParticipantAddressesTheCaseOwner:
    @pytest.mark.spec("CM-16-004")
    def test_offer_goes_to_the_owner_not_the_emitting_case_actor(
        self, case_actor_dl
    ):
        """The regression, pinned: to=[owner], never to=[CaseActor].

        In CI this failed as "CHECK FAILED: Offer(CaseParticipant) for V2
        arrived in C1's DataLayer" — the activity was delivered, but to the
        CaseActor's own inbox.
        """
        _seed_case_actor_store(case_actor_dl)

        status = _run(case_actor_dl, _offer_node())

        assert status == Status.SUCCESS
        recipients = _queued_recipients(case_actor_dl, "Offer")
        assert recipients == [OWNER_ID], (
            "Offer(CaseParticipant) must be addressed to the CASE_OWNER"
            f" participant ({OWNER_ID}); got {recipients!r}"
        )
        assert CASE_ACTOR_ID not in recipients, (
            "the CaseActor must not DM itself — the Case Owner would never"
            " receive the membership decision it is required to make"
        )

    @pytest.mark.spec("CM-16-004")
    def test_falls_back_to_attributed_to_when_no_owner_participant(
        self, case_actor_dl
    ):
        """A store with no CASE_OWNER participant still resolves an owner.

        The Case Owner's *own* store is attributed to the owner (CM-02-008), so
        ``attributed_to`` remains a usable fallback there.
        """
        _seed_case_actor_store(
            case_actor_dl,
            with_owner_participant=False,
            attributed_to=OWNER_ID,
        )

        status = _run(case_actor_dl, _offer_node())

        assert status == Status.SUCCESS
        assert _queued_recipients(case_actor_dl, "Offer") == [OWNER_ID]

    @pytest.mark.spec("CM-16-004")
    def test_fails_when_the_only_candidate_is_the_emitting_actor(
        self, case_actor_dl
    ):
        """No resolvable owner is a hard failure, not a self-addressed DM.

        Returning FAILURE surfaces the misconfiguration at the emitting node
        (ARCH-15-001); self-delivery instead looks like success and strands the
        whole ADR-0026 chain three steps later.
        """
        _seed_case_actor_store(case_actor_dl, with_owner_participant=False)

        status = _run(case_actor_dl, _offer_node())

        assert status == Status.FAILURE
        assert _queued_recipients(case_actor_dl, "Offer") == []


class TestDuplicateRecommendationNoteAddressesTheCaseOwner:
    @pytest.mark.spec("CM-16-008")
    def test_note_goes_to_the_owner_not_the_emitting_case_actor(
        self, case_actor_dl
    ):
        """Same defect, same store, second node (CM-16-008).

        fcvcv never reached the duplicate-recommendation path, so this one was
        latent — it would have mis-addressed identically the first time a second
        recommendation for the same actor arrived.
        """
        _seed_case_actor_store(case_actor_dl)

        status = _run(case_actor_dl, _note_node())

        assert status == Status.SUCCESS
        recipients = _queued_recipients(case_actor_dl, "Add")
        assert recipients == [OWNER_ID], (
            "Add(Note, Case) must be addressed to the CASE_OWNER participant"
            f" ({OWNER_ID}); got {recipients!r}"
        )

    @pytest.mark.spec("CM-16-008")
    def test_note_fails_when_the_only_candidate_is_the_emitting_actor(
        self, case_actor_dl
    ):
        _seed_case_actor_store(case_actor_dl, with_owner_participant=False)

        status = _run(case_actor_dl, _note_node())

        assert status == Status.FAILURE
        assert _queued_recipients(case_actor_dl, "Add") == []
