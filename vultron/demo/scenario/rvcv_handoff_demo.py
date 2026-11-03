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

"""Reporter → Vendor1 → Coordinator (ownership transfer) → Vendor2 (RVCV-handoff).

Four actor containers plus a dedicated CaseActor: Reporter, Vendor1 (the
initial CASE_OWNER), Coordinator (the new CASE_OWNER after the handoff) and
Vendor2.  Vendor1 transfers case ownership to the Coordinator through the
trigger endpoints (TRIG-11-001/TRIG-11-002), and the Coordinator — not
Vendor1 — then invites Vendor2 (DEMOMA-11-003).  The handoff moves CASE_OWNER,
never CASE_MANAGER: that stays with the CaseActor on its own container.

Cast (DEMOCI-11-020): every scenario runs the same containers, so a role's
address and actor id are the same here as in its siblings.  ``ROLES`` below
seats each actor; the cast table is ``vultron/demo/helpers/cast.py``.  Vendor1
proposes the case, so that container's default case roles become Vendor1's
roles in the case (CP-01-013).

The story is assembled, not written out: it starts with
:data:`~vultron.demo.helpers.vendor_coordinator_story\
.THE_VENDOR_INVITES_A_COORDINATOR`, the opening it shares with
``rvcv-extension`` — itself continuing the vendor-first family's
``THE_VENDOR_ANSWERS_THE_REPORTER`` — and continues with Vendor1 offering
ownership to the Coordinator (:data:`STORY`, DEMOCI-11-019).  That shared
opening is why this scenario's ledger and ``rvcv-extension``'s agree byte for
byte up to the owner's decision (DEMOCI-11-018).

Spec: DEMOMA-11 (D5-7, GitHub issue #1561).
"""

import logging

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
from vultron.demo.helpers.coordinated_story import (
    COORDINATOR,
    COORDINATOR_LABEL,
    REPORTER,
    REPORTER_LABEL,
    close_the_case,
    reports_published,
)
from vultron.demo.helpers.notes import NotePost
from vultron.demo.helpers.owner_decision_story import (
    the_new_owner_invites,
    the_owner_hands_the_case_over,
)
from vultron.demo.helpers.story import StoryState, choose, run_story, story
from vultron.demo.helpers.story_cast import CASE_ACTOR_NAME, story_clients
from vultron.demo.helpers.vendor_coordinator_story import (
    COORDINATOR_JOINED,
    COORDINATOR_PART,
    THE_VENDOR_INVITES_A_COORDINATOR,
    dump_vendor_coordinator_ledgers,
    every_replica_converges,
    unseated_coordinator_and_vendor2,
    vendor_coordinator_cast_members,
)
from vultron.demo.helpers.vendor_story import (
    VENDOR,
    VENDOR2,
    VENDOR2_LABEL,
    VENDOR2_PART,
    VENDOR_LABEL,
    VENDOR_PART,
    both_vendors_report_the_fix_ready,
    required_participants_are_present,
    the_disclosure_reached_every_replica,
    the_embargo_ends_for,
    the_joiners_add_their_notes,
    vendor_open_cast,
)
from vultron.demo.scenario.registry import scenario
from vultron.demo.utils import DataLayerClient, setup_demo_logging
from vultron.enums.roles import CVDRole

logger = logging.getLogger(__name__)

DEMO_NAME = "rvcv-handoff"

# The scenario's actors in main() parameter order, each seated in a container of
# the fixed cast (DEMOCI-11-020).  The demo CLI derives this scenario's
# sub-command options from this list (DEMOCI-11-011); the CaseActor role
# carries an id option of its own, which DEMOMA-11 requires.
ROLES: list[ActorRole] = [
    ActorRole(REPORTER, REPORTER_SLOT, REPORTER_LABEL, has_id=True),
    ActorRole(VENDOR, VENDOR_SLOT, VENDOR_LABEL, has_id=True),
    ActorRole(COORDINATOR, COORDINATOR_SLOT, COORDINATOR_LABEL, has_id=True),
    case_actor_role(has_id=True),
    ActorRole(VENDOR2, CAST[3], VENDOR2_LABEL, has_id=True),
]
#: Indexed for the CLI factory and for ``story_clients()``, which reads
#: each actor's container address off its cast slot — so this module declares
#: no ``*_BASE_URL`` constant of its own (DEMOCI-11-020).
_ROLES = role_map(ROLES)

