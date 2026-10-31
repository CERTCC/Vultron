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
"""Story fragments of the embargo pair, ``rcv-embargo`` and ``rcvv-embargo``.

Both continue :data:`~vultron.demo.helpers.coordinated_story\
.VENDOR_JOINS_THE_CASE` by taking the Reporter's ``propose-embargo`` choice,
and both open it the same way: case creation activated the default embargo
(EP-04-001), so the Reporter's proposal **revises** it — the CASE_MANAGER
relays it, the Vendor consents, and the Coordinator, as owner, activates the
revision (EP-09, ``ACTIVE → REVISE → ACTIVE``).  That stretch is
:data:`REPORTER_PROPOSES_EMBARGO`, the prefix the pair parts from at the
Vendor's next decision: report the fix ready (``rcv-embargo``) or propose a
further revision (``rcvv-embargo``).

Each fragment asserts the CASE_MANAGER's canonical ``em_state`` after its act
(DEMOMA-20-008, DEMOMA-21-009).  The assertions read the CASE_MANAGER's
canonical case, or wait for the fan-out; none reads a triggering actor's
replica straight after its trigger (DEMOMA-20-011, DEMOMA-21-010).

The embargo a step put in force is carried to the steps that end or revise it
as a :class:`~vultron.demo.helpers.story.StoryProp`
(:data:`PROPOSED_EMBARGO`): ``EM.ACTIVE`` alone cannot tell a revision from
the embargo it revised, and a step whose revision never took effect keeps
nothing, so the steps that presuppose it stop rather than piling secondary
failures on the first (DEMOCI-01-007).
"""

from __future__ import annotations

import logging

from vultron.core.states.em import EM
from vultron.demo.exchange.embargo_lifecycle import (
    COMMIT_TIMEOUT_SECONDS,
    demo_propose_and_activate_embargo,
    demo_terminate_embargo,
)
from vultron.demo.helpers.coordinated_story import (
    COORDINATOR,
    REPORTER,
    VENDOR,
    VENDOR_JOINS_THE_CASE,
)
from vultron.demo.helpers.notes import reporter_asks_vendor_answers
from vultron.demo.helpers.polling import (
    case_manager_store,
    wait_for_case_em_state,
    wait_for_case_em_terminated,
)
from vultron.demo.helpers.story import (
    StoryProp,
    StoryState,
    choose,
    story,
)
from vultron.demo.utils import demo_check, demo_gate
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

logger = logging.getLogger(__name__)

#: The embargo the Reporter's proposal put in force, for the steps that end or
#: revise it.  Absent when the revision never took effect, which stops the
#: story there (:func:`~vultron.demo.helpers.story.run_story`).
PROPOSED_EMBARGO: StoryProp[str] = StoryProp(
    "embargo the Reporter's proposal put in force", str
)


def canonical_case(state: StoryState) -> as_VulnerabilityCase:
    """The case as the CASE_MANAGER holds it.

    Read on the dedicated case-actor container, where the CaseActor's own
    store lives (DEMOMA-06-004), falling back to the Coordinator's session
    when the CaseActor shares a container
    (:func:`~vultron.demo.helpers.polling.case_manager_store`).
    """
    client, dl_actor_id = case_manager_store(
        state.client(COORDINATOR), state.case.id_, state.case_actor_client
    )
    return as_VulnerabilityCase.model_validate(
        client.get(client.dl_path(state.case.id_, actor_id=dl_actor_id))
    )


def assert_canonical_em_state(
    state: StoryState,
    expected: EM,
    phase: str,
    active_embargo_id: str | None = None,
) -> None:
    """Assert the CASE_MANAGER's canonical case is at *expected*.

    Args:
        state: The running story's state.
        expected: The EM state the canonical case must hold.
        phase: The phase name, for the check label.
        active_embargo_id: When given, the embargo that must be the active
            one; ``EM.ACTIVE`` alone cannot tell a revision from the embargo
            it revised.
    """
    client, dl_actor_id = case_manager_store(
        state.client(COORDINATOR), state.case.id_, state.case_actor_client
    )
    with demo_check(
        f"{phase}: CASE_MANAGER's canonical case has {expected.name}"
    ):
        wait_for_case_em_state(
            client,
            state.case.id_,
            expected,
            COMMIT_TIMEOUT_SECONDS,
            dl_actor_id=dl_actor_id,
            active_embargo_id=active_embargo_id,
        )


def confirm_embargo_revised(
    state: StoryState,
    prior_embargo_id: str | None,
    phase: str,
    gate_label: str,
) -> str | None:
    """Gate on a revision, not *prior_embargo_id*, being the embargo in force.

    A gate, not a check: later steps end or revise the embargo this one put in
    force, so without a revision they would only add secondary failures
    (DEMOCI-01-007).

    Returns:
        The id of the embargo now in force, or ``None`` when no revision took
        effect (the failure is recorded).
    """
    revised_embargo_id: str | None = None
    with demo_gate(gate_label):
        in_force = canonical_case(state).active_embargo_id
        if in_force is None or in_force == prior_embargo_id:
            raise AssertionError(
                f"active embargo {in_force!r} is not a revision of"
                f" {prior_embargo_id!r}"
            )
        revised_embargo_id = in_force
        assert_canonical_em_state(
            state,
            EM.ACTIVE,
            phase,
            active_embargo_id=revised_embargo_id,
        )
    return revised_embargo_id


