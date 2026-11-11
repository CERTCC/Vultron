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
"""A cast member asks who else belongs in the case (BT-24-007, ADR-0186).

A scenario declares its candidate table by cast name (:class:`Candidate`).
:func:`ask_who_else_belongs` resolves each row to the actor the story seats
under that name, builds the
:class:`~vultron.demo.static_participant_suggestion.StaticParticipantSuggester`
from the rows, and asks it through the core service
(:func:`~vultron.core.services.participant_suggestion.suggest_participants_for_case_id`),
so the answer is projected from the asker's own replica of the case exactly
as a deployment's suggester would see it (BT-24-008).

**Where the adapter runs.**  In the demo runner, not in the asker's
container: the runner reads the asker's replica through its DataLayer
inspection routes, copies it into a private in-memory store
(:func:`replica_copy`), and asks the service about that store.  It plays the
part an operator-side Sentinel plays for its host actor: it decides who to
suggest, then calls the host actor's ``suggest-actor-to-case`` trigger
(``notes/coordination-agents.md`` § "The Sentinel Pattern Is Call-In, Not a
Shape").  No actor container is configured with a table, so the in-process
harness and the Docker demo ask the same adapter in the same process.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass

from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    dispose_actor_engines,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.participant_suggestion import ParticipantSuggestion
from vultron.core.models.report import VulnerabilityReport
from vultron.core.services.participant_suggestion import (
    suggest_participants_for_case_id,
)
from vultron.demo.helpers.owner_decision_story.parts import Part
from vultron.demo.helpers.seeding.actors import dl_key
from vultron.demo.helpers.story import StoryState
from vultron.demo.static_participant_suggestion import (
    StaticParticipantSuggester,
)
from vultron.demo.utils import DataLayerClient
from vultron.enums.roles import CVDRole
from vultron.errors import DemoStoryError

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Candidate:
    """One row of a scenario's candidate table.

    Named by cast member, because a scenario's actor ids are known only once
    the run seats its cast.  An actor suggested in two roles is two rows: a
    suggestion carries one role (BT-24-004).

    Attributes:
        part: The cast member suggested.  It must be seated before the ask,
            since the suggestion names it by actor id.
        role: The role it is suggested in.
        rationale: Why the suggester names it.
    """

    part: Part
    role: CVDRole
    rationale: str


@dataclass(frozen=True, slots=True)
class SuggestedActor:
    """One actor the suggester named, with every role it was named in.

    Attributes:
        part: The cast member the answer's actor id is seated as.
        actor_id: The actor id the answer named.
        roles: The roles the answer suggested it in, in answer order.
    """

    part: Part
    actor_id: str
    roles: tuple[CVDRole, ...]


@contextmanager
def replica_copy(
    client: DataLayerClient, case_id: str
) -> Iterator[SqliteDataLayer]:
    """A private in-memory copy of *client*'s replica of *case_id*.

    Copies the case, and each participant and report it references, from
    the store *client* inspects into a fresh store under the same actor id,
    so the core service resolves the case's references there as it would
    in the actor's own store.  The copy is named uniquely and disposed on
    exit, so it never shares an engine with any actor's real store, the
    in-process harness's included.

    Raises:
        httpx.HTTPStatusError: The replica lacks the case or an object it
            references.
        ValueError: *client* names no actor.
    """
    if client.actor_id is None:
        raise ValueError(
            "replica_copy reads one actor's replica, so its client must "
            "name the actor (ADR-0073)"
        )
    actor_id = str(client.actor_id)
    db_url = (
        f"sqlite:///file:suggest-{uuid.uuid4().hex}"
        "?mode=memory&cache=shared&uri=true"
    )
    store = SqliteDataLayer(db_url, actor_id=actor_id)
    try:
        case = VulnerabilityCase.model_validate(
            client.get(client.dl_path(dl_key(case_id)))
        )
        store.save(case)
        for kind, refs in (
            (CaseParticipant, case.case_participants),
            (VulnerabilityReport, case.vulnerability_reports),
        ):
            for ref in refs:
                record = (
                    kind.model_validate(
                        client.get(client.dl_path(dl_key(ref)))
                    )
                    if isinstance(ref, str)
                    else ref
                )
                store.save(record)
        yield store
    finally:
        dispose_actor_engines(db_url, actor_id)


def _resolved_table(
    state: StoryState, table: Sequence[Candidate]
) -> tuple[ParticipantSuggestion, ...]:
    """*table*'s rows, each named by its cast member's actor id."""
    return tuple(
        ParticipantSuggestion(
            actor_id=state.actor_id(row.part.name),
            role=row.role,
            rationale=row.rationale,
        )
        for row in table
    )


def _grouped(
    state: StoryState,
    table: Sequence[Candidate],
    answer: Sequence[ParticipantSuggestion],
) -> tuple[SuggestedActor, ...]:
    """*answer* grouped by actor, each actor mapped back to its cast member.

    Raises:
        DemoStoryError: The answer names an actor no row of *table* seats.
    """
    parts = {state.actor_id(row.part.name): row.part for row in table}
    roles: dict[str, list[CVDRole]] = {}
    for suggestion in answer:
        if suggestion.actor_id not in parts:
            raise DemoStoryError(
                f"the participant suggester named {suggestion.actor_id!r}, "
                "which no row of the scenario's candidate table seats"
            )
        named = roles.setdefault(suggestion.actor_id, [])
        if suggestion.role not in named:
            named.append(suggestion.role)
    return tuple(
        SuggestedActor(parts[actor_id], actor_id, tuple(named))
        for actor_id, named in roles.items()
    )


def ask_who_else_belongs(
    state: StoryState, asker: Part, table: Sequence[Candidate]
) -> tuple[SuggestedActor, ...]:
    """Ask *asker*'s participant suggester who else belongs in the case.

    The suggester is a
    :class:`~vultron.demo.static_participant_suggestion.StaticParticipantSuggester`
    over *table* (BT-24-007), asked through the core service about *asker*'s
    replica of the story's case (BT-24-008), so it never sees the case
    itself (BT-24-002).  An empty table, or one whose every actor is in the
    case already, answers with no one.

    Returns:
        Each actor the answer named, once, in answer order, with every role
        it was named in.

    Raises:
        DemoStoryError: The answer names an actor *table* does not seat.
        httpx.HTTPStatusError: *asker*'s replica lacks the case or an object
            it references.
    """
    suggester = StaticParticipantSuggester(_resolved_table(state, table))
    case_id = state.case.id_
    with replica_copy(state.client(asker.name), case_id) as store:
        answer = suggest_participants_for_case_id(case_id, suggester, store)
    suggested = _grouped(state, table, answer)
    logger.info(
        "%s's participant suggester named %s",
        asker.label,
        [f"{s.part.label} as {[r.value for r in s.roles]}" for s in suggested]
        or "no one",
    )
    return suggested


__all__ = [
    "Candidate",
    "SuggestedActor",
    "ask_who_else_belongs",
    "replica_copy",
]
