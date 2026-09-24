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

"""Which snapshot fields an RSH-05 adjudication patch may name.

One contract with three parties, so it lives in one module rather than being
restated by each:

* ``FilterParticipantStatusDimensionsNode`` (status/nodes/dimension_filter.py)
  publishes a patch for a wire-shaped ``ParticipantStatus``;
* ``FinalizeCsFilterNode`` (status/nodes/cs_dimension_filter.py) publishes one
  for a wire-shaped ``CaseStatus``;
* ``CommitCaseLedgerEntryNode`` (case/nodes/lifecycle.py) validates an incoming
  patch against the union of the two (RSH-05-013) and merges it onto the
  canonical payload snapshot.

Every field is named as a **core** field, and the AS2 snapshot key it
corresponds to is read from the field's own alias through
:mod:`vultron.core.models.wire_keys`.  Core logic therefore types no AS2
spelling (ADR-0099 detail 2) and there is no hand-written table to drift from
the models.

Spec: ``specs/received-status-handling.yaml`` RSH-05-004, RSH-05-009,
RSH-05-013; ``specs/case-ledger-processing.yaml`` CLP-07-001.
"""

from typing import Any

from pydantic import BaseModel

from vultron.core.models.case_status import CaseStatus
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.wire_keys import input_keys, wire_key, wire_keys

#: The ``ParticipantStatus`` dimensions ``FilterParticipantStatusDimensionsNode``
#: adjudicates.  ``em`` and ``consent`` are deliberately absent: ``em`` is
#: EmbargoTeardownAuthorizationGate's to adjudicate (ADR-0046, ISSUE-2256) and
#: ``consent`` passes through untouched, so neither may be patched from there.
PARTICIPANT_STATUS_PATCH_FIELDS: tuple[str, ...] = (
    "rm",
    "vf",
    "d",
    "case_status",
)

#: The ``CaseStatus`` dimensions ``FinalizeCsFilterNode`` adjudicates, reached
#: either flat or inside a patched ``case_status``.
CASE_STATUS_PATCH_FIELDS: tuple[str, ...] = ("em", "pxa")

#: :data:`PARTICIPANT_STATUS_PATCH_FIELDS` as the AS2 snapshot keys a patch names.
PARTICIPANT_STATUS_PATCH_KEYS: tuple[str, ...] = wire_keys(
    PARTICIPANT_STATUS_PATCH_FIELDS, ParticipantStatus
)

#: :data:`CASE_STATUS_PATCH_FIELDS` as the AS2 snapshot keys a patch names.
CASE_STATUS_PATCH_KEYS: tuple[str, ...] = wire_keys(
    CASE_STATUS_PATCH_FIELDS, CaseStatus
)

_PATCHABLE: tuple[tuple[type[BaseModel], tuple[str, ...]], ...] = (
    (ParticipantStatus, PARTICIPANT_STATUS_PATCH_FIELDS),
    (CaseStatus, CASE_STATUS_PATCH_FIELDS),
)


def _other_spellings(
    model: type[BaseModel], field_name: str
) -> frozenset[str]:
    """Return every spelling of *field_name* other than its AS2 snapshot key."""
    key = wire_key(field_name, model)
    return frozenset(
        spelling
        for spelling in input_keys(model, field_name)
        if spelling != key
    )


#: The AS2 snapshot key of each patchable field, mapped to every *other* spelling
#: of the same field.
#:
#: Two jobs, both needing the same set.  The **keys** are the allow-list
#: RSH-05-013 validates an override's ``fields`` against — a producer naming
#: anything else is a bug, and the commit node hard-fails.  The **values** are
#: the twins :func:`drop_stale_twins` removes: the ``object`` being patched is a
#: *wire object* — CLP-07-001 makes the payload snapshot AS2-shaped, so it is
#: normally serialized ``by_alias`` and carries only the camelCase key — but a
#: snapshot that reached this actor by some other route may carry a second
#: spelling of the same field, and leaving that twin beside a patched alias would
#: let a consumer read the value the receiver just refused (RSH-05-009,
#: CLP-07-001, CM-18-006).
#:
#: This replaces the hand-written ``_SNAKE_TWINS`` table, which listed the seven
#: camelCase keys and their snake_case partners literally and included
#: ``emConsentState``, a key no producer emits (#3485 AC-2).
PATCH_KEY_TWINS: dict[str, frozenset[str]] = {
    wire_key(field_name, model): _other_spellings(model, field_name)
    for model, field_names in _PATCHABLE
    for field_name in field_names
}


def drop_stale_twins(obj: dict[str, Any], patched_key: str) -> None:
    """Remove every other spelling of the field *patched_key* just overwrote.

    See :data:`PATCH_KEY_TWINS` for why a twin left behind is a correctness
    problem rather than merely untidy (RSH-05-009).
    """
    for twin in PATCH_KEY_TWINS.get(patched_key, frozenset()):
        obj.pop(twin, None)
