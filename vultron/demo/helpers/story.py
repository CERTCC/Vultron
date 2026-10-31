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
"""Write a branching demo story once: fragments, named prefixes and choices.

Sibling scenarios used to be copies: ``rcv`` and ``rcv-reject`` told the same
opening — the Reporter tells the Coordinator, the Coordinator invites the
Vendor — in two hand-placed copies, free to drift (DEMOMA-17-001).  A story is
that opening written **once**, with one continuation per choice
(DEMOCI-11-019, ADR-0098):

* a **fragment** is one step of a story, a callable taking the run's
  :class:`StoryState`.  It names no container of its own: the cast and the
  tree-wide seed are fixed (DEMOCI-11-020, DEMOCI-11-025), so a fragment is
  handed the cast's sessions and reads the case off the state;
* :func:`choose` is one declared decision — a branch point, the choice this
  story takes there, and the cast member that decides;
* a **named prefix** is a :class:`Story` several scenarios start with.
  :func:`story` concatenates prefixes, fragments and choices into one
  sequence, so the whole story reads top to bottom in one file.

The path is then read off the choices (:attr:`Story.path`), never typed a
second time beside the story: ``@scenario(story=STORY)`` instead of
``@scenario(path=...)``, and a scenario that declares both fails discovery
(DEMOCI-11-024).  :func:`run_story` plays the sequence inside
:func:`~vultron.demo.helpers.harness.scenario_harness` and records each step
mark as it passes a choice, with the harness's deciding-role check, so a
composed scenario places no ``reach_step`` by hand (DEMOCI-11-013).

Usage from a scenario module::

    STORY = story(
        COORDINATOR_INVITES_VENDOR,                 # the named prefix
        choose("vendor-join", "accept", by=VENDOR),
        vendor_accepts_and_joins,
        ...
    )

    @scenario(name="rcv", ..., story=STORY)
    def main(...) -> None:
        ...

Design: ``notes/demo-scenario-tree.md`` § "Composition".
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from vultron.demo.actor_session import ActorSession
from vultron.demo.helpers.harness import ScenarioHarness, scenario_harness
from vultron.demo.scenario.branch_points import validate_path
from vultron.demo.scenario.tree import PathStep
from vultron.demo.utils import DataLayerClient, demo_failures, demo_gate
from vultron.errors import DemoStoryError
from vultron.wire.as2.vocab.base.objects.activities.transitive import as_Offer
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

logger = logging.getLogger(__name__)

#: One step of a story: a callable run against the story's state.  Named
#: rather than inlined because it is also what a named prefix is made of, and
#: what a scenario reads top to bottom.
Fragment = Callable[["StoryState"], None]


@dataclass(frozen=True, slots=True)
class Choose:
    """One declared decision of a story (DEMOCI-11-013, DEMOCI-11-019).

    Frozen: the item is read by the registry at import time to derive the
    scenario's path and again by :func:`run_story` to record the step mark, and
    the two must be the same fact.
    """

    #: The branch point decided here; an entry of
    #: :data:`~vultron.demo.scenario.branch_points.BRANCH_POINTS`.
    branch_point: str
    #: The choice this story takes there.
    choice: str
    #: The cast member that decides, by the name its scenario seats it under
    #: (:class:`~vultron.demo.helpers.actor_roles.ActorRole`), not its actor
    #: id: a story is written before the run that draws the ids.
    by: str

    def __post_init__(self) -> None:
        # The same validation the `@scenario(path=...)` form gets, so an
        # unknown branch point or choice fails where it is written rather than
        # when the tree is merged.
        validate_path(((self.branch_point, self.choice),))
        if not isinstance(self.by, str) or not self.by:
            raise DemoStoryError(
                f"choice {self.branch_point}:{self.choice} names "
                f"{self.by!r} as the actor that decides it; the name is the "
                "one its scenario's ROLES seats the actor under, and the "
                "harness reads that actor's role from the canonical case "
                "(DEMOCI-11-013)."
            )

    @property
    def step(self) -> PathStep:
        """This choice as one step of a scenario's path."""
        return (self.branch_point, self.choice)


def choose(branch_point: str, choice: str, *, by: str) -> Choose:
    """Declare that the story decides *branch_point* by taking *choice*.

    Args:
        branch_point: The branch point decided here.
        choice: The choice this story takes.
        by: The deciding cast member's name in this scenario.

    Returns:
        The story item. ``by`` is keyword-only: the first two arguments are a
        pair read from the branch-point table, and a third positional string
        beside them would be trivially swappable with either.

    Raises:
        DemoScenarioRegistryError: When the branch point or the choice is not
            in the branch-point table.
        DemoStoryError: When ``by`` is not a cast member's name.
    """
    return Choose(branch_point=branch_point, choice=choice, by=by)


