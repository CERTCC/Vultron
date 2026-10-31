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

"""RCVV embargo demo (Reporter + Coordinator + Vendor1 + Vendor2).

A four-party case across five containers (Reporter, Coordinator, Vendor1,
Vendor2 and CaseActor) that exercises the embargo lifecycle on its own:
post-submission negotiation, a revision cycle, a late second vendor, and an
embargo that collapses by accident when the Reporter publishes
(DEMOMA-21, issue #2072).

The Coordinator creates the case and holds CASE_OWNER; the CaseActor holds
CASE_MANAGER.  Case creation activates the default embargo (EP-04-001), so the
Reporter's proposal **revises** it (``ACTIVE → REVISE → ACTIVE``, EP-09); then
Vendor1 proposes a second revision that the Reporter accepts and the
Coordinator, as owner, activates.  Vendor2 is invited only after that, and
signs the embargo in force by accepting the invitation.  After the fixes are
ready the Reporter reports public disclosure: CS.P ends the embargo
automatically (``ACTIVE → EXITED``), and nobody terminates it.

The story is assembled, not written out: it starts with
:data:`~vultron.demo.helpers.coordinated_embargo_story
.REPORTER_PROPOSES_EMBARGO`, the opening it shares with ``rcv-embargo``, and
continues with Vendor1's revision (:data:`STORY`, DEMOCI-11-019).  Its steps
run in the order DEMOMA-21-008 gives, and the revision, the late invite and
the collapse each assert the expected EM state before the next starts
(DEMOMA-21-009).

Vendor2 is a **character actor**: its container is reset with the rest, and its
actor is seeded by the fragment that invites it rather than by the shared
opening, because every record the opening writes before the case exists moves
the first ledger entry's timestamp away from the sibling it must match byte
for byte (DEMOCI-11-018).

Spec: DEMOMA-21, DEMOCI-07 (GitHub issue #2072).
"""

import logging

from vultron.core.behaviors.embargo.nodes import EMBARGO_TEARDOWN_SEMANTIC_TYPE
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import EmbargoConsentState
from vultron.demo.exchange.embargo_lifecycle import (
    COMMIT_TIMEOUT_SECONDS,
    demo_propose_embargo_revision,
)
from vultron.demo.helpers.actor_roles import (
    ActorRole,
    case_actor_role,
    resolved_actor_ids,
    role_map,
)
from vultron.demo.helpers.cast import (
    CAST,
    COORDINATOR_SLOT,
    REPORTER_SLOT,
    VENDOR_SLOT,
)
from vultron.demo.helpers.coordinated_embargo_story import (
    PROPOSED_EMBARGO,
    REPORTER_PROPOSES_EMBARGO,
    assert_canonical_em_state,
    confirm_embargo_revised,
    embargo_stays_ended_through_closure,
    embargo_survives_the_fix,
    replicas_see_the_embargo_ended,
)
from vultron.demo.helpers.coordinated_story import (
    CASE_ACTOR_NAME,
    COORDINATOR,
    COORDINATOR_LABEL,
    REPORTER,
    REPORTER_LABEL,
    VENDOR,
    CastContainer,
    close_the_case,
    coordinated_clients,
    dump_coordinated_ledgers,
    invitee_joins_the_case,
    open_coordinated_cast,
    report_fix_ready,
    reports_published,
    seat_character_actor,
)
from vultron.demo.helpers.harness import ScenarioHarness
from vultron.demo.helpers.polling import (
    wait_for_case_em_state,
    wait_for_participant_embargo_consent,
    wait_for_semantic_type_in_ledger,
)
from vultron.demo.helpers.seeding import seed_containers_rcvv
from vultron.demo.helpers.story import (
    StoryProp,
    StoryState,
    UnseatedContainer,
    choose,
    run_story,
    story,
)
from vultron.demo.scenario.registry import scenario
from vultron.demo.utils import (
    DataLayerClient,
    demo_check,
    demo_gate,
    demo_step,
    setup_demo_logging,
)
from vultron.enums.roles import CVDRole

logger = logging.getLogger(__name__)

#: What this scenario calls its two vendors.  Vendor1 is the family's Vendor —
#: the first Vendor of the fixed cast, named ``Vendor`` as ``rcv-embargo``'s
#: one Vendor is, because the two share their path up to Vendor1's decision
#: and their ledgers must match there (DEMOCI-11-018).
VENDOR1 = VENDOR
VENDOR1_LABEL = "Vendor1"
VENDOR2 = "vendor2"
VENDOR2_LABEL = "Vendor2"