def replicas_see_the_embargo_ended(
    state: StoryState, watchers: tuple[str, ...]
) -> None:
    """Check each of *watchers*' replicas learns the embargo ended.

    Replicas learn it from the ledger fan-out after the CASE_MANAGER's commit,
    so these are checks of the effect, not gates for what follows
    (EDF-06-006).
    """
    for name in watchers:
        with demo_check(f"{name}'s replica has EM.EXITED"):
            wait_for_case_em_terminated(
                client=state.client(name),
                case_id=state.case.id_,
                timeout_seconds=COMMIT_TIMEOUT_SECONDS,
            )


# ---------------------------------------------------------------------------
# The shared embargo opening
# ---------------------------------------------------------------------------


def the_default_embargo_is_in_force(state: StoryState) -> None:
    """Case creation activated the default embargo, before anyone proposed.

    EP-04-001: the case is at ``EM.ACTIVE`` as soon as it exists, which is why
    the Reporter's proposal below is a revision rather than a first embargo.
    Placed after the Reporter's decision rather than before it, so the opening
    this pair shares with its wider siblings ends exactly at the branch point
    they part from (DEMOCI-11-018); the assertion reads no ledger and writes
    nothing, so where it sits does not move a byte.
    """
    assert_canonical_em_state(state, EM.ACTIVE, "report_submission")


def reporter_revises_the_default_embargo(state: StoryState) -> None:
    """The Reporter revises the default embargo; the Coordinator activates it.

    The CASE_MANAGER relays the proposal, the Vendor consents, and the
    Coordinator, as owner, activates the revision (EP-09).  The embargo now in
    force is kept as :data:`PROPOSED_EMBARGO`; a revision that never took
    effect keeps nothing and the failure is recorded, so the fragments that
    end or revise it stop there.
    """
    default_embargo_id = canonical_case(state).active_embargo_id

    demo_propose_and_activate_embargo(
        state.actor(REPORTER),
        state.actor(COORDINATOR),
        state.actor(VENDOR),
        state.case,
        case_manager_client=state.case_actor_client,
    )

    revised = confirm_embargo_revised(
        state,
        default_embargo_id,
        "embargo_proposal",
        "The revision, not the default embargo, is now in force",
    )
    if revised is not None:
        state.keep(PROPOSED_EMBARGO, revised)


def reporter_asks_about_the_embargo(state: StoryState) -> None:
    """The Reporter asks whether the revised embargo leaves time for a fix.

    The Reporter proposed rather than asked first — its choice at
    ``reporter-after-join`` — so this thread follows the proposal and comes
    before the Vendor's own next decision.  It puts ``add_note_to_case`` in
    the case ledger (DEMOMA-16-001).
    """
    reporter_asks_vendor_answers(
        state.actor(REPORTER),
        state.actor(VENDOR),
        state.client(COORDINATOR),
        state.case,
    )


#: The opening both embargo scenarios share: the Vendor joins, the Reporter
#: chooses to propose, the default embargo is confirmed active, and the
#: Reporter revises it and asks about it.  It stops where the Vendor's
#: decision falls — report the fix ready, or propose a further revision.
REPORTER_PROPOSES_EMBARGO = story(
    VENDOR_JOINS_THE_CASE,
    choose("reporter-after-join", "propose-embargo", by=REPORTER),
    the_default_embargo_is_in_force,
    reporter_revises_the_default_embargo,
    reporter_asks_about_the_embargo,
)


# ---------------------------------------------------------------------------
# Continuations
# ---------------------------------------------------------------------------


def embargo_survives_the_fix(state: StoryState) -> None:
    """The fix being ready leaves the embargo alone (``EM.ACTIVE``)."""
    assert_canonical_em_state(state, EM.ACTIVE, "fix_lifecycle")


def coordinator_ends_the_embargo(state: StoryState) -> None:
    """The Coordinator ends the embargo deliberately, before publication.

    Reads :data:`PROPOSED_EMBARGO` first: there is nothing to end when the
    revision never took effect, and the story stops here rather than
    terminating, publishing and closing against the wrong embargo
    (DEMOCI-01-007).
    """
    in_force = state.kept(PROPOSED_EMBARGO)
    logger.info("Ending the embargo in force: %s", in_force)

    # The helper asserts EM.EXITED on the CASE_MANAGER's canonical case and no
    # participant's consent (DEMOMA-20-011, DEMOMA-20-012).
    demo_terminate_embargo(
        state.actor(COORDINATOR),
        state.case,
        case_manager_client=state.case_actor_client,
    )
    assert_canonical_em_state(state, EM.EXITED, "embargo_termination")
    replicas_see_the_embargo_ended(state, (REPORTER, VENDOR))


def embargo_stays_ended_through_publication(state: StoryState) -> None:
    """Publication leaves the ended embargo ended (``EM.EXITED``)."""
    assert_canonical_em_state(state, EM.EXITED, "publication")


def embargo_stays_ended_through_closure(state: StoryState) -> None:
    """Closing the case leaves the ended embargo ended (``EM.EXITED``)."""
    assert_canonical_em_state(state, EM.EXITED, "case_closure")


__all__ = [
    "PROPOSED_EMBARGO",
    "REPORTER_PROPOSES_EMBARGO",
    "assert_canonical_em_state",
    "canonical_case",
    "confirm_embargo_revised",
    "coordinator_ends_the_embargo",
    "embargo_stays_ended_through_closure",
    "embargo_stays_ended_through_publication",
    "embargo_survives_the_fix",
    "replicas_see_the_embargo_ended",
    "reporter_asks_about_the_embargo",
    "reporter_revises_the_default_embargo",
    "the_default_embargo_is_in_force",
]