@dataclass(frozen=True, slots=True)
class Story:
    """A scenario's story, or a named prefix several scenarios start with.

    Build one with :func:`story`, which is where prefixes are concatenated and
    the items are checked.
    """

    #: The story's items in order: fragments and declared choices.
    items: tuple[Choose | Fragment, ...]

    @property
    def path(self) -> tuple[PathStep, ...]:
        """The path this story walks: its choices, in order (DEMOCI-11-019).

        This is what ``@scenario(story=...)`` registers as the scenario's
        path, so the tree, the generated index and the step marks in the
        recordings all come from the code that runs.
        """
        return tuple(
            item.step for item in self.items if isinstance(item, Choose)
        )


def story(*parts: Story | Choose | Fragment) -> Story:
    """Assemble one story from named prefixes, choices and fragments.

    A :class:`Story` part is spliced in rather than nested, so a scenario that
    starts with a named prefix has one flat sequence: the path is the choices
    of the whole, and :func:`run_story` plays the items in the order written.

    Args:
        parts: Named prefixes, :func:`choose` items and fragments, in order.

    Returns:
        The assembled story.

    Raises:
        DemoStoryError: When no part is given, or a part is neither a story,
            a choice nor a callable fragment.
    """
    items: list[Choose | Fragment] = []
    for part in parts:
        if isinstance(part, Story):
            items.extend(part.items)
        elif isinstance(part, Choose) or callable(part):
            items.append(part)
        else:
            raise DemoStoryError(
                f"story item {part!r} is neither a named prefix, a "
                "choose(...) nor a fragment taking the story's state; a "
                "story is a flat sequence of those three."
            )
    if not items:
        raise DemoStoryError(
            "a story has at least one item; an empty one would register a "
            "scenario with no path and no steps to run."
        )
    return Story(items=tuple(items))