# The scenario's actors in main() parameter order, each seated in a container of
# the fixed cast (DEMOCI-11-020).  The demo CLI derives this scenario's
# sub-command options from this list (DEMOCI-11-011).
ROLES: list[ActorRole] = [
    ActorRole(REPORTER, REPORTER_SLOT, REPORTER_LABEL, has_id=True),
    ActorRole(COORDINATOR, COORDINATOR_SLOT, COORDINATOR_LABEL, has_id=True),
    ActorRole(VENDOR1, VENDOR_SLOT, VENDOR1_LABEL, has_id=True),
    ActorRole(VENDOR2, CAST[3], VENDOR2_LABEL, has_id=True),
    case_actor_role(),
]
_ROLES = role_map(ROLES)

DEMO_NAME = "rcvv-embargo"

#: ``vultron-demo rcvv-embargo --help`` text.
CLI_HELP = """Run the RCVV embargo demo (DEMOMA-21).

Reporter + Coordinator + Vendor1 + Vendor2, exercising the embargo lifecycle:
the Reporter and then Vendor1 revise the embargo, Vendor2 joins late and signs
it, and the embargo collapses when the Reporter publishes.

\b
Workflow:
  1. Seed the containers; Reporter submits a report to Coordinator;
     Coordinator engages the case (CASE_OWNER); Vendor1 joins by invitation.
     The default embargo is active (EM.ACTIVE).
  2. Reporter proposes new embargo terms; the CASE_MANAGER relays the proposal;
     Vendor1 consents; Coordinator, as owner, activates the revision.
  3. Vendor1 proposes a further revision; Reporter consents; Coordinator
     activates it.
  4. Coordinator invites Vendor2; Vendor2 accepts and signs the embargo.
  5. Both vendors advance to fix ready (VFd).
  6. Reporter reports publication; CS.P ends the embargo (EM.EXITED) with no
     deliberate termination.
  7. All participants close the case (every RM.CLOSED in the Case Actor's store).
  8. Case ledgers are dumped for the invariant harness.
"""

#: The embargo Vendor1's revision put in force.  A second prop rather than a
#: rewrite of :data:`PROPOSED_EMBARGO`, so a revision that never took effect
#: leaves nothing for the steps that presuppose it to read and the story stops
#: there (DEMOCI-01-007).
REVISED_EMBARGO: StoryProp[str] = StoryProp(
    "embargo Vendor1's revision put in force", str
)

#: The embargo Vendor2 signed by accepting its case invitation.  The fix
#: lifecycle, the collapse and the closure presuppose it, so they read it
#: rather than acting on a case Vendor2 never joined (DEMOMA-21-012).
VENDOR2_SIGNED: StoryProp[str] = StoryProp(
    "embargo Vendor2 signed on joining", str
)


# ---------------------------------------------------------------------------
# Fragments this scenario alone tells
# ---------------------------------------------------------------------------


def vendor1_proposes_a_revision(state: StoryState) -> None:
    """Vendor1 revises the embargo; the Reporter consents; the owner activates.

    The relayed revision sequence (EP-09, DEMOMA-21-002).  Vendor2 signs
    whatever is in force when it joins, so without this second revision the
    late invite would assert about the wrong embargo — which is why the
    revision it put in force is kept rather than inferred from ``EM.ACTIVE``.
    """
    proposed = state.kept(PROPOSED_EMBARGO)

    demo_propose_embargo_revision(
        proposing=state.actor(VENDOR1),
        accepting=state.actor(REPORTER),
        owner=state.actor(COORDINATOR),
        case=state.case,
        case_manager_client=state.case_actor_client,
    )

    revised = confirm_embargo_revised(
        state,
        proposed,
        "embargo_revision",
        "The second revision is now in force",
    )
    if revised is not None:
        state.keep(REVISED_EMBARGO, revised)


