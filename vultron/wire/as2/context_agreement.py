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

"""Parse-edge refusal of an activity whose parts name different cases.

An activity says which case it is about in its ``context``, and so may the
object it carries: a note, a status, a participant, or an inner activity
that has a ``context`` of its own.  When two of these name different cases,
the sender has said two things about where the act belongs, and a receiver
that acted on either would ignore the other (HP-08-015).  Every value the
check reads is in the message, so it needs no receiver state and runs at the
parse edge, beside the other checks that a message's parts fit together
(ADR-0032, validate at the edge).

The parts compared are the activity and each object down its ``object``
chain: the carried object, and for a nested activity its own object, at any
depth (:func:`object_chain`).  A part that names no case has nothing to
disagree with, and a part named only by reference names none: a bare URI, a
``Link`` and a typed reference carry no ``context`` (MV-10-011).

A ``Refuse`` quotes the act it refuses as it arrived (CLP-05-001), so its
object is evidence, not a part of the refusal: the chain compared ends at
the ``Refuse``.  A refusal notice from a tree built on the target case
quotes an ``Add`` whose object names another case (HP-08-007), and the
participant must still be able to read it (CLP-06-006).
"""

from collections.abc import Iterator

from vultron.core.models.activity import VultronActivity
from vultron.wire.as2.errors import VultronParseValidationError
from vultron.wire.as2.vocab.base.links import as_Link
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.extension_activities import as_Refuse
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCaseStub,
)


def _is_activity(value: object) -> bool:
    """Whether *value* is an activity, wire or core, that carries an object."""
    return isinstance(value, as_Activity | VultronActivity)


def object_chain(activity: as_Activity) -> Iterator[tuple[str, object]]:
    """*activity* and each object down its ``object`` chain, with its path.

    Yields ``("", activity)`` first, then each carried object under the key
    the sender wrote (``"object"``, ``"object.object"``).  An activity's
    ``object`` holds one value, and a carried activity's own object follows
    it; any other object ends the chain.  A bare URI or a ``Link`` in an
    ``object`` slot is yielded as it is, so a caller decides what a
    reference means for its rule.
    """
    part: object = activity
    path = ""
    while True:
        yield path, part
        carried = (
            getattr(part, "object_", None) if _is_activity(part) else None
        )
        if carried is None:
            return
        part, path = carried, f"{path}.object" if path else "object"


def case_uri_of(case_ref: object) -> str | None:
    """Return the URI a case reference names.

    That is the string itself, the case a stub stands for (its ``case_id``,
    never its own ``<case-id>/stub`` id — CM-11-003), or the object's id.
    """
    if isinstance(case_ref, str):
        return case_ref or None
    if isinstance(case_ref, as_VulnerabilityCaseStub):
        return case_ref.case_id
    case_id = getattr(case_ref, "id_", None)
    return case_id if isinstance(case_id, str) and case_id else None


def _case_named_by(value: object) -> str | None:
    """The case one ``context`` value names: an IRI, a Link's ``href``, an id."""
    if isinstance(value, as_Link):
        return value.href
    return case_uri_of(value)


def cases_named_by_context(part: object) -> frozenset[str]:
    """The cases *part*'s ``context`` names; empty when it names none.

    A bare URI, a ``Link`` or a typed reference standing for an object has
    no ``context``, so it names no case.
    """
    context = getattr(part, "context", None)
    if context is None or isinstance(part, str | as_Link):
        return frozenset()
    values = context if isinstance(context, list) else [context]
    return frozenset(
        case for value in values if (case := _case_named_by(value)) is not None
    )


def _cases_text(cases: frozenset[str]) -> str:
    return ", ".join(f"case {case!r}" for case in sorted(cases))


def _compared_parts(activity: as_Activity) -> Iterator[tuple[str, object]]:
    """The :func:`object_chain` parts compared, ending at a ``Refuse``.

    A ``Refuse``'s object is the refused act as it arrived, quoted, so it is
    not compared with the ``Refuse``'s own ``context`` (CLP-05-001).
    """
    for path, part in object_chain(activity):
        yield path, part
        if isinstance(part, as_Refuse):
            return


def refuse_context_disagreement(activity: as_Activity) -> None:
    """Refuse *activity* when two of its parts' ``context`` name different cases.

    Each part that names a case is reported with the case it names, so the
    sender sees every part of the disagreement at once (EH-07-001).  An
    activity with one ``context`` in it, or whose parts all name the same
    case, passes, and the act a ``Refuse`` quotes is not compared.

    Raises:
        VultronParseValidationError: Naming the activity, each ``context``
            and the case it names (HP-08-015).
    """
    named = [
        (f"{path}.context" if path else "context", cases)
        for path, part in _compared_parts(activity)
        if (cases := cases_named_by_context(part))
    ]
    if len({cases for _, cases in named}) < 2:
        return
    parts = "; ".join(
        f"{position} names {_cases_text(cases)}" for position, cases in named
    )
    raise VultronParseValidationError(
        f"activity {activity.id_!r}: its parts name different cases ({parts});"
        " an activity and the objects it carries name one case, so the"
        " receiver cannot tell which case the act is for (HP-08-015)"
    )


__all__ = [
    "case_uri_of",
    "cases_named_by_context",
    "object_chain",
    "refuse_context_disagreement",
]