@dataclass
class StoryState:
    """What every fragment of one story run shares.

    A fragment takes the cast, not a container: each actor is an
    :class:`~vultron.demo.actor_session.ActorSession` bound to the container
    the fixed cast seats it in (DEMOCI-11-020), looked up by the name its
    scenario's ``ROLES`` uses.  The artifacts a story produces — the report,
    the Offer, the case, each delivered Invite — are recorded here as the
    fragments that produce them run, and read back through accessors that
    raise rather than hand out a ``None`` a later fragment would post.
    """

    #: Each actor the scenario seats, by its ``ActorRole`` name.
    cast: Mapping[str, ActorSession]
    #: Client for the dedicated case-actor container, which holds the
    #: canonical case and ledger (DEMOMA-06-005).
    case_actor_client: DataLayerClient
    #: The harness of this run: where the step marks and the ledger dump go.
    harness: ScenarioHarness
    #: This scenario's ledger dump, armed by :meth:`open_case` as soon as
    #: there is a case to dump (DEMOMA-23-003).
    dump: Callable[[StoryState], None]
    _case: as_VulnerabilityCase | None = field(
        default=None, init=False, repr=False
    )
    _report: as_VulnerabilityReport | None = field(
        default=None, init=False, repr=False
    )
    _offer: as_Offer | None = field(default=None, init=False, repr=False)
    _invites: dict[str, str] = field(
        default_factory=dict, init=False, repr=False
    )

    def actor(self, name: str) -> ActorSession:
        """The session of the cast member this scenario calls *name*.

        Raises:
            DemoStoryError: When the scenario's cast seats no such actor —
                a fragment and the scenario's ``ROLES`` have drifted apart.
        """
        session = self.cast.get(name)
        if session is None:
            raise DemoStoryError(
                f"the story names the actor {name!r}, which this scenario's "
                f"cast does not seat; it seats {sorted(self.cast)}."
            )
        return session

    def client(self, name: str) -> DataLayerClient:
        """The container client of the cast member called *name*."""
        return self.actor(name).client

    def actor_id(self, name: str) -> str:
        """The actor id of the cast member called *name*.

        Raises:
            DemoStoryError: When the cast seats no such actor, or its actor
                carries no id — a seeded actor always does, so an id-less one
                means the cast was built from a stand-in.
        """
        actor_id = self.actor(name).actor.id_
        if not actor_id:
            raise DemoStoryError(
                f"the cast member {name!r} has no actor id, so no step it "
                "decides can be checked against its role (DEMOCI-11-013)."
            )
        return actor_id

    @property
    def case(self) -> as_VulnerabilityCase:
        """The case this story opened.

        Raises:
            DemoStoryError: Before :meth:`open_case` — a fragment that reads
                the case must run after the one that opens it.
        """
        if self._case is None:
            raise DemoStoryError(
                "the story has not opened a case yet; a fragment that reads "
                "the case runs after the one that opens it."
            )
        return self._case

    @property
    def report(self) -> as_VulnerabilityReport:
        """The report this story's Reporter submitted.

        Raises:
            DemoStoryError: Before :meth:`open_case`.
        """
        if self._report is None:
            raise DemoStoryError(
                "the story has no report yet; the Reporter submits it in the "
                "fragment that opens the case."
            )
        return self._report

    @property
    def offer(self) -> as_Offer:
        """The Offer the submitted report arrived as.

        Raises:
            DemoStoryError: Before :meth:`open_case`.
        """
        if self._offer is None:
            raise DemoStoryError(
                "the story has no report Offer yet; the Reporter submits it "
                "in the fragment that opens the case."
            )
        return self._offer

    def open_case(
        self,
        *,
        case: as_VulnerabilityCase,
        report: as_VulnerabilityReport,
        offer: as_Offer,
    ) -> None:
        """Record the opened case, arm the ledger dump and follow the ledger.

        Called by the fragment that opens the case, which is the first point
        at which there is anything to dump: every later fragment can then fail
        without costing the ledgers (DEMOMA-23-003, ISSUE-2239).

        Args:
            case: The case as the Case Owner's container stores it.
            report: The report the Reporter submitted.
            offer: The Offer it arrived as.
        """
        self._case = case
        self._report = report
        self._offer = offer
        self.harness.dump_with(lambda: self.dump(self))
        self.harness.follow_ledger(self.case_actor_client, case.id_)

    def invited(self, name: str, invite_id: str | None) -> None:
        """Record the Invite delivered to the cast member called *name*.

        ``None`` records that none was — the invite trigger or the delivery
        wait failed and recorded it — which is what
        :meth:`delivered_invite` hands the answer fragment.

        Raises:
            DemoStoryError: When the cast seats no actor of that name.
        """
        self.actor(name)
        if invite_id is None:
            self._invites.pop(name, None)
            return
        self._invites[name] = invite_id

    def delivered_invite(self, name: str) -> str | None:
        """The Invite the cast member called *name* holds, or ``None``.

        The one accessor here that may hand back ``None``, because the answer
        is the step that owns the skip: a demo helper records a failure and
        skips its dependents rather than raising
        (:func:`~vultron.demo.helpers.invite_chain.answer_case_invite` refuses
        a ``None`` inside its own gate, EDF-06-005).  Everything else a story
        produces is read through an accessor that raises.

        Raises:
            DemoStoryError: When the cast seats no actor of that name.
        """
        self.actor(name)
        return self._invites.get(name)


def run_story(
    name: str,
    plot: Story,
    open_cast: Callable[[ScenarioHarness], StoryState],
) -> None:
    """Play *plot* as the scenario *name*, inside the shared harness.

    The harness resets the failure accumulator, always dumps the case ledgers
    and only then asserts success (DEMOMA-23-001).  Each choice the story
    passes is reported to it as a step mark, with the deciding actor read off
    the cast, so the role check runs exactly as it does for a hand-placed
    ``reach_step`` and a composed scenario places none (DEMOCI-11-013).

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
            produced.
    """
    with scenario_harness(name) as harness:
        state = open_cast(harness)
        for item in plot.items:
            if isinstance(item, Choose):
                if not _mark_step(harness, state, item):
                    return
                continue
            logger.debug("%s runs %s", name, getattr(item, "__name__", item))
            item(state)


def _mark_step(
    harness: ScenarioHarness, state: StoryState, item: Choose
) -> bool:
    """Record *item*'s step mark; return whether the story may go on.

    A step's role is read from the canonical case (DEMOCI-11-013), so a
    decision cannot be checked when the act that granted the role failed: an
    invitee holds the role of an Invite that was never sent no more than it
    holds any other.  A mark is therefore a dependent step like any other, and
    on a run that has already recorded a failure it is reported the way a
    dependent step is — inside a ``demo_gate``, recorded and never raised, and
    the story stops there so the first failure stays the headline
    (DEMOCI-01-003, EDF-06-005).  The whole chain nested the same way before
    the stories were composed: the invitee's mark sat inside the Invite's
    delivery gate, so a failed invite skipped it with the answer.

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


__all__ = [
    "Choose",
    "Fragment",
    "Story",
    "StoryState",
    "choose",
    "run_story",
    "story",
]
