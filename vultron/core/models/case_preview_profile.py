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

"""The profile a case preview is cut from the case by (ADR-0217).

A case preview is cut from the full case field by field.  The protocol sets an
**envelope**: for each case field, the operations a sender may apply to it.
This codebase picks one of them per field in a static **profile**, so the cut
is mechanical and makes no choice per invitation (CM-17-010):

- **include**: the case's value, as held;
- **substitute**: a replacement (the ``summary`` from the owner's
  ``stub_summary``) or a reduction of the held value (the current status
  only, each vul item cut to its ``ids``);
- **redact**: a :class:`~vultron.core.models.redacted.Redacted` marker, one
  for a whole list;
- **omit**: no key.

:data:`INVITATION_PROFILE` is the profile a stub Invite's preview is cut by.
Each row is a :class:`PreviewFieldRule`: the operations the envelope permits,
the ones it forbids while an embargo is in force, and the one this codebase
applies.  :meth:`~vultron.core.models.case_preview.CasePreview.from_case`
applies it.

A field the envelope requires the preview to show (it permits neither redact
nor omit, at least while an embargo is in force) is a **shown item**.  A cut
that leaves a shown item without a value cannot be sent.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from pydantic import BaseModel

from vultron.core.models._helpers import new_object_id
from vultron.core.models.base import CoreObject
from vultron.core.models.case.vulnerability_case import VulnerabilityCase
from vultron.core.models.preview_object import to_loose
from vultron.core.models.redacted import Redacted
from vultron.errors import VultronActivityConstructionError


class PreviewOperation(StrEnum):
    """What a preview does with one case field (ADR-0217)."""

    INCLUDE = "include"
    SUBSTITUTE = "substitute"
    REDACT = "redact"
    OMIT = "omit"


_OP = PreviewOperation

#: Every operation: the envelope permits one unless a reason forbids it.
_ANY = frozenset(PreviewOperation)

#: The operations that show a field.  Redact and omit do not.
SHOWING_OPERATIONS = frozenset({_OP.INCLUDE, _OP.SUBSTITUTE})

#: What a substitution makes of the case: the value the preview shows, or
#: ``None`` when the case holds nothing to show.
Substitution = Callable[[VulnerabilityCase], object]


@dataclass(frozen=True)
class PreviewFieldRule:
    """One case field's row in a preview profile.

    Attributes:
        permitted: The operations the envelope permits for the field.
        chosen: The one the profile applies.  It is permitted, also while an
            embargo is in force.
        forbidden_in_force: The permitted operations the envelope forbids
            while an embargo is in force (CM-17-002, CM-17-013).
        substitution: What the field shows when ``chosen`` is substitute.
        reason: Why the envelope forbids an operation, for a refusal to name;
            empty when it forbids none.

    Raises:
        ValueError: When the row is not self-consistent: ``chosen`` is not
            permitted, an in-force restriction names an operation the row
            does not permit, or a substitute row has no substitution (or
            another row has one).
    """

    permitted: frozenset[PreviewOperation]
    chosen: PreviewOperation
    forbidden_in_force: frozenset[PreviewOperation] = frozenset()
    substitution: Substitution | None = None
    reason: str = ""

    def __post_init__(self) -> None:
        if not self.forbidden_in_force <= self.permitted:
            raise ValueError(
                f"a preview rule forbids {sorted(self.forbidden_in_force)}"
                f" in force but permits only {sorted(self.permitted)}"
            )
        if not self.permits(self.chosen, in_force=True):
            raise ValueError(
                f"a preview rule chooses {self.chosen!s}, which its envelope"
                f" {sorted(self.permitted)} does not permit while an embargo"
                " is in force"
            )
        if (self.chosen is _OP.SUBSTITUTE) != (self.substitution is not None):
            raise ValueError(
                "a preview rule has a substitution exactly when it chooses"
                f" substitute, not when it chooses {self.chosen!s}"
            )

    def substitute(self, case: VulnerabilityCase) -> object:
        """What the field shows of *case* under this row's substitution.

        Raises:
            ValueError: When the row does not substitute.
        """
        if self.substitution is None:
            raise ValueError(
                f"a preview rule that chooses {self.chosen!s} substitutes"
                " nothing"
            )
        return self.substitution(case)

    def permits(self, operation: PreviewOperation, *, in_force: bool) -> bool:
        """Whether the envelope permits *operation* on the field."""
        if in_force and operation in self.forbidden_in_force:
            return False
        return operation in self.permitted

    def must_show(self, *, in_force: bool) -> bool:
        """Whether the field is a shown item: neither redact nor omit is
        permitted."""
        return not (
            self.permits(_OP.REDACT, in_force=in_force)
            or self.permits(_OP.OMIT, in_force=in_force)
        )

    @property
    def omit_only(self) -> bool:
        """Whether the envelope permits nothing but omit: case bookkeeping a
        preview never carries."""
        return self.permitted == {_OP.OMIT}


#: A preview profile: one rule per case field, by Python field name.
type CasePreviewProfile = Mapping[str, PreviewFieldRule]


def _stub_summary(case: VulnerabilityCase) -> object:
    """The owner's chosen ``stub_summary`` (CM-17-020)."""
    return case.stub_summary