#: ``vultron-demo rvcv-handoff --help`` text. Lives here rather than in
#: ``cli.py`` because the sub-command is generated from the registry and the
#: scenario module is the only place that knows what its own workflow does.
CLI_HELP = """Run the RVCV-handoff (Vendor1 → Coordinator ownership transfer) demo (D5-7).

Vendor1 creates the case and invites the Coordinator, then transfers case
ownership to it via the trigger endpoints (TRIG-11-001/002).  The
Coordinator (now CASE_OWNER) invites Vendor2.  Both vendors independently
advance through the full fix and publication lifecycle.

\b
Workflow:
  1. Seed the Reporter and Vendor1 containers; Reporter submits a
     vulnerability report to Vendor1's inbox.
  2. Vendor1 validates and engages the case; Reporter asks about a
     workaround and Vendor1 answers.
  3. The Coordinator's and Vendor2's containers are seeded and Vendor1
     invites the Coordinator; it accepts.
  4. Vendor1 offers case ownership transfer to the Coordinator
     (TRIG-11-001); the Coordinator accepts (TRIG-11-002); every replica's
     attributed_to becomes the Coordinator.
  5. The Coordinator, now CASE_OWNER, invites Vendor2; the CaseActor emits
     the Invite, so Vendor2's Accept routes back to the CaseActor
     (PCR-08-008).
  6. Verify LedgerFanout replication on all replicas.
  7. All four exchange case notes.
  8. Both vendors independently advance to fix-ready (VFd).
  9. All participants report publication; embargo terminates.
 10. All participants close the case; the case ledgers are dumped.
"""


# ---------------------------------------------------------------------------
# Fragments this scenario alone tells
# ---------------------------------------------------------------------------


def vendor1_hands_the_case_to_the_coordinator(state: StoryState) -> None:
    """Vendor1 offers case ownership to the Coordinator, which accepts.

    The Coordinator holds ``CVDRole.COORDINATOR`` and must be an active
    participant by now, so the shared continuation reads the join the
    opening's roster gate kept and stops the story without it (CM-21-021).
    Afterwards every replica's ``attributed_to`` names the Coordinator
    (DEMOMA-11-004) and Vendor1 is a plain participant (DEMOMA-11-014).
    """
    the_owner_hands_the_case_over(
        state,
        joined=COORDINATOR_JOINED,
        owner=VENDOR_PART,
        new_owner=COORDINATOR_PART,
    )


def the_coordinator_invites_the_second_vendor(state: StoryState) -> None:
    """The Coordinator, the new CASE_OWNER, invites Vendor2 (DEMOMA-11-003)."""
    the_new_owner_invites(
        state,
        new_owner=COORDINATOR_PART,
        invitee=VENDOR2_PART,
        role=CVDRole.VENDOR,
        seated=(REPORTER, VENDOR, COORDINATOR, VENDOR2),
    )


def the_case_is_active(state: StoryState) -> None:
    """M1: every participant has joined and the embargo is still active.

    DEMOMA-11-013: the embargo established before the transfer still covers
    every participant, Vendor2 included, after it.
    """
    required_participants_are_present(
        state,
        check=(
            "M1: required participants (≥5), EM.ACTIVE, reporter +"
            " coordinator have replicas"
        ),
    )


def the_four_exchange_notes(state: StoryState) -> None:
    """The Coordinator and Vendor2 answer the thread the opening posted."""
    the_joiners_add_their_notes(
        state,
        [
            NotePost(
                state.actor(COORDINATOR),
                f"{COORDINATOR_LABEL} Update",
                "As the new case owner, I confirm both Vendor1 and Vendor2 "
                "are engaged. Target disclosure in 30 days.",
            ),
            NotePost(
                state.actor(VENDOR2),
                f"{VENDOR2_LABEL} Status Update",
                "Vendor2 confirms the issue affects our component as well. "
                "We will align our fix timeline with Vendor1.",
            ),
        ],
    )


