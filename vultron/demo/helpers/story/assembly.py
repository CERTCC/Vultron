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
"""Assemble a story: fragments, props, choices and named prefixes.

:data:`Fragment`, :class:`StoryProp`, :func:`choose` and :func:`story`, the
parts a scenario writes its story from (:mod:`vultron.demo.helpers.story`).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from vultron.demo.scenario.branch_points import validate_path
from vultron.demo.scenario.tree import PathStep
from vultron.errors import DemoStoryError

if TYPE_CHECKING:
    from vultron.demo.helpers.story.state import StoryState


#: One step of a story: a callable run against the story's state.  Named
#: rather than inlined because it is also what a named prefix is made of, and
#: what a scenario reads top to bottom.
Fragment = Callable[["StoryState"], None]


@dataclass(frozen=True)
class StoryProp[PropT]:
    """One artifact a story carries from the fragment that makes it onward.

    :class:`StoryState` names the artifacts *every* story has — the case, the
    report, the Offer, the delivered Invites.  A family's own artifacts are
    declared as props beside the fragments that pass them: the embargo in
    force in the Reporter → Coordinator → Vendor embargo pair, the note a
    later poster replies to.  A prop rather than a field on the state, and
    rather than a per-family subclass, because a fragment is typed
    ``Callable[[StoryState], None]`` and a ``Callable[[Subclass], None]`` is
    not assignable to it (``notes/demo-scenario-tree.md`` § "Composition").

    Declare one at module level, where the fragments that share it can see it::

        EMBARGO_IN_FORCE: StoryProp[str] = StoryProp("embargo in force", str)

    Attributes:
        name: What the artifact is, in the words the error message uses.
        type_: What :meth:`StoryState.keep` accepts and
            :meth:`StoryState.kept` returns.  Checked on the way in, so a
            reader never has to.
    """

    name: str
    type_: type[PropT]


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
        # Validated here rather than when the registry merges the tree, so an
        # unknown branch point or choice fails where it is written.
        validate_path(((self.branch_point, self.choice),))
        if not isinstance(self.by, str) or not self.by:
            raise DemoStoryError(
                f"choice {self.branch_point}:{self.choice} names "
                f"{self.by!r} as the actor that decides it; the name is the "
                "one its scenario's ROLES seats the actor under, and the "
                "harness reads that actor's role from the canonical case "
                "(DEMOCI-11-013, DEMOCI-11-047)."
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
