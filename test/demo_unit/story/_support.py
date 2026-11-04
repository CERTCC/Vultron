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

"""Stand-in fragments, sessions and states the story tests share."""

from __future__ import annotations

from collections.abc import Callable
from unittest.mock import MagicMock

from vultron.demo.actor_session import ActorSession
from vultron.demo.helpers.story import (
    Story,
    StoryProp,
    StoryState,
    UnseatedContainer,
    choose,
    story,
)
from vultron.demo.utils import demo_step

#: ``rv``'s path, as choices of a story.  Reused as the fixture story so the
#: fixture registry it is spliced into stays one well-formed tree.
RV_CHOICES = (
    ("reporter-whom-to-tell", "vendor"),
    ("vendor-after-answer", "report-fix-ready"),
)


def recording_fragment(
    name: str, log: list[str], fails: bool = False
) -> Callable[[StoryState], None]:
    """A fragment that records that it ran, and optionally fails doing it.

    A failing fragment fails the way a demo fragment does: inside
    ``demo_step``, which records the failure and lets the story go on
    (DEMOCI-01-003).
    """

    def run(_state: StoryState) -> None:
        log.append(name)
        if fails:
            with demo_step(f"{name} fails"):
                raise AssertionError(f"{name} exploded")

    run.__name__ = name
    return run


def session_for(actor_id: str) -> ActorSession:
    """A session whose actor carries *actor_id* and nothing else."""
    actor = MagicMock()
    actor.id_ = actor_id
    return ActorSession(client=MagicMock(base_url="x"), actor=actor)


def stand_in_state(
    unseated: dict[str, UnseatedContainer] | None = None,
    **cast: ActorSession,
) -> StoryState:
    return StoryState(
        cast=cast,
        case_actor_client=MagicMock(),
        harness=MagicMock(),
        dump=lambda _state: None,
        unseated=unseated or {},
    )


#: A prop of the shape a family declares beside its own fragments.
KEPT_ID: StoryProp[str] = StoryProp("embargo in force", str)


def rv_story(log: list[str] | None = None) -> Story:
    """A composed fixture story walking ``rv``'s path."""
    entries = log if log is not None else []
    return story(
        choose("reporter-whom-to-tell", "vendor", by="reporter"),
        recording_fragment("submit", entries),
        choose("vendor-after-answer", "report-fix-ready", by="vendor"),
        recording_fragment("fix", entries),
    )