def _preview_id(_case: VulnerabilityCase) -> object:
    """The preview's own id, minted like any object's (OID-01-013).  The
    case reference carrying the preview names the case (ADR-0205)."""
    return new_object_id()


def _preview_type(_case: VulnerabilityCase) -> object:
    """The preview's own type, the case's defined preview (MV-10-012)."""
    return "CasePreview"


def _current_status(case: VulnerabilityCase) -> object:
    """The case's statuses reduced to the current one, whole (CM-17-013).

    Raises:
        VultronActivityConstructionError: When the case holds no status
            object to show, only ids.
    """
    try:
        current = case.current_status
    except ValueError as exc:
        raise VultronActivityConstructionError(
            f"case {case.id_!r} holds no case status to show its current one"
            " (CM-17-013)"
        ) from exc
    return [to_loose(current)]


def _in_force_embargo(case: VulnerabilityCase) -> object:
    """The register reduced to the in-force embargo, whole (CM-17-011).

    The register holds each embargo whole (ADR-0202), so the preview carries
    its terms and status and the invitee need not read them by id
    (CM-17-024).
    """
    embargo = case.active_embargo
    if embargo is None:
        return None
    return [to_loose(embargo)]


def _item_ids(case: VulnerabilityCase) -> object:
    """Each vul item cut to its ``ids``, the CVE ID among them (CM-05-018).

    An item the case holds by id alone has no ``ids`` to show, so it is a
    marker: the item is there, and the preview does not show it.
    """
    items = [
        Redacted() if isinstance(item, str) else to_loose(item, ("ids",))
        for item in case.vulnerability_items
    ]
    return items or None


def _shown(
    *,
    substitution: Substitution | None = None,
    include: bool = False,
    reason: str,
) -> PreviewFieldRule:
    """A shown item: the envelope permits neither redact nor omit."""
    return PreviewFieldRule(
        permitted=frozenset({_OP.INCLUDE, _OP.SUBSTITUTE}),
        chosen=_OP.INCLUDE if include else _OP.SUBSTITUTE,
        substitution=substitution,
        reason=reason,
    )


def _shown_in_force(
    substitution: Substitution, reason: str
) -> PreviewFieldRule:
    """A field the preview shows while an embargo is in force."""
    return PreviewFieldRule(
        permitted=_ANY,
        chosen=_OP.SUBSTITUTE,
        forbidden_in_force=frozenset({_OP.REDACT, _OP.OMIT}),
        substitution=substitution,
        reason=reason,
    )


#: Any operation; this codebase shows the value as held.
_INCLUDE = PreviewFieldRule(permitted=_ANY, chosen=_OP.INCLUDE)
#: Any operation; this codebase marks the value withheld.
_REDACT = PreviewFieldRule(permitted=_ANY, chosen=_OP.REDACT)
#: Case bookkeeping, meaningless outside the case.
_BOOKKEEPING = PreviewFieldRule(
    permitted=frozenset({_OP.OMIT}),
    chosen=_OP.OMIT,
    reason="case bookkeeping, meaningless outside the case",
)