def vendor2_joins_under_the_revision(state: StoryState) -> None:
    """Seed and invite Vendor2 once the revision is active; it signs it.

    Vendor2's container is seeded here rather than in the shared opening
    (DEMOCI-11-018): ``seed_containers_rcvv`` creates it and registers it as a
    peer of the three already seated, returning each of them unchanged
    because ``POST /actors/`` and ``POST /actors/{id}/peers/`` are idempotent.

    Accepting the invitation consents to the embargo in force (CM-11-002), so
    Vendor2 is a signatory before it does anything else (DEMOMA-21-012); the
    signed embargo is kept, and the steps that presuppose it stop without it.
    """
    embargo_id = state.kept(REVISED_EMBARGO)

    waiting = state.container(VENDOR2)
    with demo_step("Seeding the Vendor2 container"):
        seeded = seed_containers_rcvv(
            reporter_client=state.client(REPORTER),
            coordinator_client=state.client(COORDINATOR),
            vendor_client=state.client(VENDOR1),
            vendor2_client=waiting.client,
            reporter_actor_id=state.actor_id(REPORTER),
            coordinator_actor_id=state.actor_id(COORDINATOR),
            vendor_actor_id=state.actor_id(VENDOR1),
            vendor2_actor_id=waiting.actor_id,
            case_actor_client=state.case_actor_client,
        )
        # Seated inside the step that seeded it: a seeding failure then leaves
        # the cast short, and the fragments that reach for Vendor2 stop the
        # story rather than acting on a stand-in (#2308).
        seat_character_actor(state, VENDOR2, seeded[3].id_)

    invitee_joins_the_case(
        state,
        VENDOR2,
        VENDOR2_LABEL,
        role=CVDRole.VENDOR,
        seated=(REPORTER, COORDINATOR, VENDOR1, VENDOR2),
    )
    assert_canonical_em_state(
        state,
        EM.ACTIVE,
        "v2_late_invite",
        active_embargo_id=embargo_id,
    )

    with demo_gate("Vendor2 is a signatory to the active embargo"):
        wait_for_participant_embargo_consent(
            state.case_actor_client,
            state.case.id_,
            state.actor_id(VENDOR2),
            embargo_id,
            EmbargoConsentState.AGREED,
            COMMIT_TIMEOUT_SECONDS,
        )
        state.keep(VENDOR2_SIGNED, embargo_id)
    with demo_check("Vendor2's replica has the revised embargo active"):
        wait_for_case_em_state(
            state.client(VENDOR2),
            state.case.id_,
            EM.ACTIVE,
            COMMIT_TIMEOUT_SECONDS,
            active_embargo_id=embargo_id,
        )


def both_vendors_report_the_fix_ready(state: StoryState) -> None:
    """Both vendors report fix ready; the embargo is untouched."""
    state.kept(VENDOR2_SIGNED)
    report_fix_ready(state, VENDOR1, VENDOR1_LABEL)
    report_fix_ready(state, VENDOR2, VENDOR2_LABEL)


def reporter_publishes_and_the_embargo_collapses(state: StoryState) -> None:
    """The Reporter publishes; CS.P ends the embargo with nobody terminating it.

    The collapse is the protocol's own consequence of the P-transition
    (DEMOMA-21-014): this fragment never calls ``terminate_embargo``.
    """
    reports_published(state, REPORTER)

    # The teardown is the CASE_MANAGER's own commit, so it is read where it
    # commits before any replica is expected to show it (EDF-06-002).
    with demo_gate("The CASE_MANAGER commits the embargo teardown"):
        wait_for_semantic_type_in_ledger(
            client=state.case_actor_client,
            case_id=state.case.id_,
            semantic_type=EMBARGO_TEARDOWN_SEMANTIC_TYPE,
            timeout_seconds=COMMIT_TIMEOUT_SECONDS,
        )
    assert_canonical_em_state(state, EM.EXITED, "accidental_collapse")
    replicas_see_the_embargo_ended(
        state, (COORDINATOR, REPORTER, VENDOR1, VENDOR2)
    )


def everyone_including_vendor2_closes(state: StoryState) -> None:
    """Every participant closes the case; the Case Owner leaves last."""
    close_the_case(state, others=(VENDOR1, REPORTER, VENDOR2), milestone="M7")


#: The RCVV-embargo story: the opening it shares with ``rcv-embargo``, then
#: Vendor1's revision, the late second vendor, and the accidental collapse.
#: The registry reads this scenario's path off the ``choose`` items
#: (DEMOCI-11-019), so it declares no ``path=``.
STORY = story(
    REPORTER_PROPOSES_EMBARGO,
    # Vendor1 decides once the revised embargo is in force.
    choose("vendor-after-embargo", "propose-revision", by=VENDOR1),
    vendor1_proposes_a_revision,
    vendor2_joins_under_the_revision,
    both_vendors_report_the_fix_ready,
    embargo_survives_the_fix,
    reporter_publishes_and_the_embargo_collapses,
    everyone_including_vendor2_closes,
    embargo_stays_ended_through_closure,
)


def _dump_ledgers(state: StoryState) -> None:
    """Dump each participant's case ledger (the last step, DEMOMA-21-008).

    Thin wrapper (DEMOMA-23-002): the harness runs it on the way out, whether
    or not an earlier step failed.
    """
    replicas = [REPORTER, COORDINATOR, VENDOR1]
    if VENDOR2 in state.cast:
        replicas.append(VENDOR2)
    dump_coordinated_ledgers(state, replicas=replicas)


