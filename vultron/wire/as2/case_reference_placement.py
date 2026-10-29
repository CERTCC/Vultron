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

"""Parse-edge refusal of a case reference outside the acts that name a case.

A ``VulnerabilityCase`` that carries only its ``id`` and ``type`` is the
typed reference a participant's ``Join``, ``Ignore`` or ``Leave`` of a case,
or an ownership-transfer ``Offer``, names its case by (AKM-03-004, ADR-0165).
Anywhere else a case is carried whole, so a reference there is a malformed
case: a ``Create(VulnerabilityCase)`` that carried one would reach core
naming a case with no owner and no position.  The parser refuses it where it
arrives, as it refused the sparse case before references existed: an inline
case that fails the case's validation is never read as a less specific type,
and its activity is refused as malformed (MV-04-003; ADR-0032, validate at
the edge).
"""

from collections.abc import Iterator

from vultron.core.models.case_naming import CASE_NAMING_ACTIVITY_TYPES
from vultron.wire.as2.errors import VultronParseValidationError
from vultron.wire.as2.vocab.base.base import as_Base
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCaseReference,
)


def _misplaced_references(value: object, path: str) -> Iterator[str]:
    """The paths below *path* that hold a case reference no act may carry."""
    if isinstance(value, list):
        for index, item in enumerate(value):
            yield from _misplaced_references(item, f"{path}[{index}]")
        return
    if isinstance(value, as_VulnerabilityCaseReference):
        yield path
        return
    if not isinstance(value, as_Base):
        return
    names_case = (
        isinstance(value, as_Activity)
        and str(value.type_) in CASE_NAMING_ACTIVITY_TYPES
    )
    for field_name in type(value).model_fields:
        child = getattr(value, field_name, None)
        if (
            names_case
            and field_name == "object_"
            and isinstance(child, as_VulnerabilityCaseReference)
        ):
            continue
        key = field_name.rstrip("_")
        child_path = f"{path}.{key}" if path else key
        yield from _misplaced_references(child, child_path)


def refuse_misplaced_case_reference(activity: as_Activity) -> None:
    """Refuse *activity* when a case reference sits where a case is carried.

    Raises:
        VultronParseValidationError: Naming the activity and each slot.
    """
    misplaced = list(_misplaced_references(activity, ""))
    if misplaced:
        raise VultronParseValidationError(
            f"activity {activity.id_!r}: a VulnerabilityCase carrying only"
            f" its id and type at {', '.join(misplaced)} names the case;"
            " only the object of a Join, Ignore, Leave or Offer may name a"
            " case by reference, and anywhere else the case is carried whole"
            " (AKM-03-004)"
        )


__all__ = ["refuse_misplaced_case_reference"]
