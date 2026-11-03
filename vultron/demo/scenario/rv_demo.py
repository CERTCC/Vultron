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

"""rv (Reporter + Vendor) multi-container CVD workflow demo.

Two actor containers plus a dedicated CaseActor:

- Reporter: the report submitter, seated when the case is created
  (CM-22-002), so it is never invited;
- Vendor (cast slot 1, the first Vendor): CASE_OWNER throughout, and the only
  actor with a fix path (DEMOMA-06-002);
- CaseActor (case-actor container): holds the canonical case and ledger
  (DEMOMA-06-005).

Cast (DEMOCI-11-020): every scenario runs the same containers, so a role's
address and actor id are the same here as in its siblings.  ``ROLES`` below
seats each actor; the cast table is ``vultron/demo/helpers/cast.py``.

The story is assembled, not written out: it starts with
:data:`~vultron.demo.helpers.vendor_story.REPORTER_TELLS_THE_VENDOR`, the
opening it shares with every vendor-first scenario, and continues through the
replica synchronization, the note thread and the Vendor's fix
(:data:`STORY`, DEMOCI-11-019).  The two steps it tells between that opening
and the note thread its siblings post next — the M1 participant check and the
M2 replica synchronization — read replicas and write nothing, so they move no
byte of the recording the siblings must match (DEMOCI-11-018).

Spec: DEMOMA-06 (D5-1-G5).
"""

import logging

from vultron.core.states.cs import CS_vf
from vultron.demo.helpers.actor_roles import (
    ActorRole,
    case_actor_role,
    resolved_actor_ids,
    role_map,
)
from vultron.demo.helpers.cast import REPORTER_SLOT, VENDOR_SLOT
from vultron.demo.helpers.coordinated_story import (
    REPORTER,
    REPORTER_LABEL,
    close_the_case,
    reports_published,
    vendor_notifies_fix_ready,
)
from vultron.demo.helpers.polling import wait_for_participant_vf_state
from vultron.demo.helpers.story import StoryState, choose, run_story, story
from vultron.demo.helpers.story_cast import (
    CASE_ACTOR_NAME,
    CastContainer,
    story_clients,
)
from vultron.demo.helpers.sync import run_sync_verification_phase
from vultron.demo.helpers.vendor_story import (
    REPORTER_TELLS_THE_VENDOR,
    REPORTERS_QUESTION,
    VENDOR,
    VENDOR_LABEL,
    VENDORS_ANSWER,
    dump_vendor_ledgers,
    required_participants_are_present,
    the_disclosure_reached_every_replica,
    the_embargo_ends_for,
    the_fix_ready_reached_the_reporter,
    the_reporter_asks_about_the_workaround,
    vendor_open_cast,
)
from vultron.demo.helpers.verification import (
    verify_case_actor_holds_records,
    verify_receiver_case_state,
)
from vultron.demo.scenario.registry import scenario
from vultron.demo.utils import (
    DataLayerClient,
    demo_check,
    demo_gate,
    logfmt,
    setup_demo_logging,
)

logger = logging.getLogger(__name__)

DEMO_NAME = "rv"

#: What this scenario calls its one Vendor on the command line and in the
#: health check.  The family's story labels say ``Vendor1`` whatever a
#: scenario's ``ROLES`` call it (:data:`~vultron.demo.helpers.vendor_story\
#: .VENDOR_LABEL`), because one authored opening means one label; rv has only
#: one Vendor, so its own CLI help and reset labels keep the plainer name.
VENDOR_ROLE_LABEL = "Vendor"

# The scenario's actors in main() parameter order, each seated in a container of
# the fixed cast (DEMOCI-11-020).  The demo CLI derives this scenario's
# sub-command options from this list (DEMOCI-11-011).
ROLES: list[ActorRole] = [
    ActorRole(REPORTER, REPORTER_SLOT, REPORTER_LABEL, has_id=True),
    ActorRole(VENDOR, VENDOR_SLOT, VENDOR_ROLE_LABEL, has_id=True),
    case_actor_role(),
]
#: Indexed for the CLI factory and for ``story_clients()``, which reads
#: each actor's container address off its cast slot — so this module declares
#: no ``*_BASE_URL`` constant of its own (DEMOCI-11-020).
_ROLES = role_map(ROLES)

