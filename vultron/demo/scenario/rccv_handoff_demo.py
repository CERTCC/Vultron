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

"""Reporter → C1 → C2 (ownership transfer) → Vendor (RCCV-handoff) demo.

Four actor containers plus a dedicated CaseActor: Reporter, C1 (the initial
CASE_OWNER), C2 (the new CASE_OWNER after the handoff) and Vendor.  C1
transfers case ownership to C2 through the trigger endpoints
(TRIG-11-001/TRIG-11-002), and C2 — not C1 — then invites the Vendor
(DEMOMA-14-005).  The handoff moves CASE_OWNER, never CASE_MANAGER: that
stays with the CaseActor on its own container.

Cast (DEMOCI-11-020): every scenario runs the same containers, so a role's
address and actor id are the same here as in its siblings.  ``ROLES`` below
seats each actor; the cast table is ``vultron/demo/helpers/cast.py``.  C1 is
the first Coordinator, so it runs in cast slot 2 and C2 takes a character
slot; C1 proposes the case, so that container's default case roles become
C1's roles in the case (CP-01-013).

The story is assembled, not written out: it starts with
:data:`~vultron.demo.helpers.two_coordinator_story.C1_INVITES_C2`, the opening
it shares with ``rccv-extension`` — itself continuing the rcv family's
``REPORTER_TELLS_THE_COORDINATOR`` — and continues with C1 offering ownership
to C2 (:data:`STORY`, DEMOCI-11-019).  That shared opening is why this
scenario's ledger and ``rccv-extension``'s agree byte for byte up to the
owner's decision (DEMOCI-11-018).

Spec: DEMOMA-14 (GitHub issue #1216).
"""

import logging

from vultron.demo.helpers.actor_roles import (
    case_actor_role,
    resolved_actor_ids,
    role_map,
)
from vultron.demo.helpers.coordinated_story import (
    CASE_ACTOR_NAME,
    REPORTER,
    VENDOR,
    VENDOR_LABEL,
    close_the_case,
    coordinated_clients,
    coordinated_open_cast,
    vendor_reports_the_fix_ready,
)
from vultron.demo.helpers.notes import NotePost
from vultron.demo.helpers.owner_decision_story import (
    the_new_owner_invites,
    the_owner_hands_the_case_over,
)
from vultron.demo.helpers.story import StoryState, choose, run_story, story
from vultron.demo.helpers.two_coordinator_story import (
    C1,
    C1_INVITES_C2,
    C1_PART,
    C1_ROLE,
    C2,
    C2_PART,
    SECOND_COORDINATOR_JOINED,
    VENDOR_PART,
    all_four_publish,
    dump_two_coordinator_ledgers,
    every_replica_converges,
    four_way_note_thread,
    required_participants_are_present,
    two_coordinator_cast_members,
    two_coordinator_roles,
    unseated_second_coordinator,
)
from vultron.demo.scenario.registry import scenario
from vultron.demo.utils import DataLayerClient, setup_demo_logging
from vultron.enums.roles import CVDRole

logger = logging.getLogger(__name__)

DEMO_NAME = "rccv-handoff"

# The scenario's actors in main() parameter order, each seated in a container of
# the fixed cast (DEMOCI-11-020).  The demo CLI derives this scenario's
# sub-command options from this list (DEMOCI-11-011); the CaseActor role
# carries an id option of its own, which DEMOMA-14-008 requires.
ROLES = two_coordinator_roles(case_actor=case_actor_role(has_id=True))
#: Indexed for the CLI factory and for ``coordinated_clients()``, which reads
#: each actor's container address off its cast slot — so this module declares
#: no ``*_BASE_URL`` constant of its own (DEMOCI-11-020).
_ROLES = role_map(ROLES)

#: ``vultron-demo rccv-handoff --help`` text. Lives here rather than in
#: ``cli.py`` because the sub-command is generated from the registry and the
#: scenario module is the only place that knows what its own workflow does.
CLI_HELP = """Run the RCCV-handoff (C1 → C2 ownership transfer) demo (DEMOMA-14).

C1 (Coordinator1) creates the case as CASE_OWNER and invites C2
(Coordinator2).  C1 then transfers case ownership to C2 via the trigger
endpoints (TRIG-11-001/002).  C2 (now CASE_OWNER) invites Vendor.  All
four actors coordinate to closure.

\b
Workflow:
  1. Seed the Reporter, C1 and Vendor containers; Reporter submits a report
     to C1's inbox; C1 validates and engages the case (CASE_OWNER).
  2. C2's container is seeded and C1 invites C2 with CVDRole.COORDINATOR;
     C2 accepts.
  3. C1 offers case ownership transfer to C2 (TRIG-11-001); C2 accepts
     (TRIG-11-002); every replica's attributed_to becomes C2.
  4. C2, the new CASE_OWNER, invites Vendor; the CaseActor emits the Invite,
     so Vendor's Accept routes back to the CaseActor (PCR-08-008).
  5. Verify LedgerFanout replication on all replicas.
  6. All four exchange case notes.
  7. Vendor advances to fix ready (VFd).
  8. C2 (CASE_OWNER) triggers publication; the embargo terminates; all
     participants report publication.
  9. All participants close the case; the case ledgers are dumped.
"""


