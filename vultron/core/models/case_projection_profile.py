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

"""The profiles a case is cut by for a projection (ADR-0219).

A **projection** is a document a participant makes from its replica of a
case, for a reader outside the protocol.  It is made in two steps: the call
site's profile cuts the case and its ledger into a
:class:`~vultron.core.models.case_preview.CasePreview`, and a renderer
translates only that preview into one format.  The profile decides what may
leave the case, for every format; a renderer decides only what its format can
express.  So nothing here names a format.

A :class:`ProjectionProfile` is the field profile of ADR-0217
(:data:`~vultron.core.models.case_preview_profile.CasePreviewProfile`), one
operation for every case field, plus what it does with the case ledger, which
is not a case field.  Each call site uses one fixed profile:

- :data:`PUBLIC_PROFILE`, at the draft step of the publication pipeline:
  the facts of a public advisory, with no participant, no ledger and no
  embargo.
- :data:`JOINED_PROFILE`, at the operator's request for a document to give a
  party outside Vultron: what a joined participant sees, without the case
  bookkeeping.

Each profile also names the distribution label of the documents it cuts for
and its own versioned name, which a document's identity derives from.  The
version is bumped whenever a change to the profile, or to a renderer, changes
what a projection holds.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from vultron.core.models.base import CoreObject
from vultron.core.models.case.vulnerability_case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_preview_profile import (
    CasePreviewProfile,
    PreviewFieldRule,
    PreviewOperation,
    Substitution,
    current_status,
    preview_type,
)
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.preview_object import PreviewObject, to_loose

_OP = PreviewOperation
_ANY = frozenset(PreviewOperation)


class DistributionLabel(StrEnum):
    """The Traffic Light Protocol label a projection is shared under.

    The FIRST TLP 2.0 labels.  The label belongs to the document only; how a
    label appears inside Vultron is a separate question (#5133).
    """

    CLEAR = "CLEAR"
    GREEN = "GREEN"
    AMBER = "AMBER"
    AMBER_STRICT = "AMBER+STRICT"
    RED = "RED"


#: The acts whose ledger entries the joined profile keeps: the coordination
#: events a reader outside the protocol can read as events, by the crosswalk
#: concept mapping (``docs/reference/csaf_crosswalk/concept_mapping.md``).
#: Every other entry records case bookkeeping and is left out.
JOINED_LEDGER_ACTS: frozenset[str] = frozenset(
    semantics.value
    for semantics in (
        MessageSemantics.SUBMIT_REPORT,
        MessageSemantics.VALIDATE_REPORT,
        MessageSemantics.INVALIDATE_REPORT,
        MessageSemantics.ENGAGE_CASE,
        MessageSemantics.ACTIVATE_EMBARGO_ON_CASE,
        MessageSemantics.ACCEPT_INVITE_TO_EMBARGO_ON_CASE,
        MessageSemantics.REJECT_INVITE_TO_EMBARGO_ON_CASE,
    )
)

#: What a kept ledger entry shows of itself.  Its ``payloadSnapshot`` is cut
#: separately (:data:`SHOWN_PAYLOAD_KEYS`); its chain links and receipt time
#: are bookkeeping.
SHOWN_ENTRY_FIELDS = (
    "context",
    "log_index",
    "log_object_id",
    "semantic_type",
    "entry_hash",
    "published",
    "payload_snapshot",
)

#: What a kept entry shows of the activity it records: who acted, toward
#: whom, when, and which act it answers.  The activity's ``object``,
#: ``target`` and any other member are left out, because the snapshot holds
#: the activity verbatim, and a value the profile withholds elsewhere, such
#: as an embargo proposal, could otherwise leave the case inside it
#: (ADR-0219).
SHOWN_PAYLOAD_KEYS = ("id", "type", "actor", "to", "published", "inReplyTo")


@dataclass(frozen=True)
class ProjectionProfile:
    """The profile one call site cuts a case by for a projection (ADR-0219).

    Attributes:
        name: The versioned name, such as ``public-v1``.  A projection's
            identity derives from it, so it changes whenever the profile or a
            renderer changes what a projection holds.
        distribution: The label every document cut by this profile is shared
            under.
        fields: One operation for every case field (ADR-0217).
        ledger_acts: The semantic types whose ledger entries the preview
            keeps, each cut to :data:`SHOWN_ENTRY_FIELDS` and
            :data:`SHOWN_PAYLOAD_KEYS`; ``None`` to omit the ledger.

    Raises:
        ValueError: When *fields* does not name every case field, so a cut
            would have to guess (ADR-0219).
    """

    name: str
    distribution: DistributionLabel
    fields: CasePreviewProfile
    ledger_acts: frozenset[str] | None = None

    def __post_init__(self) -> None:
        unclassified = sorted(
            set(VulnerabilityCase.model_fields) - set(self.fields)
        )
        if unclassified:
            raise ValueError(
                f"projection profile {self.name!r} has no row for"
                f" {unclassified} (ADR-0219)"
            )

    @property
    def ledger_operation(self) -> PreviewOperation:
        """What the profile does with the ledger list: omit it, or
        substitute the entries it keeps."""
        return _OP.OMIT if self.ledger_acts is None else _OP.SUBSTITUTE

    def cut_ledger(
        self, ledger: Sequence[CaseLedgerEntry]
    ) -> list[PreviewObject] | None:
        """The entries of *ledger* this profile keeps, each cut, in order.

        ``None`` when the profile omits the ledger or keeps none of its
        entries: a list that cannot be empty is left out, never marked.
        """
        if self.ledger_acts is None:
            return None
        kept = [
            _cut_entry(entry)
            for entry in ledger
            if entry.semantic_type in self.ledger_acts
        ]
        return kept or None


def _cut_entry(entry: CaseLedgerEntry) -> PreviewObject:
    """*entry* as a projection shows it: its coordinates, its act's label
    and the envelope of the activity it records."""
    payload = {
        key: entry.payload_snapshot[key]
        for key in SHOWN_PAYLOAD_KEYS
        if key in entry.payload_snapshot
    }
    return to_loose(
        entry.model_copy(update={"payload_snapshot": payload}),
        SHOWN_ENTRY_FIELDS,
    )


def _rule(chosen: PreviewOperation) -> PreviewFieldRule:
    """A row a projection may cut any way; it applies *chosen*."""
    if chosen is _OP.SUBSTITUTE:
        raise ValueError("a substitute row names its substitution")
    return PreviewFieldRule(permitted=_ANY, chosen=chosen)


def _substitute(substitution: Substitution) -> PreviewFieldRule:
    """A row a projection may cut any way; it applies *substitution*."""
    return PreviewFieldRule(
        permitted=_ANY, chosen=_OP.SUBSTITUTE, substitution=substitution
    )


_INCLUDE = _rule(_OP.INCLUDE)
_OMIT = _rule(_OP.OMIT)

#: The rows the two profiles share, as the field-group table of
#: ``notes/csaf-projection.md`` lists them.  A projection is not carried in
#: a case reference, so its preview names the case by its own ``id``.
_SHARED_ROWS: dict[str, PreviewFieldRule] = {
    "id_": _INCLUDE,
    "type_": _substitute(preview_type),
    "context_": _OMIT,
    "name": _INCLUDE,
    "summary": _INCLUDE,
    "published": _INCLUDE,
    "updated": _INCLUDE,
    "vulnerability_items": _INCLUDE,
    "case_references": _INCLUDE,
    "case_statuses": _substitute(current_status),
    "ledger_position": _INCLUDE,
    "stub_summary": _OMIT,
    "actor_participant_index": _OMIT,
    "pending_embargo_proposal_index": _OMIT,
    "genesis_hash": _OMIT,
    "parent_cases": _OMIT,
    "child_cases": _OMIT,
    "sibling_cases": _OMIT,
}

#: The rows in which the two profiles differ: the public one omits each,
#: and the joined one includes each.
_JOINED_ONLY = (
    "content",
    "notes",
    "vulnerability_reports",
    "attributed_to",
    "embargo_register",
    "case_participants",
)


def _profile_rows(
    overrides: Mapping[str, PreviewFieldRule],
) -> CasePreviewProfile:
    """The shared rows with *overrides*, then every other AS2 property an
    object carries, omitted."""
    rows = {**_SHARED_ROWS, **overrides}
    return MappingProxyType(
        {
            **rows,
            **{
                name: _OMIT
                for name in CoreObject.model_fields
                if name not in rows
            },
        }
    )


#: The profile of the publication pipeline's draft step (ADR-0219).
PUBLIC_PROFILE = ProjectionProfile(
    name="public-v1",
    distribution=DistributionLabel.CLEAR,
    fields=_profile_rows({name: _OMIT for name in _JOINED_ONLY}),
)

#: The profile of the operator's request for a document to give a party
#: outside Vultron (ADR-0219).
JOINED_PROFILE = ProjectionProfile(
    name="joined-v1",
    distribution=DistributionLabel.AMBER_STRICT,
    fields=_profile_rows({name: _INCLUDE for name in _JOINED_ONLY}),
    ledger_acts=JOINED_LEDGER_ACTS,
)


__all__ = [
    "JOINED_LEDGER_ACTS",
    "JOINED_PROFILE",
    "PUBLIC_PROFILE",
    "SHOWN_ENTRY_FIELDS",
    "SHOWN_PAYLOAD_KEYS",
    "DistributionLabel",
    "ProjectionProfile",
]
