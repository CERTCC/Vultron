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

"""Ask the participant-suggestion port about a case (ADR-0186, BT-24-008).

:func:`suggest_case_participants` is the one way core asks the
:class:`~vultron.core.ports.participant_suggestion.ParticipantSuggestionPort`:
it resolves the case's report and participant references, projects the case
to its :class:`~vultron.core.models.participant_suggestion.SuggestionContext`
and hands the port only that.  The call-out wrapper inside a tree
(:class:`~vultron.core.behaviors.call_out.bundles.participant_suggestion.SuggestParticipantsRetriever`)
and a Sentinel outside core both call it, so the disclosure decision the
projection makes is made once.  A ratchet holds this module to being the
port's only caller.
"""

import logging

from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.participant_suggestion import (
    ParticipantSuggestion,
    SuggestionContext,
)
from vultron.core.models.report import VulnerabilityReport
from vultron.core.ports.case_persistence import CasePersistence
from vultron.core.ports.participant_suggestion import (
    ParticipantSuggestionPort,
)
from vultron.errors import VultronNotFoundError

logger = logging.getLogger(__name__)


def _resolved[T](
    refs: list[str | T], kind: type[T], dl: CasePersistence
) -> list[T]:
    """*refs* with every bare id read from *dl* as a *kind*.

    Raises:
        VultronNotFoundError: A reference names no *kind* in *dl*.
    """
    resolved: list[T] = []
    for ref in refs:
        if not isinstance(ref, str):
            resolved.append(ref)
            continue
        record = dl.read(ref)
        if not isinstance(record, kind):
            raise VultronNotFoundError(kind.__name__, ref)
        resolved.append(record)
    return resolved


def suggestion_context(
    case: VulnerabilityCase, dl: CasePersistence
) -> SuggestionContext:
    """*case*'s suggestion context, its references read from *dl*.

    The stored case lists its reports and participants by id, so each is
    read as its object before the case is projected.  *case* itself is not
    changed.

    Raises:
        VultronNotFoundError: A report or participant the case names is not
            in *dl*.
        VultronValidationError: A participant names no actor.
    """
    inline = case.model_copy(
        update={
            "vulnerability_reports": _resolved(
                list(case.vulnerability_reports), VulnerabilityReport, dl
            ),
            "case_participants": _resolved(
                list(case.case_participants), CaseParticipant, dl
            ),
        }
    )
    return SuggestionContext.from_case(inline)


def suggest_case_participants(
    case: VulnerabilityCase,
    port: ParticipantSuggestionPort,
    dl: CasePersistence,
) -> list[ParticipantSuggestion]:
    """Ask *port* who else should take part in *case* (BT-24-001).

    Projects *case* through :func:`suggestion_context` and asks *port* about
    that context alone (BT-24-002).  The answer may be empty (BT-24-004).

    Raises:
        VultronNotFoundError: A report or participant the case names is not
            in *dl*.
        VultronValidationError: A participant names no actor.
        VultronError: The adapter could not answer.
        TypeError: The adapter answered with something other than
            :class:`ParticipantSuggestion` objects.  It is a wiring error, so
            it is not a ``VultronError`` and fails a tree run whole.
    """
    context = suggestion_context(case, dl)
    suggestions = list(port.suggest_participants(context))
    wrong = sorted(
        {
            type(s).__name__
            for s in suggestions
            if not isinstance(s, ParticipantSuggestion)
        }
    )
    if wrong:
        raise TypeError(
            f"{type(port).__name__} answered with {wrong}; a "
            "participant-suggestion adapter answers ParticipantSuggestion "
            "objects (BT-24-004)."
        )
    logger.debug(
        "Actor '%s' asked for participant suggestions on case '%s': %d named",
        dl.actor_id,
        case.id_,
        len(suggestions),
    )
    return suggestions


def suggest_participants_for_case_id(
    case_id: str,
    port: ParticipantSuggestionPort,
    dl: CasePersistence,
) -> list[ParticipantSuggestion]:
    """Read case *case_id* from *dl*, then :func:`suggest_case_participants`.

    For a caller that holds the case's id, as the tree's call-out and a
    Sentinel do.

    Raises:
        VultronNotFoundError: *dl* holds no case *case_id*, or a report or
            participant the case names.
        VultronValidationError: A participant names no actor.
        VultronError: The adapter could not answer.
        TypeError: The adapter answered with something other than
            :class:`ParticipantSuggestion` objects.
    """
    case = dl.read_case(case_id)
    if case is None:
        raise VultronNotFoundError("VulnerabilityCase", case_id)
    return suggest_case_participants(case, port, dl)


__all__ = [
    "suggest_case_participants",
    "suggest_participants_for_case_id",
    "suggestion_context",
]