# ---------------------------------------------------------------------------
# Fragments this scenario alone tells
# ---------------------------------------------------------------------------


def c1_hands_the_case_to_c2(state: StoryState) -> None:
    """C1 offers case ownership to C2, which accepts (DEMOMA-14-004).

    C2 holds ``CVDRole.COORDINATOR`` and must be an active participant by
    now, so the shared continuation reads the join the opening's roster gate
    kept and stops the story without it (DEMOMA-14-010).  Afterwards C1's
    own role is ``CVDRole.COORDINATOR`` and no longer ``CASE_OWNER``
    (DEMOMA-14-012), and every replica's ``attributed_to`` names C2
    (DEMOMA-14-011).
    """
    the_owner_hands_the_case_over(
        state,
        joined=SECOND_COORDINATOR_JOINED,
        owner=C1_PART,
        new_owner=C2_PART,
    )


def c2_invites_the_vendor(state: StoryState) -> None:
    """C2, the new CASE_OWNER, invites the Vendor — not C1 (DEMOMA-14-005)."""
    the_new_owner_invites(
        state,
        new_owner=C2_PART,
        invitee=VENDOR_PART,
        role=CVDRole.VENDOR,
        seated=(REPORTER, C1, C2, VENDOR),
    )


def the_four_exchange_notes(state: StoryState) -> None:
    """C2 and the Vendor answer the thread the Reporter and C1 opened."""
    four_way_note_thread(
        state,
        [
            NotePost(
                state.actor(C2),
                "C2 Update (new Case Owner)",
                "As the new case owner, I confirm Vendor is engaged. "
                "Target disclosure in 30 days.",
            ),
            NotePost(
                state.actor(VENDOR),
                f"{VENDOR_LABEL} Status Update",
                "Vendor confirms the issue and will align fix timeline with "
                "the coordinated disclosure window.",
            ),
        ],
    )


def everyone_publishes(state: StoryState) -> None:
    """C2, the Case Owner since the handoff, publishes first (DEMOMA-14-014)."""
    all_four_publish(state, owner=C2_PART, other=C1_PART)


def everyone_closes(state: StoryState) -> None:
    """C1, the Vendor and the Reporter leave; C2, the Case Owner, leaves last.

    C2 holds CASE_OWNER since the handoff (TRIG-11-002), so it is the one
    whose ``Leave`` is gated on the others' departures being recorded in the
    CASE_MANAGER's store (CM-23-015, DEMOMA-14-015).
    """
    close_the_case(
        state, others=(C1, VENDOR, REPORTER), owner=C2, milestone="M8"
    )


#: The RCCV-handoff story: the opening it shares with ``rccv-extension``, then
#: the ownership transfer, C2 inviting the Vendor, and the four-party
#: lifecycle to closure.  The registry reads this scenario's path off the
#: ``choose`` items (DEMOCI-11-019), so it declares no ``path=``.
STORY = story(
    C1_INVITES_C2,
    # C1, the case owner, decides once C2 has joined.
    choose("owner-keep-case", "offer-ownership", by=C1),
    c1_hands_the_case_to_c2,
    c2_invites_the_vendor,
    required_participants_are_present,
    every_replica_converges,
    the_four_exchange_notes,
    vendor_reports_the_fix_ready,
    everyone_publishes,
    everyone_closes,
)