def run_rcvv_embargo_demo(
    reporter_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    vendor_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    reporter_id: str | None = None,
    coordinator_id: str | None = None,
    vendor_id: str | None = None,
    vendor2_id: str | None = None,
) -> None:
    """Orchestrate the RCVV embargo workflow."""
    logger.info("=" * 80)
    logger.info(
        "RCVV EMBARGO DEMO: Reporter + Coordinator(CASE_OWNER) + Vendor1 + Vendor2"
    )
    logger.info("=" * 80)
    logger.info("Reporter container:    %s", reporter_client.base_url)
    logger.info("Coordinator container: %s", coordinator_client.base_url)
    logger.info("Vendor1 container:     %s", vendor_client.base_url)
    logger.info("Vendor2 container:     %s", vendor2_client.base_url)
    logger.info("CaseActor container:   %s", case_actor_client.base_url)

    def open_cast(harness: ScenarioHarness) -> StoryState:
        return open_coordinated_cast(
            harness,
            reporter_client=reporter_client,
            coordinator_client=coordinator_client,
            vendor_client=vendor_client,
            case_actor_client=case_actor_client,
            dump=_dump_ledgers,
            reporter_id=reporter_id,
            coordinator_id=coordinator_id,
            vendor_id=vendor_id,
            unseated={
                VENDOR2: UnseatedContainer(
                    VENDOR2_LABEL, vendor2_client, vendor2_id
                )
            },
        )

    # run_story() owns the failure accumulator through scenario_harness: it
    # resets it, always dumps the case ledgers, and asserts success — so a
    # failure here never costs us the artifacts (ISSUE-2239, DEMOMA-23-001).
    run_story(DEMO_NAME, STORY, open_cast)

    logger.info("=" * 80)
    logger.info(
        "RCVV EMBARGO DEMO COMPLETE ✓  "
        "(EM: ACTIVE → REVISE → ACTIVE → REVISE → ACTIVE → EXITED)"
    )
    logger.info("=" * 80)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


@scenario(
    name=DEMO_NAME,
    label="RCVV embargo",
    participants="Reporter + Coordinator + Vendor1 + Vendor2",
    feature="Embargo revision cycle, late second vendor, and accidental collapse",
    in_pr_set=True,
    story=STORY,
)
def main(
    skip_health_check: bool = False,
    reporter_url: str | None = None,
    coordinator_url: str | None = None,
    vendor_url: str | None = None,
    vendor2_url: str | None = None,
    case_actor_url: str | None = None,
    reporter_id: str | None = None,
    coordinator_id: str | None = None,
    vendor_id: str | None = None,
    vendor2_id: str | None = None,
) -> None:
    """Entry point for the RCVV embargo demo.

    Args:
        skip_health_check: Skip the server availability check.
        reporter_url: Override base URL for the Reporter container.
        coordinator_url: Override base URL for the Coordinator container.
        vendor_url: Override base URL for the Vendor1 container.
        vendor2_url: Override base URL for the Vendor2 container.
        case_actor_url: Override base URL for the CaseActor container.
        reporter_id: Optional deterministic URI for the Reporter actor.
        coordinator_id: Optional deterministic URI for the Coordinator actor.
        vendor_id: Optional deterministic URI for the Vendor1 actor.
        vendor2_id: Optional deterministic URI for the Vendor2 actor.
    """
    clients = coordinated_clients(
        _ROLES,
        [
            CastContainer(REPORTER, REPORTER_LABEL, reporter_url),
            CastContainer(COORDINATOR, COORDINATOR_LABEL, coordinator_url),
            CastContainer(VENDOR1, VENDOR1_LABEL, vendor_url),
            CastContainer(VENDOR2, VENDOR2_LABEL, vendor2_url),
        ],
        skip_health_check=skip_health_check,
        case_actor_url=case_actor_url,
    )
    run_rcvv_embargo_demo(
        reporter_client=clients[REPORTER],
        coordinator_client=clients[COORDINATOR],
        vendor_client=clients[VENDOR1],
        vendor2_client=clients[VENDOR2],
        case_actor_client=clients[CASE_ACTOR_NAME],
        **resolved_actor_ids(
            _ROLES,
            reporter=(clients[REPORTER], reporter_id),
            coordinator=(clients[COORDINATOR], coordinator_id),
            vendor=(clients[VENDOR1], vendor_id),
            vendor2=(clients[VENDOR2], vendor2_id),
        ),
    )


if __name__ == "__main__":
    setup_demo_logging()
    main()
