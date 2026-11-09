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

Sibling scenarios share an opening, and a second copy of it would be free to
drift (DEMOMA-17-001).  A story is that opening written **once**, with one
continuation per choice (DEMOCI-11-019, ADR-0098):

* a **fragment** is one step of a story, a callable taking the run's
  :class:`StoryState`.  It names no container of its own: the cast and the
  tree-wide seed are fixed (DEMOCI-11-020, DEMOCI-11-025), so a fragment is
  handed the cast's sessions and reads the case off the state;
* :func:`choose` is one declared decision — a branch point, the choice this
  story takes there, and the cast member that decides;
* a **named prefix** is a :class:`Story` several scenarios start with.
  :func:`story` concatenates prefixes, fragments and choices into one
  sequence, so the whole story reads top to bottom in one file;
* a **prop** (:class:`StoryProp`) is an artifact one family passes between its
  own fragments — the embargo in force, the note a later poster replies to —
  kept on the state rather than on a per-family subclass of it, which a
  fragment's type forbids.

The path is then read off the choices (:attr:`Story.path`), never typed a
second time beside the story: ``@scenario(story=STORY)`` is the only way a
scenario places itself on the tree, and the registry takes no path parameter
to type a second copy into (DEMOCI-11-019, DEMOCI-11-024).  :func:`run_story`
plays the sequence inside
:func:`~vultron.demo.helpers.harness.scenario_harness` and records each step
mark as it passes a choice, with the harness's deciding-role check, so the
runner is the sole source of a scenario's marks and nothing places one by hand
(DEMOCI-11-019).

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

The package is split by concern (CS-18-005): :mod:`.assembly` holds the
parts a story is written from, :mod:`.state` the state a running story
carries, and :mod:`.runner` the player.  Every public name is re-exported
here (CS-18-003).
"""

from vultron.demo.helpers.story.assembly import (
    Choose,
    Fragment,
    Story,
    StoryProp,
    choose,
    fragment_name,
    story,
)
from vultron.demo.helpers.story.runner import run_story
from vultron.demo.helpers.story.state import (
    StoryState,
    UnseatedContainer,
)

__all__ = [
    "Choose",
    "Fragment",
    "Story",
    "StoryProp",
    "StoryState",
    "UnseatedContainer",
    "choose",
    "fragment_name",
    "run_story",
    "story",
]
