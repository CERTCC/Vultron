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
"""Play an assembled story inside the shared harness: :func:`run_story`.

The runner is the only place a step mark is made: it reports each choice the
story passes to the harness, with the deciding actor read off the cast, and
stops the story when a fragment or a mark depends on an earlier failure
(DEMOCI-11-019, :mod:`vultron.demo.helpers.story`).
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from vultron.demo.helpers.harness import ScenarioHarness, scenario_harness
from vultron.demo.helpers.story.assembly import Choose, Story
from vultron.demo.helpers.story.state import Fragment, StoryState
from vultron.demo.utils import demo_failures, demo_gate
from vultron.errors import DemoStoryError

logger = logging.getLogger(__name__)


def run_story(
    name: str,
    plot: Story,
    open_cast: Callable[[ScenarioHarness], StoryState],
) -> None:
    """Play *plot* as the scenario *name*, inside the shared harness.

    The harness resets the failure accumulator, always dumps the case ledgers
    and only then asserts success (DEMOMA-23-001).  Each choice the story
    passes is reported to it as a step mark, with the deciding actor read off
    the cast, and this is the only place a mark is made: no scenario or
    helper places one by hand (DEMOCI-11-019).

    Args:
        name: The scenario's registered name.
        plot: Its assembled story.
        open_cast: Builds the run's state — resets and seeds the containers
            and binds the cast's sessions to the harness.  It runs inside the
            harness, so a seeding failure is dumped and reported like any
            other.

    Raises:
        DemoFailureError: When the story completed with recorded failures.
        DemoScenarioStepError: When a choice is not the next step of the
            scenario's declared path, or its actor does not hold the branch
            point's role on a run that had not already failed
            (:func:`_mark_step`).
        DemoStoryError: When a fragment reads an artifact no earlier fragment
            produced on a run that had recorded no failure (:func:`_run_item`).
    """
    with scenario_harness(name) as harness:
        state = open_cast(harness)
        for item in plot.items:
            if isinstance(item, Choose):
                if not _mark_step(harness, state, item):
                    return
                continue
            if not _run_fragment(name, state, item):
                return


def _run_fragment(name: str, state: StoryState, item: Fragment) -> bool:
    """Run *item*; return whether the story may go on.

    A fragment reads what an earlier one made through an accessor that raises
    (:meth:`StoryState.kept` and its siblings), so a failed act shows up here
    as a :class:`DemoStoryError` in the fragment that depended on it.  A flat
    sequence of fragments gets from that what nesting gets from a
    ``demo_gate``: the steps that presuppose a failed act do not run
    (DEMOCI-01-007).

    A missing artifact is therefore treated exactly as an unmakeable step mark
    is (:func:`_mark_step`): on a run that has already recorded a failure it
    is that failure showing through, so it is recorded inside a ``demo_gate``
    and the story stops, leaving the first failure as the headline and the
    dependent fragments unrun.  On a run with nothing recorded the story is
    mis-assembled — a fragment placed before the one that makes what it reads
    — and that must not be reported as a soft failure the next regeneration
    could bless, so it is raised.

    Args:
        name: The scenario's name, for the log line.
        state: The story's state.
        item: The fragment to run.

    Returns:
        Whether the fragment ran, and so whether the story continues.

    Raises:
        DemoStoryError: When the fragment read a missing artifact on a run
            that had recorded no failure.
    """
    label = getattr(item, "__name__", repr(item))
    logger.debug("%s runs %s", name, label)
    stopped = False
    try:
        item(state)
    except DemoStoryError:
        if not demo_failures():
            raise
        stopped = True
        with demo_gate(f"{name} cannot run {label} after an earlier failure"):
            raise
    if stopped:
        logger.error(
            "%s stopped before %s, which needs what an earlier failed step "
            "would have made; the first failure stays the headline",
            name,
            label,
        )
        return False
    return True


def _mark_step(
    harness: ScenarioHarness, state: StoryState, item: Choose
) -> bool:
    """Record *item*'s step mark; return whether the story may go on.

    A step's role is read from the canonical case (DEMOCI-11-047), so a
    decision cannot be checked when the act that granted the role failed: an
    invitee holds the role of an Invite that was never sent no more than it
    holds any other.  A mark is therefore a dependent step like any other, and
    on a run that has already recorded a failure it is reported the way a
    dependent step is — inside a ``demo_gate``, recorded and never raised, and
    the story stops there so the first failure stays the headline
    (DEMOCI-01-003, EDF-06-005).

    On a run with nothing recorded, the mark raises: then the step really is
    mis-declared, and a declaration defect must not be reported as a soft
    failure the next regeneration could bless.

    Args:
        harness: The run's harness, which checks and records the mark.
        state: The story's state, which names the deciding actor.
        item: The choice being passed.

    Returns:
        Whether the mark was made, and so whether the story continues.
    """
    step = f"{item.branch_point}:{item.choice}"
    if not demo_failures():
        harness.reach_step(
            item.branch_point, item.choice, by=state.actor_id(item.by)
        )
        return True
    marked = False
    with demo_gate(
        f"{harness.demo_name} reaches {step} after an earlier failure"
    ):
        harness.reach_step(
            item.branch_point, item.choice, by=state.actor_id(item.by)
        )
        marked = True
    if not marked:
        logger.error(
            "%s cannot reach %s after an earlier failure; stopping the story "
            "so the first failure stays the headline",
            harness.demo_name,
            step,
        )
    return marked


__all__ = ["run_story"]