#: ``vultron-demo rv --help`` text. Lives here rather than in ``cli.py`` because
#: the sub-command is generated from the registry and the scenario module is the
#: only place that knows what its own workflow does.
CLI_HELP = """Run the rv (Reporter + Vendor) multi-container CVD demo (D5-1-G5).

Orchestrates a complete CVD workflow across two separate API server
containers.  Requires both containers to be running and reachable at
the configured base URLs.

Use ``--reporter-url`` / ``--vendor-url`` (or the cast's env vars,
``VULTRON_ACTOR0_BASE_URL`` / ``VULTRON_ACTOR1_BASE_URL``) to point
the demo at running containers.

\b
Workflow (six phases; titles match docs/tutorials/rv-demo.md):
  Setup. Seed both containers (actor records + peer registration).
  1. Report submission and case activation (M1): Reporter submits a report
     to Vendor's inbox; Vendor's tree proposes a case and the CaseActor
     creates it, seating the Reporter (it is never invited);
     Vendor validates (trigger: validate-report) and engages the case
     (trigger: engage-case).
  2. Replica synchronization verification (M2): verify the Reporter's case
     replica and that the ledgers synchronized.
  3. Notes exchange (M3): Reporter and Vendor exchange notes.
  4. Fix lifecycle (M4-M5): Vendor reports fix ready (VFd; Vendor stops
     at VFd).
  5. Publication and embargo teardown (M6): Vendor and Reporter report
     publication; embargo terminates (EM.EXITED).
  6. Case closure (M7): the Reporter closes the case, then the Vendor, the
     Case Owner, closes it last (every RM.CLOSED in the Case Actor's store).
"""


# ---------------------------------------------------------------------------
# Fragments this scenario alone tells
# ---------------------------------------------------------------------------


def the_case_is_active(state: StoryState) -> None:
    """M1: the Reporter and the Vendor are seated and the embargo is active."""
    required_participants_are_present(
        state,
        check=(
            "M1: required participants (vendor + reporter + case-actor, ≥3), "
            "EM.ACTIVE, reporter has case replica"
        ),
    )


def the_reporter_replica_converges(state: StoryState) -> None:
    """M2: the Reporter's replica follows the Vendor's authoritative state.

    Synthetic checkpoint entries (``demo_verification``) are excluded from the
    canonical case ledger (ADR-0019, CLP-07-004), so replication is verified
    by comparing replica state directly rather than polling for a new entry
    (#1434).  Then the dedicated case-actor container is read for the
    canonical records, which no participant replica holds (DEMOMA-06-004).

    This scenario's own step: its siblings check their replicas after the
    actors they invite have joined, which is after the branch point.  It reads
    replicas and writes nothing, so it moves no byte of the opening the
    siblings must match (DEMOCI-11-018).
    """
    run_sync_verification_phase(
        auth_client=state.client(VENDOR),
        auth_label=VENDOR_LABEL,
        auth_actor_id=state.actor_id(VENDOR),
        reporter_client=state.client(REPORTER),
        reporter_actor_id=state.actor_id(REPORTER),
        replicas=[(state.client(REPORTER), REPORTER_LABEL)],
        case_id=state.case.id_,
        state_checks=[(state.client(REPORTER), REPORTER_LABEL)],
    )

    with demo_check(
        "Dedicated case-actor container holds the case, with its CaseActor as"
        " the CASE_MANAGER participant (DEMOMA-06-004)"
    ):
        verify_case_actor_holds_records(
            state.case_actor_client, state.case.id_
        )

    logger.info(
        "✓ M2: Reporter DataLayer synchronized (LedgerFanout verified)"
    )


def the_vendor_holds_the_final_case(state: StoryState) -> None:
    """M3: the Vendor's container holds the authoritative case, both notes on it.

    Reads both notes of the thread the opening posted, so the check names the
    question and the answer rather than asserting ``None`` twice
    (:data:`~vultron.demo.helpers.vendor_story.REPORTERS_QUESTION`,
    :data:`~vultron.demo.helpers.vendor_story.VENDORS_ANSWER`).
    """
    question = state.kept(REPORTERS_QUESTION)
    answer = state.kept(VENDORS_ANSWER)
    with demo_check(
        "M3: Vendor container holds the authoritative final case state"
    ):
        final_case = verify_receiver_case_state(
            receiver_client=state.client(VENDOR),
            case_id=state.case.id_,
            report_id=state.report.id_,
            receiver_actor_id=state.actor_id(VENDOR),
            reporter_actor_id=state.actor_id(REPORTER),
            question_note_id=question.id_,
            reply_note_id=answer.id_,
        )
        logger.info("Final case state (Vendor): %s", logfmt(final_case))


def the_vendor_reports_the_fix_ready(state: StoryState) -> None:
    """The Vendor reports fix ready and stops at VFd (CSB-15-002).

    The milestone checks nest inside the trigger's gate and inside a gate on
    the Reporter's replica, so a refused trigger or a replica that never
    caught up skips them rather than comparing state that was never written
    (CSB-18-001, DEMOCI-01-011).
    """
    vendor_notifies_fix_ready(
        state,
        VENDOR,
        VENDOR_LABEL,
        then=lambda: _the_reporter_replica_reflects_the_fix(state),
    )


def _the_reporter_replica_reflects_the_fix(state: StoryState) -> None:
    """The M4 and M5 milestones, inside the gate on the Reporter's replica."""
    with demo_gate("M4/M5: reporter replica reflects fix-ready vf_state"):
        wait_for_participant_vf_state(
            client=state.client(REPORTER),
            case_id=state.case.id_,
            actor_id=state.actor_id(VENDOR),
            expected_states={CS_vf.VF},
        )
        the_fix_ready_reached_the_reporter(
            state,
            milestones=(
                "M4: both replicas show CS includes F (fix ready)",
                "M5: both replicas show CS includes F (fix ready) — vendor"
                " stops at VFd",
            ),
        )


