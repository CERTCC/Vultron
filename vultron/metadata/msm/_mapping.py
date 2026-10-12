"""MSM mapping facts derived from the occasions on ``SEMANTIC_REGISTRY``.

Each ``SemanticEntry`` declares its occasions and its message page (ADR-0128).
This module derives what the occasions already say, so nothing here is typed
by hand:

- the mapping status of an entry (MSM-06-003, MSM-08-006);
- the discriminator, the payload fields or state contexts that tell an
  entry's occasions apart;
- the "Sent by" value of an occasion, from the sender entitlement its received
  use case declares (MSM-08-005).

:class:`RowSpec` is the derived view of one entry that the page renderer and
the MSM-06-002 ratchet read.
"""

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

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderExemption,
)
from vultron.core.models.events.base import MessageSemantics
from vultron.semantic_registry import SEMANTIC_REGISTRY
from vultron.semantic_registry._entry import (
    DISPATCHER_FALLBACKS,
    SemanticEntry,
)
from vultron.semantic_registry._occasion import (
    FieldValue,
    MessagePage,
    Occasion,
    ProtocolShorthand,
    StateContext,
)
from vultron.wire.as2.extractor._pattern import ActivityPattern


class MappingStatus(StrEnum):
    """How a protocol shorthand relates to a ``SEMANTIC_REGISTRY`` entry."""

    DIRECT = "direct"
    """One shorthand maps to exactly one semantics value."""
    COLLAPSE = "collapse"
    """Several shorthands share one wire form, told apart by a distinguisher."""
    EXPANSION = "expansion"
    """One shorthand expands across several wire forms."""
    EVOLVED = "evolved"
    """The shorthand's purpose is served by a mechanism on a different axis."""
    NONE = "none"
    """No formal protocol shorthand; wire activity with no formal counterpart."""


#: Dispatcher fallbacks: no page, no occasion (MSM-06-002).
EXEMPTED_SEMANTICS: frozenset[MessageSemantics] = DISPATCHER_FALLBACKS

#: All known page slugs, in canonical display order.
PAGE_SLUGS: tuple[str, ...] = tuple(page.value for page in MessagePage)


# ---------------------------------------------------------------------------
# Mapping status (MSM-08-006).
# ---------------------------------------------------------------------------


def entry_shorthands(entry: SemanticEntry) -> tuple[ProtocolShorthand, ...]:
    """Return the distinct shorthands *entry*'s occasions carry, in order."""
    return tuple(
        dict.fromkeys(
            o.shorthand for o in entry.occasions if o.shorthand is not None
        )
    )


def mapping_status(
    entry: SemanticEntry, registry: Sequence[SemanticEntry]
) -> MappingStatus:
    """Derive *entry*'s mapping status from the occasions in *registry*.

    - ``evolved`` when an occasion declares an evolved mechanism (MSM-05),
      which has no shorthand to count;
    - ``none`` when no occasion carries a shorthand;
    - ``collapse`` when the occasions carry several distinct shorthands;
    - ``expansion`` when its one shorthand is also carried by another entry;
    - ``direct`` otherwise, including several occasions sharing one shorthand.

    Args:
        entry: The entry to classify.
        registry: Every entry, so a shorthand spread across entries is seen.

    Returns:
        The derived :class:`MappingStatus`.
    """
    if any(o.evolved for o in entry.occasions):
        return MappingStatus.EVOLVED
    shorthands = entry_shorthands(entry)
    if not shorthands:
        return MappingStatus.NONE
    if len(shorthands) > 1:
        return MappingStatus.COLLAPSE
    shorthand = next(iter(shorthands))
    carriers = sum(
        1 for other in registry if shorthand in entry_shorthands(other)
    )
    return MappingStatus.EXPANSION if carriers > 1 else MappingStatus.DIRECT


def discriminator(occasions: Iterable[Occasion]) -> str | None:
    """Name what tells the *occasions* of one entry apart, or ``None``.

    A field-value distinguisher contributes its field name; a state context
    contributes "<machine> state context".  Distinct names are joined with
    `` / `` in first-seen order.
    """
    names: list[str] = []
    for occasion in occasions:
        d = occasion.distinguisher
        if isinstance(d, FieldValue):
            names.append(d.field)
        elif isinstance(d, StateContext):
            names.append(f"{d.machine.__name__} state context")
    unique = list(dict.fromkeys(names))
    return " / ".join(unique) if unique else None


# ---------------------------------------------------------------------------
# "Sent by" (MSM-08-005).
# ---------------------------------------------------------------------------

#: The "Sent by" wording per entitlement kind (MSM-08-005, decided in #4418).
#: Moving it onto the kind itself is planned (MSM-08-010,
#: ``notes/message-occasion-table.md``).
#: ``NAMED_ACTOR`` is worded from the answered request; see :func:`sent_by`.
SENT_BY_WORDING: dict[SenderEntitlementKind, str] = {
    SenderEntitlementKind.CASE_MANAGER: "the case manager",
    SenderEntitlementKind.CASE_OWNER: "the case owner",
    SenderEntitlementKind.ACTIVE_PARTICIPANT: "an active participant",
    SenderEntitlementKind.INVITEE: "the invitee",
    SenderEntitlementKind.EXECUTING_ACTOR: "the receiving actor itself",
    SenderEntitlementKind.ANY_ACTOR: "any actor",
}