#: The rows the profile names one by one.  Every other AS2 property the case
#: holds is redacted (:data:`INVITATION_PROFILE`).
_NAMED_ROWS: dict[str, PreviewFieldRule] = {
    "id_": PreviewFieldRule(
        permitted=frozenset({_OP.SUBSTITUTE}),
        chosen=_OP.SUBSTITUTE,
        substitution=_preview_id,
        reason="the case reference carrying the preview names the case"
        " (ADR-0205)",
    ),
    "type_": PreviewFieldRule(
        permitted=frozenset({_OP.SUBSTITUTE}),
        chosen=_OP.SUBSTITUTE,
        substitution=_preview_type,
        reason="the preview's type is CasePreview (MV-10-012)",
    ),
    # The JSON-LD context is not content.
    "context_": PreviewFieldRule(
        permitted=frozenset({_OP.INCLUDE, _OP.OMIT}), chosen=_OP.OMIT
    ),
    "summary": _shown(
        substitution=_stub_summary,
        reason="the invitee needs readable context; set the case's"
        " stub_summary before inviting (MV-10-001, CM-17-020)",
    ),
    "attributed_to": _shown(
        include=True,
        reason="nobody joins a case without knowing who runs it",
    ),
    "case_statuses": _shown_in_force(
        _current_status,
        "the invitee needs the EM state while an embargo is in force"
        " (CM-17-013)",
    ),
    "name": _INCLUDE,
    "published": _INCLUDE,
    "updated": _INCLUDE,
    "vulnerability_items": PreviewFieldRule(
        permitted=_ANY, chosen=_OP.SUBSTITUTE, substitution=_item_ids
    ),
    "content": _REDACT,
    "case_participants": _REDACT,
    "vulnerability_reports": _REDACT,
    "notes": _REDACT,
    "case_references": _REDACT,
    "parent_cases": _REDACT,
    "child_cases": _REDACT,
    "sibling_cases": _REDACT,
    "embargo_register": PreviewFieldRule(
        permitted=frozenset({_OP.SUBSTITUTE, _OP.REDACT, _OP.OMIT}),
        chosen=_OP.SUBSTITUTE,
        forbidden_in_force=frozenset({_OP.REDACT, _OP.OMIT}),
        substitution=_in_force_embargo,
        reason="the invitee consents to the in-force terms (CM-17-002); open"
        " proposals reach it after joining (CM-17-014)",
    ),
    "pending_embargo_proposal_index": PreviewFieldRule(
        permitted=frozenset({_OP.OMIT}),
        chosen=_OP.OMIT,
        reason="open proposals reach the invitee after joining (CM-17-014)",
    ),
    "genesis_hash": _BOOKKEEPING,
    "ledger_position": _BOOKKEEPING,
    "actor_participant_index": _BOOKKEEPING,
    "stub_summary": _BOOKKEEPING,
}

#: The profile a stub Invite's case preview is cut by (CM-17-010, ADR-0217).
#: The named rows, then every other AS2 property an object carries, redacted.
#: A case field in neither has no row, so a new case field cannot be cut
#: until it is classified.
INVITATION_PROFILE: CasePreviewProfile = MappingProxyType(
    {
        **_NAMED_ROWS,
        **{
            name: _REDACT
            for name in CoreObject.model_fields
            if name not in _NAMED_ROWS
        },
    }
)


def _wire_name(field_name: str) -> str:
    """The key the case field *field_name* is written under."""
    info = VulnerabilityCase.model_fields[field_name]
    return info.serialization_alias or info.alias or field_name.rstrip("_")


def _has_value(held: object) -> bool:
    """Whether a case field holds a value: not ``None``, not empty."""
    if held is None:
        return False
    if isinstance(held, (list, dict, set, tuple)):
        return bool(held)
    return True


def _shown_as_held(held: object) -> object:
    """*held* as a preview shows it: each object in its loose form."""
    if isinstance(held, list):
        return [_shown_as_held(item) for item in held]
    if isinstance(held, BaseModel):
        return to_loose(held)
    return held


def _cut_field(
    case: VulnerabilityCase, name: str, rule: PreviewFieldRule
) -> object:
    """What the preview shows for *case*'s field *name* under *rule*, or
    ``None`` to leave the field out."""
    if rule.chosen is _OP.OMIT:
        return None
    if rule.chosen is _OP.SUBSTITUTE:
        return rule.substitute(case)
    held = getattr(case, name, None)
    if not _has_value(held):
        return None
    if rule.chosen is _OP.REDACT:
        return Redacted()
    return _shown_as_held(held)


def cut_case(
    case: VulnerabilityCase, profile: CasePreviewProfile
) -> dict[str, object]:
    """*case*'s fields as *profile* shows them, by Python field name.

    Each case field takes its row's chosen operation.  A field with no held
    value (absent, ``None`` or an empty collection) is left out, never
    marked: there is nothing to withhold.  A list field is redacted as one
    marker.

    Raises:
        VultronActivityConstructionError: When *profile* has no row for a
            case field, so the cut would have to guess; when the cut leaves a
            field the envelope requires it to show without a value; or when
            a substitution cannot be made.
    """
    unclassified = sorted(set(VulnerabilityCase.model_fields) - set(profile))
    if unclassified:
        raise VultronActivityConstructionError(
            f"case {case.id_!r}: the preview profile has no row for"
            f" {unclassified}, so the cut cannot decide what to show"
            " (ADR-0217)"
        )
    in_force = case.embargo_in_force
    data: dict[str, object] = {}
    for name, rule in profile.items():
        value = _cut_field(case, name, rule)
        if value is not None:
            data[name] = value
        elif rule.must_show(in_force=in_force):
            raise VultronActivityConstructionError(
                f"case {case.id_!r}: the preview cannot show"
                f" {_wire_name(name)!r}, which an invitation preview"
                f" must show: {rule.reason} (CM-17-010)"
            )
    return data


__all__ = [
    "INVITATION_PROFILE",
    "SHOWING_OPERATIONS",
    "CasePreviewProfile",
    "PreviewFieldRule",
    "PreviewOperation",
    "Substitution",
    "cut_case",
]
