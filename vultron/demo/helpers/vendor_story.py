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
"""Story fragments of the vendor-first half of the tree: the Reporter tells a Vendor.

``rv``, ``rvv``, ``rvcv-extension`` and ``rvcv-handoff`` all open the same
way — the Reporter submits its report to a Vendor, the Vendor validates it and
engages the case as CASE_OWNER, and the Reporter then asks whether a
workaround exists and the Vendor answers.  That opening is written here
**once** and each scenario assembles its story from the longest prefix it
shares with its siblings (:mod:`vultron.demo.helpers.story`), so no two of
them place it by hand (DEMOMA-17-001, DEMOCI-11-018).

The prefixes nest, one per shared stretch, so a sibling cannot slip an act in
before a branch point (``notes/demo-scenario-tree.md`` § "Composition"):

* :data:`REPORTER_TELLS_THE_VENDOR` stops once the Vendor holds the case and
  its roster.  All four scenarios start with it.
* :data:`THE_VENDOR_ANSWERS_THE_REPORTER` continues through the note thread
  and stops where the Vendor's ``vendor-after-answer`` decision falls, which
  follows its own answer in that thread.  ``rvv`` and the ``rvcv`` pair part
  here — ``rv`` tells the same two steps with two replica checks of its own in
  between, which write nothing and so move no byte of its recording
  (``vultron/demo/scenario/rv_demo.py``).
* :data:`~vultron.demo.helpers.vendor_coordinator_story\
  .THE_VENDOR_INVITES_A_COORDINATOR` continues through the Coordinator's join
  and stops where the owner's ``owner-keep-case`` decision falls.  The
  ``rvcv`` pair parts there.

The family seats its Reporter under :data:`REPORTER` and its first Vendor
under :data:`VENDOR`, whatever each scenario's ``ROLES`` calls them: the
Reporter's cast name is the one the continuations both halves of the tree
share read it under (:mod:`vultron.demo.helpers.owner_decision_story`), and
one copy of each fragment here then serves every scenario.  A scenario's
further containers — the second Vendor, and the Coordinator in the ``rvcv``
pair — are reset with the rest and seeded by the fragment that brings each
into the case, never by the shared opening: what the opening writes before the
case exists is part of the bytes its siblings must match (DEMOCI-11-018,
#5532).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence

from vultron.core.states.cs import CS_vf
from vultron.demo.helpers.coordinated_story import (
    REPORTER,
    REPORTER_LABEL,
    await_reporter_case_replica,
    vendor_notifies_fix_ready,
)
from vultron.demo.helpers.harness import ScenarioHarness
from vultron.demo.helpers.milestones import (
    verify_case_active,
    verify_fix_ready,
    verify_publicly_disclosed,
)
from vultron.demo.helpers.notes import (
    WORKAROUND_QUESTION,
    NotePost,
    add_note_thread,
    reporter_asks,
    vendor_answers_workaround,
)
from vultron.demo.helpers.owner_decision_story import Part
from vultron.demo.helpers.polling import (
    LATE_JOINER_TIMEOUT,
    wait_for_case_em_terminated,
    wait_for_case_participants,
    wait_for_participant_vf_state,
)
from vultron.demo.helpers.seeding import seed_containers
from vultron.demo.helpers.story import (
    Fragment,
    StoryProp,
    StoryState,
    UnseatedContainer,
    choose,
    story,
)
from vultron.demo.helpers.story_cast import (
    CastSeat,
    dump_story_ledgers,
    open_story_cast,
)
from vultron.demo.helpers.workflow import (
    reporter_submits_report,
    run_direct_path_rm_triage,
)
from vultron.demo.utils import DataLayerClient, demo_check, demo_gate
from vultron.wire.as2.vocab.base.objects.object_types import as_Note
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

logger = logging.getLogger(__name__)

#: The names this family's stories seat their two opening members under, and
#: so the keys of :attr:`StoryState.cast` every fragment here reads.  The
#: Reporter's is the rcv family's, because the continuations both halves of
#: the tree share read the Reporter under that name
#: (:data:`~vultron.demo.helpers.owner_decision_story.REPORTER_PART`).
VENDOR = "vendor"

#: The second Vendor, which three of the four scenarios bring in: ``rvv`` by
#: invitation from the first Vendor, the ``rvcv`` pair through the owner's
#: decision.  Seated by the fragment that seeds it, never by the opening.
VENDOR2 = "vendor2"

#: How the two vendors are named in this family's step and gate labels.
#: ``Vendor1`` rather than ``Vendor`` even in ``rv``, which has only one: one
#: authored opening means one label, and three of the four scenarios have a
#: second Vendor to tell it apart from.  Each scenario's ``ROLES`` keeps its
#: own labels, which is what the CLI help and the health check read.
VENDOR_LABEL = "Vendor1"
VENDOR2_LABEL = "Vendor2"

#: Seconds the first Vendor's own RM triage may take.  One authored opening
#: means one budget, so it is the widest member's: the ``rvcv`` pair raised it
#: to 60 s for a run that brings five actor containers up under CI load, and
#: the narrower scenarios inherit it.  A budget only bounds how long a wait may
#: take, so raising it refuses nothing a shorter one admitted and moves no byte
#: of a recording (DEMOCI-11-018).
VENDOR_TRIAGE_TIMEOUT = 60.0

#: Seconds the Reporter's case replica may take to arrive.  The 30 s
#: ``wait_for_reporter_case`` budget every scenario of this family used for it.
CASE_REPLICA_TIMEOUT = 30.0

#: Seconds each cross-container wait of a joiner's arrival may take.  Every
#: join of this family reaches its actor through the CaseActor — invited
#: directly, suggested and approved, or invited by a new owner — so each wait
#: queues behind the same outbox and takes the late-joiner budget, the widest
#: any of these scenarios carried before the step was shared.
JOIN_TIMEOUT = LATE_JOINER_TIMEOUT

#: The parts the continuations of ``owner-keep-case`` act on
#: (:mod:`vultron.demo.helpers.owner_decision_story`).
VENDOR_PART = Part(VENDOR, VENDOR_LABEL)
VENDOR2_PART = Part(VENDOR2, VENDOR2_LABEL)

#: The case whose roster the Vendor has confirmed, as its id.  Read by the
#: first fragment of each scenario's continuation — the note thread, or
#: ``rv``'s own M1 check, whichever that scenario tells next — because the
#: Reporter and the Vendor both being seated is what every later step
#: presupposes: a roster that never arrived must stop the story rather than
#: post into a case the owner cannot vouch for, or check participants that
#: were never seated (DEMOCI-01-011, ``vultron/demo/AGENTS.md`` § "Never Wrap
#: a Causal Wait in demo_check").  A flat story cannot nest those steps inside
#: the roster's gate, so the gate keeps this and they read it.
THE_VENDORS_CASE: StoryProp[str] = StoryProp(
    "case whose roster the Vendor confirmed", str
)

#: The Reporter's workaround question, as the note the case holds.  Read by
#: ``rv``'s final case check, which asserts both notes of the thread are on
#: the case (:func:`~vultron.demo.helpers.verification\
#: .verify_receiver_case_state`).
REPORTERS_QUESTION: StoryProp[as_Note] = StoryProp(
    "Reporter's workaround question", as_Note
)

#: The Vendor's answer to it.  Read by every scenario whose joiners reply to
#: the thread the opening posted rather than opening one of their own, and by
#: ``rv``'s final case check (DEMOCI-11-017).
VENDORS_ANSWER: StoryProp[as_Note] = StoryProp(
    "Vendor's workaround answer", as_Note
)


# ---------------------------------------------------------------------------
# Containers and cast
# ---------------------------------------------------------------------------


def vendor_seats(
    *,
    reporter_client: DataLayerClient,
    vendor_client: DataLayerClient,
    reporter_id: str | None = None,
    vendor_id: str | None = None,
) -> tuple[CastSeat, CastSeat]:
    """The two seats the shared opening seeds, in ``seed_containers`` order.

    Only two, whatever else a scenario runs: the opening seeds the containers
    *every* sibling uses, and each further actor and peer record written
    before the case exists moves the first ledger entry away from the siblings
    this opening must match byte for byte (DEMOCI-11-018, #5532).
    """
    return (
        CastSeat(REPORTER, REPORTER_LABEL, reporter_client, reporter_id),
        CastSeat(VENDOR, VENDOR_LABEL, vendor_client, vendor_id),
    )


def open_vendor_cast(
    harness: ScenarioHarness,
    *,
    reporter_client: DataLayerClient,
    vendor_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    dump: Fragment,
    reporter_id: str | None = None,
    vendor_id: str | None = None,
    unseated: Mapping[str, UnseatedContainer] | None = None,
) -> StoryState:
    """Reset this family's containers, seed its two, and return its cast.

    The opening of every vendor-first scenario: the same reset and the same
    seeding, so no scenario writes either (DEMOMA-17-001).

    Args:
        harness: The run's :class:`~vultron.demo.helpers.harness\
            .ScenarioHarness`.
        reporter_client: Client for the Reporter's container.
        vendor_client: Client for the first Vendor's container.
        case_actor_client: Client for the dedicated case-actor container.
        dump: The scenario's ledger dump, armed when the case opens.
        reporter_id: Deterministic URI for the Reporter actor, when given.
        vendor_id: Deterministic URI for the first Vendor's actor.
        unseated: Each further container the scenario will seed and seat an
            actor in, by the name it will seat it under.  Reset here with the
            rest, seeded by the fragment that brings its actor into the case
            (:class:`UnseatedContainer`).

    Returns:
        The story state the family's fragments run against.

    Raises:
        DemoStoryError: When the containers could not be seeded, so there is
            no cast to tell the story with.
    """
    return open_story_cast(
        harness,
        seats=vendor_seats(
            reporter_client=reporter_client,
            vendor_client=vendor_client,
            reporter_id=reporter_id,
            vendor_id=vendor_id,
        ),
        seed=lambda: seed_containers(
            reporter_client=reporter_client,
            vendor_client=vendor_client,
            reporter_actor_id=reporter_id,
            vendor_actor_id=vendor_id,
            case_actor_client=case_actor_client,
        ),
        seed_step="Seeding the Reporter and Vendor containers",
        case_actor_client=case_actor_client,
        dump=dump,
        unseated=unseated,
    )


def vendor_open_cast(
    *,
    reporter_client: DataLayerClient,
    vendor_client: DataLayerClient,
    case_actor_client: DataLayerClient,
    dump: Fragment,
    reporter_id: str | None = None,
    vendor_id: str | None = None,
    unseated: Mapping[str, UnseatedContainer] | None = None,
) -> Callable[[ScenarioHarness], StoryState]:
    """The ``open_cast`` callable :func:`~.story.run_story` takes.

    Every scenario of the family hands ``run_story`` the same closure over
    :func:`open_vendor_cast`, so it is built here rather than written out once
    per scenario module (DEMOMA-17-001).  The arguments are
    :func:`open_vendor_cast`'s; the harness is the one ``run_story`` enters,
    which is what puts a seeding failure inside the harness that dumps and
    reports it.

    The closure calls :func:`open_vendor_cast` rather than
    :func:`~vultron.demo.helpers.story_cast.open_story_cast` with the same
    arguments: the seats, the seeder and the step label would then exist twice
    and could drift (CS-22-001), and the opening would be reachable only
    through this factory, so a test that patches :func:`open_vendor_cast` as
    the first step of the run that can die would patch nothing
    (``test/demo/test_issue_2239_ledger_dump_in_finally.py``, DEMOMA-23-003).
    """

    def open_cast(harness: ScenarioHarness) -> StoryState:
        return open_vendor_cast(
            harness,
            reporter_client=reporter_client,
            vendor_client=vendor_client,
            case_actor_client=case_actor_client,
            dump=dump,
            reporter_id=reporter_id,
            vendor_id=vendor_id,
            unseated=unseated,
        )

    return open_cast


def dump_vendor_ledgers(state: StoryState, replicas: Sequence[str]) -> None:
    """Dump each named cast member's case ledger, and the canonical one.

    Thin wrapper (DEMOMA-23-002): the harness runs it on the way out, whether
    or not an earlier step failed.  An actor the run never seated has no
    replica to read, so it is left out rather than 404ing the dump.  Every
    scenario of this family names its actors the same on the command line, in
    ``ROLES`` and in its devlogs, so one cast name serves all three.

    Args:
        state: The running story's state.
        replicas: Whose replicas to dump, in dump order.
    """
    dump_story_ledgers(
        state, replicas=[name for name in replicas if name in state.cast]
    )


# ---------------------------------------------------------------------------
# The shared opening
# ---------------------------------------------------------------------------


def the_reporter_tells_the_vendor(state: StoryState) -> None:
    """The Reporter submits its report; the Vendor engages the case.

    The Vendor validates the report and engages the case (RM→ACCEPTED),
    holding CASE_OWNER; each step is gated on its own RM state.  The Reporter
    is seated when the case is created (CM-22-002), so it is never invited.

    The case is recorded as soon as the triage returns it, which arms the
    ledger dump at the first instant there is anything to dump, so every step
    below can fail without costing the ledgers (DEMOMA-23-003, ISSUE-2239).
    Then the roster wait is a ``demo_gate``: the Reporter and the Vendor both
    being seated is the precondition for every later step, so a timeout skips
    the Reporter's replica check, the re-read and :data:`THE_VENDORS_CASE`,
    and the fragment that runs next stops the story rather than acting on a
    case the owner cannot vouch for (DEMOCI-01-011).
    """
    reporter = state.actor(REPORTER).actor
    vendor = state.actor(VENDOR).actor
    owner_client = state.client(VENDOR)
    report, offer = reporter_submits_report(
        receiver_client=owner_client,
        reporter=reporter,
        receiver=vendor,
        reporter_client=state.client(REPORTER),
    )
    case = run_direct_path_rm_triage(
        receiver_client=owner_client,
        receiver=vendor,
        offer=offer,
        timeout_seconds=VENDOR_TRIAGE_TIMEOUT,
    )
    # Recorded here, at the first instant there is anything to dump, so every
    # step below can fail without costing the ledgers (DEMOMA-23-003,
    # ISSUE-2239) — including the gate that follows.
    state.open_case(case=case, report=report, offer=offer)

    with demo_gate(
        f"{VENDOR_LABEL} case reflects Reporter + {VENDOR_LABEL} participants"
    ):
        wait_for_case_participants(
            vendor_client=owner_client,
            case_id=case.id_,
            expected_actor_ids={reporter.id_, vendor.id_},
        )

        # CLP-08-005: the Reporter needs the case before any later step
        # broadcasts Announce(CaseLedgerEntry) to it (Bug #2135).
        await_reporter_case_replica(state, CASE_REPLICA_TIMEOUT)

        # Re-read the case as the Vendor now stores it: the triage and the
        # participant seating have moved on since the trigger returned it.
        state.restate_case(
            as_VulnerabilityCase.model_validate(
                owner_client.get(owner_client.dl_path(case.id_))
            )
        )
        state.keep(THE_VENDORS_CASE, str(case.id_))


#: The opening every vendor-first scenario shares: the Reporter tells the
#: Vendor, and the Vendor engages the case and holds its roster.  Named rather
#: than assembled from the fragment at each call site, because assembling
#: siblings from fragments alone lets one of them slip a step in before the
#: branch point (``notes/demo-scenario-tree.md`` § "Composition").
REPORTER_TELLS_THE_VENDOR = story(
    choose("reporter-whom-to-tell", "vendor", by=REPORTER),
    the_reporter_tells_the_vendor,
)


def the_reporter_asks_about_the_workaround(state: StoryState) -> None:
    """The Reporter asks whether a workaround exists; the Vendor answers.

    The thread every vendor-first scenario posts before the Vendor's
    ``vendor-after-answer`` decision, which follows the Vendor's own answer in
    it (``notes/demo-scenario-registry.md``).  Both notes are kept: a
    continuation replies to the answer rather than opening a thread of its own
    (:data:`VENDORS_ANSWER`), and ``rv``'s final case check names both
    (:data:`REPORTERS_QUESTION`).

    Reads :data:`THE_VENDORS_CASE` first: the Reporter posts from its own
    replica of a case whose roster the owner has confirmed, so a roster that
    never arrived stops the story here (DEMOCI-01-011).
    """
    state.kept(THE_VENDORS_CASE)
    posted = reporter_asks(
        state.actor(REPORTER),
        state.client(VENDOR),
        state.case,
        WORKAROUND_QUESTION,
        [vendor_answers_workaround(state.actor(VENDOR))],
    )
    # strict=False, because a failed gate posts nothing at all and a failed
    # post reads back as None: fewer notes than props is the recorded-failure
    # case, which must keep nothing and let the fragments that read a prop
    # stop the story, not raise a shape error of its own (:func:`run_story`).
    props: tuple[StoryProp[as_Note], ...] = (
        REPORTERS_QUESTION,
        VENDORS_ANSWER,
    )
    for prop, note in zip(props, posted, strict=False):
        if note is not None:
            state.keep(prop, note)
    logger.info(
        "✓ Notes exchange complete (two notes committed to case ledger)"
    )


#: The opening through the note thread the Reporter opens, which stops where
#: the Vendor's ``vendor-after-answer`` decision falls.  ``rvv`` and the
#: ``rvcv`` pair start with it; ``rv`` tells the same two steps with two
#: replica checks of its own in between (module docstring).
THE_VENDOR_ANSWERS_THE_REPORTER = story(
    REPORTER_TELLS_THE_VENDOR,
    the_reporter_asks_about_the_workaround,
)


# ---------------------------------------------------------------------------
# Continuations shared by more than one scenario of the family
# ---------------------------------------------------------------------------


def required_participants_are_present(
    state: StoryState, *, check: str
) -> None:
    """The case holds every participant invited so far, and is still embargoed.

    Read from the first Vendor's replica, which holds the case from the moment
    it engaged it whether or not it is still the owner.  Each scenario numbers
    this milestone itself and names the participants it expects by then, so the
    label is the caller's; the reads are the same in all four.

    Reads :data:`THE_VENDORS_CASE` first, so a roster that never arrived stops
    the story here instead of checking participants that were never seated
    (DEMOCI-01-011).

    Args:
        state: The running story's state.
        check: This scenario's ``demo_check`` label for the milestone.
    """
    state.kept(THE_VENDORS_CASE)
    with demo_check(check):
        verify_case_active(
            receiver_client=state.client(VENDOR),
            reporter_client=state.client(REPORTER),
            case_id=state.case.id_,
            receiver_actor_id=state.actor_id(VENDOR),
            reporter_actor_id=state.actor_id(REPORTER),
        )


def the_fix_ready_reached_the_reporter(
    state: StoryState, *, milestones: Sequence[str]
) -> None:
    """The first Vendor reads VF on its own and on the Reporter's replica.

    One copy of the check every scenario of this family makes **twice**, under
    two milestone labels — ``rv``'s M4 and M5, ``rvv``'s M4 and M5,
    ``rvcv-extension``'s M5 and M6, and ``rvcv-handoff``'s two unnumbered
    ones.  The second one asserts exactly what the first does; a consolidation
    must not change what a scenario passes or fails on (DEMOMA-17-002), so the
    repetition is kept as it was and #5602 tracks making the pair say two
    different things.

    Args:
        state: The running story's state.
        milestones: The ``demo_check`` label of each milestone, in order.
    """
    for check in milestones:
        with demo_check(check):
            for watcher in (VENDOR, REPORTER):
                wait_for_participant_vf_state(
                    client=state.client(watcher),
                    case_id=state.case.id_,
                    actor_id=state.actor_id(VENDOR),
                    expected_states={CS_vf.VF},
                )
            verify_fix_ready(
                receiver_client=state.client(VENDOR),
                reporter_client=state.client(REPORTER),
                case_id=state.case.id_,
                receiver_actor_id=state.actor_id(VENDOR),
            )


def both_vendors_report_the_fix_ready(
    state: StoryState, *, milestones: Sequence[str]
) -> None:
    """Each Vendor reports fix ready (VFd), gated on its own RM state.

    Both hold ``CVDRole.VENDOR`` and not ``DEPLOYER``, so both stop at VFd
    (CSB-15-002); each trigger is refused until that vendor's own participant
    record is out of triage, which is the gate
    (:func:`~vultron.demo.helpers.coordinated_story\
    .vendor_notifies_fix_ready`, CSB-18-001).  Told by every scenario of this
    family that has a second Vendor.

    Args:
        state: The running story's state.
        milestones: This scenario's labels for the two milestones that follow
            (:func:`the_fix_ready_reached_the_reporter`).
    """
    for name, label in ((VENDOR, VENDOR_LABEL), (VENDOR2, VENDOR2_LABEL)):
        vendor_notifies_fix_ready(state, name, label)
    the_fix_ready_reached_the_reporter(state, milestones=milestones)


def the_joiners_add_their_notes(
    state: StoryState, updates: Sequence[NotePost]
) -> None:
    """The actors that joined after the opening answer the thread it posted.

    They reply to the Vendor's answer rather than opening a thread of their
    own, so the thread the opening shares with every sibling stays one thread
    (:data:`VENDORS_ANSWER`, DEMOCI-11-017).  Posted through the first
    Vendor's replica, which every scenario of the family watches.

    Reads :data:`VENDORS_ANSWER` first: a thread whose answer never landed has
    nothing to reply to, so the story stops here rather than posting an
    unthreaded note the scenario's note assertions do not describe
    (DEMOCI-01-011).

    Args:
        state: The running story's state.
        updates: The posts that follow the Vendor's answer, in order.
    """
    answered = state.kept(VENDORS_ANSWER)
    add_note_thread(
        state.client(VENDOR), state.case, updates, in_reply_to=answered
    )
    logger.info(
        "✓ Notes exchange complete (the joiners' notes added to the thread)"
    )


def the_embargo_ends_for(
    state: StoryState, *, check: str, watcher: str
) -> None:
    """*watcher*'s replica reads ``EM.EXITED``.

    Per DEMOMA-07-003(4) the Case Owner's ``notify-published`` is what ends
    the embargo, and each scenario reads the termination on the replica its
    own next step depends on, so the label and the watcher are the caller's.

    Args:
        state: The running story's state.
        check: This scenario's ``demo_check`` label.
        watcher: The cast name whose replica is read.
    """
    with demo_check(check):
        wait_for_case_em_terminated(
            client=state.client(watcher), case_id=state.case.id_
        )


def the_disclosure_reached_every_replica(
    state: StoryState, *, check: str, em_watchers: Sequence[str] = (REPORTER,)
) -> None:
    """The final publication milestone: EM.EXITED, VF and CS.VFdPxa.

    The last check of every scenario of this family, which differs only in
    whose replicas it reads ``EM.EXITED`` on: the Reporter's alone in the
    three whose owner published first, and every participant's in
    ``rvcv-handoff``, where the owner publishes last.

    Args:
        state: The running story's state.
        check: This scenario's ``demo_check`` label for the milestone.
        em_watchers: The cast names whose replicas must read ``EM.EXITED``.
    """
    with demo_check(check):
        for who in em_watchers:
            wait_for_case_em_terminated(
                client=state.client(who), case_id=state.case.id_
            )
        for who in (VENDOR, REPORTER):
            wait_for_participant_vf_state(
                client=state.client(who),
                case_id=state.case.id_,
                actor_id=state.actor_id(VENDOR),
                expected_states={CS_vf.VF},
            )
        verify_publicly_disclosed(
            receiver_client=state.client(VENDOR),
            reporter_client=state.client(REPORTER),
            case_id=state.case.id_,
            receiver_actor_id=state.actor_id(VENDOR),
        )


__all__ = [
    "CASE_REPLICA_TIMEOUT",
    "JOIN_TIMEOUT",
    "REPORTERS_QUESTION",
    "REPORTER_TELLS_THE_VENDOR",
    "THE_VENDORS_CASE",
    "THE_VENDOR_ANSWERS_THE_REPORTER",
    "VENDOR",
    "VENDOR2",
    "VENDOR2_LABEL",
    "VENDOR2_PART",
    "VENDORS_ANSWER",
    "VENDOR_LABEL",
    "VENDOR_PART",
    "VENDOR_TRIAGE_TIMEOUT",
    "both_vendors_report_the_fix_ready",
    "dump_vendor_ledgers",
    "open_vendor_cast",
    "required_participants_are_present",
    "the_disclosure_reached_every_replica",
    "the_embargo_ends_for",
    "the_fix_ready_reached_the_reporter",
    "the_joiners_add_their_notes",
    "the_reporter_asks_about_the_workaround",
    "the_reporter_tells_the_vendor",
    "vendor_open_cast",
    "vendor_seats",
]