#: The "Sent by" wording for a use case whose sender is not yet checked.
NOT_YET_CHECKED = "not yet checked"


def _words(type_name: str) -> str:
    """``"CaseProposal"`` → ``"case proposal"``."""
    return " ".join(re.findall(r"[A-Z][a-z0-9]*", type_name)).lower()


def answered_request(entry: SemanticEntry) -> str:
    """Name the request *entry*'s activity answers, from its object type.

    ``Accept(CaseProposal)`` answers a case proposal; for a nested pattern
    such as ``Accept(Offer(VulnerabilityCase))`` the request is the inner
    object, a vulnerability case.

    Raises:
        ValueError: When the entry's pattern names no object type.
    """
    pattern = entry.pattern
    obj = None if pattern is None else pattern.object_
    if isinstance(obj, ActivityPattern):
        obj = obj.object_
    if obj is None or isinstance(obj, ActivityPattern):
        raise ValueError(
            f"{entry.semantics.name}: the pattern names no object type to"
            " word an addressee from (MSM-08-005)"
        )
    return _words(str(obj))


def sent_by(entry: SemanticEntry, occasion: Occasion) -> str:
    """Derive the "Sent by" value of *occasion* on *entry* (MSM-08-005).

    The value is the wording of the sender entitlement that the entry's
    received use case declares, or :data:`NOT_YET_CHECKED` for an exemption.
    The occasion's usual sender roles, when it has any, follow in
    parentheses: "an active participant (usually: vendor)".

    Raises:
        ValueError: When the use case declares no sender entitlement.
    """
    declared = getattr(entry.use_case_class, "sender_entitlement", None)
    if isinstance(declared, SenderExemption):
        wording = NOT_YET_CHECKED
    elif declared is SenderEntitlementKind.NAMED_ACTOR:
        wording = f"the addressee of the {answered_request(entry)}"
    elif isinstance(declared, SenderEntitlementKind):
        wording = SENT_BY_WORDING[declared]
    else:
        raise ValueError(
            f"{entry.use_case_class.__name__} declares no sender_entitlement"
            " (HP-01-007)"
        )
    if not occasion.usual_senders:
        return wording
    usual = ", ".join(
        role.value.replace("_", " ") for role in occasion.usual_senders
    )
    return f"{wording} (usually: {usual})"


# ---------------------------------------------------------------------------
# Derived rows.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RowSpec:
    """The mapping-table row of one ``SEMANTIC_REGISTRY`` entry, all derived.

    Attributes:
        semantics: The ``MessageSemantics`` enum value.
        page: Primary page slug under ``docs/reference/messages/``.
        shorthands: The distinct shorthands the entry's occasions carry.
        status: How the shorthands relate to this wire form.
        discriminator: What tells the entry's occasions apart, or ``None``.
    """

    semantics: MessageSemantics
    page: str
    shorthands: tuple[str, ...]
    status: MappingStatus
    discriminator: str | None


def row_for(
    entry: SemanticEntry, registry: Sequence[SemanticEntry]
) -> RowSpec:
    """Derive the :class:`RowSpec` of *entry* (a non-fallback entry).

    Raises:
        ValueError: When *entry* is a dispatcher fallback, which owns no page.
    """
    if entry.page is None:
        raise ValueError(
            f"{entry.semantics.name} is a dispatcher fallback and has no row"
        )
    return RowSpec(
        semantics=entry.semantics,
        page=entry.page.value,
        shorthands=tuple(s.value for s in entry_shorthands(entry)),
        status=mapping_status(entry, registry),
        discriminator=discriminator(entry.occasions),
    )


#: One derived row per non-fallback ``SEMANTIC_REGISTRY`` entry, grouped by
#: page in :data:`PAGE_SLUGS` order and in registry order within a page.
ROW_SPECS: tuple[RowSpec, ...] = tuple(
    sorted(
        (
            row_for(e, SEMANTIC_REGISTRY)
            for e in SEMANTIC_REGISTRY
            if e.semantics not in EXEMPTED_SEMANTICS
        ),
        key=lambda row: PAGE_SLUGS.index(row.page),
    )
)

#: Mapping from page slug → tuple of RowSpecs assigned to that page.
PAGE_ROWS: dict[str, tuple[RowSpec, ...]] = {
    slug: tuple(row for row in ROW_SPECS if row.page == slug)
    for slug in PAGE_SLUGS
    if any(row.page == slug for row in ROW_SPECS)
}

#: Mapping from ``MessageSemantics`` → ``RowSpec`` for O(1) lookup.
SEMANTICS_TO_ROW: dict[MessageSemantics, RowSpec] = {
    row.semantics: row for row in ROW_SPECS
}