def both_vendors_fix_the_vul(state: StoryState) -> None:
    """Both vendors report fix ready; both stop at VFd (CSB-15-002)."""
    both_vendors_report_the_fix_ready(
        state,
        milestones=(
            "Reporter replica shows both vendors CS include F (fix ready)",
            "Reporter replica shows both vendors CS include F (fix ready) —"
            " vendors stop at VFd",
        ),
    )


def everyone_publishes(state: StoryState) -> None:
    """The vendors and the Reporter publish; the Coordinator, the owner, last.

    Realistic CVD publication order: the vendors publish their advisories
    first, the Reporter may publish an independent writeup, and the
    Coordinator publishes last as the CASE_OWNER whose ``notify-published``
    triggers the embargo teardown (DEMOMA-07-003 step 4).
    """
    for who in (VENDOR, VENDOR2, REPORTER, COORDINATOR):
        reports_published(state, who)

    the_embargo_ends_for(
        state,
        check=(
            f"Embargo terminated (EM.EXITED) after {COORDINATOR_LABEL}"
            " (CASE_OWNER) reports published"
        ),
        watcher=COORDINATOR,
    )
    the_disclosure_reached_every_replica(
        state,
        check=(
            "All replicas CS.VFdPxa, EM.EXITED, all participants public-aware"
        ),
        em_watchers=(COORDINATOR, VENDOR, VENDOR2, REPORTER),
    )


def everyone_closes(state: StoryState) -> None:
    """Vendor1, Vendor2 and the Reporter leave; the Coordinator leaves last.

    The Coordinator holds CASE_OWNER since the handoff (TRIG-11-002), so it is
    the one whose ``Leave`` is gated on the others' departures being recorded
    in the CASE_MANAGER's store (CM-23-015).
    """
    close_the_case(
        state, others=(VENDOR, VENDOR2, REPORTER), owner=COORDINATOR
    )


#: The RVCV-handoff story: the opening it shares with ``rvcv-extension``, then
#: the ownership transfer, the Coordinator inviting Vendor2, and the four-party
#: lifecycle to closure.  The registry reads this scenario's path off the
#: ``choose`` items (DEMOCI-11-019), so it declares no ``path=``.
STORY = story(
    THE_VENDOR_INVITES_A_COORDINATOR,
    # Vendor1, the case owner, decides once the Coordinator has joined.
    choose("owner-keep-case", "offer-ownership", by=VENDOR),
    vendor1_hands_the_case_to_the_coordinator,
    the_coordinator_invites_the_second_vendor,
    the_case_is_active,
    every_replica_converges,
    the_four_exchange_notes,
    both_vendors_fix_the_vul,
    everyone_publishes,
    everyone_closes,
)


