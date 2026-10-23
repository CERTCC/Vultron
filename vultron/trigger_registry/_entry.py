"""The trigger registry's row type and its request-model index (ADR-0110)."""

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

import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from vultron.core.models.use_case_result import TriggerResult
from vultron.core.use_cases.triggers._base import SvcBTTriggerBase
from vultron.core.use_cases.triggers.requests import (
    TriggerRequest,
    result_type_of,
)
from vultron.errors import TriggerRegistryError

#: A verb is the final path segment of its route: lower-case kebab-case.
_VERB_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


class TriggerExposure(StrEnum):
    """Where a trigger verb is mounted (TRIG-08-002).

    ``GENERAL_PURPOSE`` — a legitimate external stimulus or an intentional
    actor decision a human operator or agentic client might initiate; mounted
    under ``/actors/{actor_id}/trigger/`` (TRIG-08-003).

    ``DEMO_ONLY`` — exists only so a demo script can puppeteer an actor
    through a step its own BT would take autonomously; mounted under
    ``/actors/{actor_id}/demo/`` and absent in ``RunMode.PROD``
    (TRIG-08-004, TRIG-09-002).
    """

    GENERAL_PURPOSE = "general-purpose"
    DEMO_ONLY = "demo-only"


#: The requirements every general-purpose trigger route implements: the
#: endpoint shape (TRIG-01), the body rules (TRIG-03), the ``activity`` body
#: key (TRIG-04) and the structured error contract (HTTP-03-005).  Domain
#: modules extend it with the verb's own requirements.
GENERAL_TRIGGER_SPECS: tuple[str, ...] = (
    "TRIG-01-001",
    "TRIG-01-002",
    "TRIG-03-001",
    "TRIG-03-002",
    "TRIG-04-001",
    "HTTP-03-005",
)


@dataclass(frozen=True, slots=True)
class TriggerEntry:
    """One trigger verb: the data a route, a ratchet or the dispatcher reads.

    Attributes:
        verb: The route's final path segment (``propose-embargo``).
        request_model: The core ``TriggerRequest`` subclass the route builds
            from its body plus ``actor_id``; binds ``result_type``.
        use_case_class: The ``Svc*UseCase`` the dispatcher constructs as
            ``(dl, request, **ports)``.
        result_type: The ``TriggerResult`` subtype ``execute()`` returns —
            the verb's exact response-body key set (UCORG-05-005).
        exposure: General-purpose or demo-only (TRIG-08-002).
        bt_backed: Whether ``use_case_class`` runs a behavior tree through
            ``SvcBTTriggerBase``; decides which driven ports it is built with.
        spec_ids: The requirements the verb implements (its route's
            ``Implements:`` block).

    A row holds data only.  It validates itself at construction so a table
    that would misroute fails at import (TRIG-12-004), but it carries no
    per-verb behavior — a method here would be the facade ADR-0110 removed.
    """

    verb: str
    request_model: type[TriggerRequest[Any]]
    #: ``type``, not ``type[<Protocol>]``: each use case narrows ``request``
    #: and its port keywords to its own types, which a shared constructor
    #: Protocol could only spell as ``Any``.  ``SemanticEntry.use_case_class``
    #: makes the same choice; the dispatcher checks the result type at runtime.
    use_case_class: type
    result_type: type[TriggerResult]
    exposure: TriggerExposure
    bt_backed: bool
    spec_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not _VERB_RE.match(self.verb):
            raise TriggerRegistryError(
                f"trigger verb {self.verb!r} is not lower-case kebab-case"
            )
        bound = result_type_of(self.request_model)
        if bound is not self.result_type:
            raise TriggerRegistryError(
                f"row {self.verb!r}: {self.request_model.__name__} binds"
                f" {bound.__name__}, not {self.result_type.__name__}"
            )
        is_bt = issubclass(self.use_case_class, SvcBTTriggerBase)
        if is_bt != self.bt_backed:
            raise TriggerRegistryError(
                f"row {self.verb!r}: bt_backed={self.bt_backed} but"
                f" {self.use_case_class.__name__} is"
                f" {'' if is_bt else 'not '}a SvcBTTriggerBase subclass"
            )
        if not self.spec_ids:
            raise TriggerRegistryError(
                f"row {self.verb!r} cites no spec requirement"
            )


def index_by_request_model(
    entries: Iterable[TriggerEntry],
) -> dict[type[TriggerRequest[Any]], TriggerEntry]:
    """Index rows by ``request_model`` for the dispatcher's resolution step.

    Several verbs may share one request model (the three demo ``notify-*``
    verbs all build an ``AddParticipantStatusTriggerRequest``); the index is
    well-defined only when they agree on the use case and result type, so a
    disagreement raises rather than letting assembly order pick a winner.
    """
    index: dict[type[TriggerRequest[Any]], TriggerEntry] = {}
    for entry in entries:
        seen = index.get(entry.request_model)
        if seen is None:
            index[entry.request_model] = entry
            continue
        if (
            seen.use_case_class is not entry.use_case_class
            or seen.result_type is not entry.result_type
        ):
            raise TriggerRegistryError(
                f"rows {seen.verb!r} and {entry.verb!r} share request model"
                f" {entry.request_model.__name__} but disagree on the use case"
                " or result type"
            )
    return index


def _iter_duplicate_verbs(entries: Iterable[TriggerEntry]) -> Iterator[str]:
    seen: set[str] = set()
    for entry in entries:
        if entry.verb in seen:
            yield entry.verb
        seen.add(entry.verb)