def run_rccv_handoff_demo(
    reporter_client: DataLayerClient,
    c1_client: DataLayerClient,
    c2_client: DataLayerClient,
    vendor_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    reporter_id: str | None = None,
    c1_id: str | None = None,
    c2_id: str | None = None,
    vendor_id: str | None = None,
    case_actor_id: str | None = None,
) -> None:
    """Orchestrate the RCCV-handoff CVD workflow.

    Args:
        reporter_client: Client for the Reporter's container.
        c1_client: Client for C1's container.
        c2_client: Client for C2's container.
        vendor_client: Client for the Vendor's container.
        case_actor_client: Client for the dedicated case-actor container.
        reporter_id: Deterministic URI for the Reporter actor.
        c1_id: Deterministic URI for the C1 actor.
        c2_id: Deterministic URI for the C2 actor.
        vendor_id: Deterministic URI for the Vendor actor.
        case_actor_id: Accepted so ``--case-actor-id`` has somewhere to go
            (DEMOMA-14-008) and unused: the case-actor container seeds its own
            identity on reset (DEMOMA-06-004), and the id the Invite check
            needs is read off the case's participant index, so that it names
            the actor actually holding CASE_MANAGER (PCR-08-008).
    """
    logger.info("=" * 80)
    logger.info("RCCV-HANDOFF DEMO: Reporter + C1 → C2 (ownership) + Vendor")
    logger.info("=" * 80)
    logger.info("Reporter container:  %s", reporter_client.base_url)
    logger.info("C1 container:        %s", c1_client.base_url)
    logger.info("C2 container:        %s", c2_client.base_url)
    logger.info("Vendor container:    %s", vendor_client.base_url)
    logger.info("CaseActor container: %s", case_actor_client.base_url)
    logger.debug("CaseActor id override, unused: %s", case_actor_id)

    open_cast = coordinated_open_cast(
        reporter_client=reporter_client,
        coordinator_client=c1_client,
        vendor_client=vendor_client,
        case_actor_client=case_actor_client,
        dump=dump_two_coordinator_ledgers,
        reporter_id=reporter_id,
        coordinator_id=c1_id,
        vendor_id=vendor_id,
        unseated=unseated_second_coordinator(c2_client, c2_id),
    )

    # run_story() owns the failure accumulator through scenario_harness: it
    # resets it, always dumps the case ledgers, and asserts success — so a
    # failure here never costs us the artifacts (ISSUE-2239, DEMOMA-23-001).
    run_story(DEMO_NAME, STORY, open_cast)

    logger.info("=" * 80)
    logger.info(
        "RCCV-HANDOFF DEMO COMPLETE ✓  (ownership transfer + VFDPxa full"
        " lifecycle)"
    )
    logger.info("=" * 80)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


@scenario(
    name=DEMO_NAME,
    label="RCCV-handoff",
    participants="Reporter + C1 → C2 + Vendor",
    feature="Ownership transfer between two coordinators",
    in_pr_set=False,
    story=STORY,
)
def main(
    skip_health_check: bool = False,
    reporter_url: str | None = None,
    c1_url: str | None = None,
    c2_url: str | None = None,
    vendor_url: str | None = None,
    case_actor_url: str | None = None,
    reporter_id: str | None = None,
    c1_id: str | None = None,
    c2_id: str | None = None,
    vendor_id: str | None = None,
    case_actor_id: str | None = None,
) -> None:
    """Entry point for the RCCV-handoff CVD workflow demo.

    Args:
        skip_health_check: Skip the server availability check.
        reporter_url: Override base URL for the Reporter container.
        c1_url: Override base URL for the C1 (Coordinator1) container.
        c2_url: Override base URL for the C2 (Coordinator2) container.
        vendor_url: Override base URL for the Vendor container.
        case_actor_url: Override base URL for the dedicated CaseActor
            container.
        reporter_id: Optional deterministic URI for the Reporter actor.
        c1_id: Optional deterministic URI for the C1 actor.
        c2_id: Optional deterministic URI for the C2 actor.
        vendor_id: Optional deterministic URI for the Vendor actor.
        case_actor_id: Optional deterministic URI for the CaseActor actor.
    """
    clients = coordinated_clients(
        _ROLES,
        two_coordinator_cast_members(
            reporter_url=reporter_url,
            c1_url=c1_url,
            c2_url=c2_url,
            vendor_url=vendor_url,
        ),
        skip_health_check=skip_health_check,
        case_actor_url=case_actor_url,
    )
    run_rccv_handoff_demo(
        reporter_client=clients[REPORTER],
        c1_client=clients[C1_ROLE],
        c2_client=clients[C2],
        vendor_client=clients[VENDOR],
        case_actor_client=clients[CASE_ACTOR_NAME],
        **resolved_actor_ids(
            _ROLES,
            reporter=(clients[REPORTER], reporter_id),
            c1=(clients[C1_ROLE], c1_id),
            c2=(clients[C2], c2_id),
            vendor=(clients[VENDOR], vendor_id),
        ),
        case_actor_id=case_actor_id,
    )


if __name__ == "__main__":
    setup_demo_logging()
    main()