def run_rvcv_handoff_demo(
    reporter_client: DataLayerClient,
    vendor_client: DataLayerClient,
    coordinator_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    vendor2_client: DataLayerClient,
    reporter_id: str | None = None,
    vendor_id: str | None = None,
    coordinator_id: str | None = None,
    case_actor_id: str | None = None,
    vendor2_id: str | None = None,
) -> None:
    """Orchestrate the RVCV-handoff CVD workflow.

    Args:
        reporter_client: Client for the Reporter's container.
        vendor_client: Client for Vendor1's container.
        coordinator_client: Client for the Coordinator's container.
        case_actor_client: Client for the dedicated case-actor container.
        vendor2_client: Client for Vendor2's container.
        reporter_id: Deterministic URI for the Reporter actor.
        vendor_id: Deterministic URI for the Vendor1 actor.
        coordinator_id: Deterministic URI for the Coordinator actor.
        case_actor_id: Accepted so ``--case-actor-id`` has somewhere to go and
            unused: the case-actor container seeds its own identity on reset
            (DEMOMA-06-004), and the id the Invite check needs is read off the
            case's participant index, so that it names the actor actually
            holding CASE_MANAGER (PCR-08-008).
        vendor2_id: Deterministic URI for the Vendor2 actor.
    """
    logger.info("=" * 80)
    logger.info(
        "RVCV-HANDOFF DEMO: Reporter + Vendor1 → Coordinator (ownership) +"
        " Vendor2"
    )
    logger.info("=" * 80)
    logger.info("Reporter container:    %s", reporter_client.base_url)
    logger.info("Vendor1 container:     %s", vendor_client.base_url)
    logger.info("Coordinator container: %s", coordinator_client.base_url)
    logger.info("CaseActor container:   %s", case_actor_client.base_url)
    logger.info("Vendor2 container:     %s", vendor2_client.base_url)
    logger.debug("CaseActor id override, unused: %s", case_actor_id)

    open_cast = vendor_open_cast(
        reporter_client=reporter_client,
        vendor_client=vendor_client,
        case_actor_client=case_actor_client,
        dump=dump_vendor_coordinator_ledgers,
        reporter_id=reporter_id,
        vendor_id=vendor_id,
        unseated=unseated_coordinator_and_vendor2(
            coordinator_client=coordinator_client,
            coordinator_id=coordinator_id,
            vendor2_client=vendor2_client,
            vendor2_id=vendor2_id,
        ),
    )

    # run_story() owns the failure accumulator through scenario_harness: it
    # resets it, always dumps the case ledgers, and asserts success — so a
    # failure here never costs us the artifacts (ISSUE-2239, DEMOMA-23-001).
    run_story(DEMO_NAME, STORY, open_cast)

    logger.info("=" * 80)
    logger.info(
        "RVCV-HANDOFF DEMO COMPLETE ✓  (ownership transfer + VFDPxa full"
        " lifecycle)"
    )
    logger.info("=" * 80)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


@scenario(
    name=DEMO_NAME,
    label="RVCV-handoff",
    participants="Reporter + Vendor1 → Coordinator + Vendor2",
    feature="Case-ownership transfer to coordinator",
    in_pr_set=True,
    story=STORY,
)
def main(
    skip_health_check: bool = False,
    reporter_url: str | None = None,
    vendor_url: str | None = None,
    coordinator_url: str | None = None,
    case_actor_url: str | None = None,
    vendor2_url: str | None = None,
    reporter_id: str | None = None,
    vendor_id: str | None = None,
    coordinator_id: str | None = None,
    case_actor_id: str | None = None,
    vendor2_id: str | None = None,
) -> None:
    """Entry point for the RVCV-handoff CVD workflow demo.

    Args:
        skip_health_check: Skip the server availability check.
        reporter_url: Override base URL for the Reporter container.
        vendor_url: Override base URL for the Vendor1 container.
        coordinator_url: Override base URL for the Coordinator container.
        case_actor_url: Override base URL for the CaseActor container.
        vendor2_url: Override base URL for the Vendor2 container.
        reporter_id: Optional deterministic URI for the Reporter actor.
        vendor_id: Optional deterministic URI for the Vendor1 actor.
        coordinator_id: Optional deterministic URI for the Coordinator actor.
        case_actor_id: Optional deterministic URI for the CaseActor actor.
        vendor2_id: Optional deterministic URI for the Vendor2 actor.
    """
    clients = story_clients(
        _ROLES,
        vendor_coordinator_cast_members(
            reporter_url=reporter_url,
            vendor_url=vendor_url,
            coordinator_url=coordinator_url,
            vendor2_url=vendor2_url,
        ),
        skip_health_check=skip_health_check,
        case_actor_url=case_actor_url,
    )
    run_rvcv_handoff_demo(
        reporter_client=clients[REPORTER],
        vendor_client=clients[VENDOR],
        coordinator_client=clients[COORDINATOR],
        case_actor_client=clients[CASE_ACTOR_NAME],
        vendor2_client=clients[VENDOR2],
        **resolved_actor_ids(
            _ROLES,
            reporter=(clients[REPORTER], reporter_id),
            vendor=(clients[VENDOR], vendor_id),
            coordinator=(clients[COORDINATOR], coordinator_id),
            vendor2=(clients[VENDOR2], vendor2_id),
        ),
        case_actor_id=case_actor_id,
    )


if __name__ == "__main__":
    setup_demo_logging()
    main()