def both_publish(state: StoryState) -> None:
    """The Vendor, as CASE_OWNER, publishes first; then the Reporter."""
    reports_published(state, VENDOR)
    the_embargo_ends_for(
        state,
        check="Embargo terminated (EM.EXITED) after Vendor reports published",
        watcher=VENDOR,
    )
    reports_published(state, REPORTER)
    the_disclosure_reached_every_replica(
        state,
        check=(
            "M6: both replicas CS.VFdPxa, EM.EXITED, vendor participant is "
            "public-aware"
        ),
    )


def both_close(state: StoryState) -> None:
    """The Reporter leaves; the Vendor, the Case Owner, leaves last."""
    close_the_case(state, others=(REPORTER,), owner=VENDOR, milestone="M7")


def _dump_ledgers(state: StoryState) -> None:
    """Dump each participant's case ledger, by its devlogs name.

    Thin wrapper (DEMOMA-23-002): the harness runs it on the way out, whether
    or not an earlier step failed.
    """
    dump_vendor_ledgers(state, (REPORTER, VENDOR))


#: The rv story: the opening every vendor-first scenario shares, then the
#: replica synchronization, the note thread and the Vendor's fix through to
#: closure.  The registry reads this scenario's path off the ``choose`` items
#: (DEMOCI-11-019), so it declares no ``path=``.
STORY = story(
    REPORTER_TELLS_THE_VENDOR,
    the_case_is_active,
    the_reporter_replica_converges,
    the_reporter_asks_about_the_workaround,
    the_vendor_holds_the_final_case,
    # The Vendor decides once it has answered the Reporter's question.
    choose("vendor-after-answer", "report-fix-ready", by=VENDOR),
    the_vendor_reports_the_fix_ready,
    both_publish,
    both_close,
)


def run_rv_demo(
    reporter_client: DataLayerClient,
    vendor_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    reporter_id: str | None = None,
    vendor_id: str | None = None,
) -> None:
    """Orchestrate the complete rv (Reporter + Vendor) CVD workflow."""
    logger.info("=" * 80)
    logger.info("rv DEMO: Reporter + Vendor CVD Workflow (VFDPxa)")
    logger.info("=" * 80)
    logger.info("Reporter container: %s", reporter_client.base_url)
    logger.info("Vendor container: %s", vendor_client.base_url)
    logger.info("CaseActor container: %s", case_actor_client.base_url)

    open_cast = vendor_open_cast(
        reporter_client=reporter_client,
        vendor_client=vendor_client,
        case_actor_client=case_actor_client,
        dump=_dump_ledgers,
        reporter_id=reporter_id,
        vendor_id=vendor_id,
    )

    # run_story() owns the failure accumulator through scenario_harness: it
    # resets it, always dumps the case ledgers, and asserts success — so a
    # failure here never costs us the artifacts (ISSUE-2239, DEMOMA-23-001).
    run_story(DEMO_NAME, STORY, open_cast)

    logger.info("=" * 80)
    logger.info("rv DEMO COMPLETE ✓  (VFDPxa full lifecycle)")
    logger.info("=" * 80)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


@scenario(
    name=DEMO_NAME,
    label="rv",
    participants="Reporter + Vendor",
    feature="Baseline two-actor CVD",
    in_pr_set=True,
    story=STORY,
)
def main(
    skip_health_check: bool = False,
    reporter_url: str | None = None,
    vendor_url: str | None = None,
    case_actor_url: str | None = None,
    reporter_id: str | None = None,
    vendor_id: str | None = None,
) -> None:
    """Entry point for the rv (Reporter + Vendor) multi-container CVD workflow demo.

    Args:
        skip_health_check: Skip the server availability check (useful for
            testing).
        reporter_url: Override base URL for the Reporter container.
        vendor_url: Override base URL for the Vendor container.
        case_actor_url: Override base URL for the dedicated CaseActor container.
        reporter_id: Optional deterministic URI for the Reporter actor.
        vendor_id: Optional deterministic URI for the Vendor actor.
    """
    clients = story_clients(
        _ROLES,
        [
            CastContainer(REPORTER, REPORTER_LABEL, reporter_url),
            CastContainer(VENDOR, VENDOR_ROLE_LABEL, vendor_url),
        ],
        skip_health_check=skip_health_check,
        case_actor_url=case_actor_url,
    )
    run_rv_demo(
        reporter_client=clients[REPORTER],
        vendor_client=clients[VENDOR],
        case_actor_client=clients[CASE_ACTOR_NAME],
        **resolved_actor_ids(
            _ROLES,
            reporter=(clients[REPORTER], reporter_id),
            vendor=(clients[VENDOR], vendor_id),
        ),
    )


if __name__ == "__main__":
    setup_demo_logging()
    main()
