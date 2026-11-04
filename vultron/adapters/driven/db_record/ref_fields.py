#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  (“Third Party Software”). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

# Copyright

"""Which fields of a model hold object references, and which stay inline.

Derived from each class's declared annotations, so the write path knows
which nested objects to collapse to an id and which to keep as snapshots.
"""

from functools import cache, lru_cache
from typing import Any, get_args

from pydantic import BaseModel

from vultron.core.models._helpers import strip_annotated
from vultron.core.models.base import CoreObject
from vultron.core.models.protocols import PersistableModel
from vultron.enums.object_types import VultronObjectType
from vultron.semantic_registry import (
    find_matching_semantics,
    semantics_to_activity_class,
)
from vultron.wire.as2.enums import (
    as_IntransitiveActivityType,
    as_TransitiveActivityType,
)
from vultron.wire.as2.vocab.base.links import as_Link
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_TransitiveActivity,
)
from vultron.wire.as2.vocab.base.objects.base import as_Object


def _is_generic_object_ref(annotation: Any) -> bool:
    """True when *annotation* is a reference to the *generic* ``as_Object``.

    The generic AS2 object-reference alias ``as_ObjectRef`` expands to
    ``as_Object | as_Link | NonEmptyString | None`` and its required form
    ``as_ObjectRequiredRef`` to ``as_Object | as_Link | NonEmptyString`` (no
    ``None``).  Both are matched; a *narrowed* reference (``as_ActorRef`` →
    ``as_Actor | as_Link | NonEmptyString | None``) is not, because its ``T`` is a
    subclass of ``as_Object`` rather than ``as_Object`` itself.  This is the
    single property that separates the AS2 Activity object-reference fields
    from narrowed refs, JSON-LD ``context``/``in_reply_to`` (typed ``Any``),
    and unrelated types' refs (``as_Relationship.subject``, …).

    Under ARCH-25-003 (ADR-0099) the aliases also admit ``CoreObject`` — a core
    object *is* its own wire object, so it may sit inline in an activity — and
    that widened form is matched too.  Missing it silently drops ``object_``,
    ``target``, ``origin`` and ``instrument`` from dehydration, so a stored
    activity's inline object reads back as a bare ``as_Object`` and semantic
    matching no longer recognises the activity.

    The IRI branch is ``NonEmptyString`` (CS-08-001), an ``Annotated`` wrapper
    around ``str`` that the union keeps; it is unwrapped before the set
    comparison, or every reference field would silently stop being dehydrated.
    """
    args = {strip_annotated(arg) for arg in get_args(annotation)} - {
        CoreObject
    }
    return args in (
        {as_Object, as_Link, str},
        {as_Object, as_Link, str, type(None)},
    )


@lru_cache(maxsize=1)
def _activity_object_ref_properties() -> frozenset[str]:
    """The generic object-reference field names of the AS2 Activity model.

    Derived from ``as_TransitiveActivity``'s own annotations — the single
    source of truth (ARCH-23-004).  ``object_`` is inherited by every
    transitive activity; ``target``/``origin``/``result``/``instrument`` come
    from ``as_Activity``.  This replaces the former hand-maintained frozenset
    restatement that could silently drift from the annotations it claimed to
    mirror (#2936).
    """
    return frozenset(
        name
        for name, field in as_TransitiveActivity.model_fields.items()
        if _is_generic_object_ref(field.annotation)
    )


@cache
def object_ref_fields(cls: type[BaseModel]) -> frozenset[str]:
    """The generic AS2 object-reference fields *cls* actually declares.

    These fields hold either an inline object or a bare URI string, so they
    are the only ones eligible for dehydration to an ID on write and
    rehydration back to an object on read.  Fields typed as concrete
    sub-objects (``inbox``/``outbox`` on actors, ``participant_statuses`` on
    participants) are excluded and stay inline, so ``model_validate``
    round-trips.

    Computed as the intersection of the model's own fields with the
    Activity-model object-reference properties, cached per class.  A model that
    narrows one of these names to a plain URI (``as_CaseProposal.target``,
    CP-01-005) still lists it — the name is what the storage layer keys on;
    :func:`~vultron.adapters.driven.datalayer_sqlite.hydration.field_admits_object`
    is the runtime guard that then declines to expand it.
    """
    return _activity_object_ref_properties() & frozenset(cls.model_fields)


# AS2 Activity ``type_`` strings (transitive + intransitive) plus
# ``CaseLedgerEntry``.  When a nested object-reference value has one
# of these types it MUST be kept inline rather than collapsed to a bare ID
# string for two independent reasons:
#
# 1. Technical: Activities may not have independent DataLayer records (e.g. a
#    reconstituted Offer in the validate-report path, a CaseLedgerEntry inside
#    an Announce envelope), so dehydrating them would make rehydration
#    impossible on read-back and cause AKM-03-003 outbox-gate failures.
#
# 2. Semantic (more important): a received Activity is an artifact; its inline
#    sub-fields are a snapshot of state at receipt time.  An
#    Accept(Offer(VulnerabilityCase)) captures what was offered at the moment
#    of acceptance, not the current case state.  This must not be changed even
#    if Activities eventually gain independent DataLayer records.  See
#    notes/datalayer-design.md § "Received Activity Artifacts: Inline
#    Sub-Field Snapshots Are Intentional".
#
# ``VulnerabilityCaseStub`` is kept inline for reason 1 alone, and more
# strictly: a stub never has a record of its own (an invitee holds no case,
# and the CASE_MANAGER holds the case the stub stands for), and the stub
# Invite is recognised by its target's ``type`` (CM-11-013), so a target
# collapsed to the stub's ID would read back as an unrecognisable Invite.
_KEEP_INLINE_NESTED_TYPES: frozenset[str] = frozenset(
    {e.value for e in as_TransitiveActivityType}
    | {e.value for e in as_IntransitiveActivityType}
    | {"CaseLedgerEntry", VultronObjectType.VULNERABILITY_CASE_STUB.value}
)


def _inline_typed_fields(cls: type[BaseModel]) -> frozenset[str]:
    """Fields of *cls* whose inline value must be re-typed on read-back.

    A superset of :func:`object_ref_fields`: re-typing is safe for any field
    that can hold an inline typed object, whereas *dehydration* is only safe
    for a field declared as a reference, so the two sets are deliberately
    distinct.

    ``context`` is here and not in :func:`object_ref_fields`.  It is never
    dehydrated, so it is always stored whole — but nothing re-typed it either,
    and ``as_Activity.context`` is loosely typed, so read-back left a raw
    ``dict``.  That is enough to break semantic matching:
    ``_OfferCaseParticipantRoleActivity`` is recognised by its ``context``
    being a ``VulnerabilityCase`` (ADR-0039), so a stored role offer came back
    classified UNKNOWN, was never coerced out of the base ``as_Offer``, and the
    receiver had no semantics to dispatch on.
    """
    return object_ref_fields(cls) | {"context"}


# Fields that hold a *list* of object references (ID strings or inline
# objects).  Used by ``DataLayer.hydrate()`` to expand bare ID strings to
# full domain objects — the list analogue of the object-reference fields.
_AS_LIST_REF_FIELDS: frozenset[str] = frozenset(
    {
        "case_participants",  # list[CaseParticipantRef] on VulnerabilityCase
    }
)


def _declared_inline_required_refs(cls: type) -> frozenset[str]:
    """The ``inline_required_refs`` *cls* declares, or an empty set."""
    declared = getattr(cls, "inline_required_refs", None)
    if isinstance(declared, frozenset | set):
        return frozenset(declared)
    return frozenset()


def _inline_required_refs(
    obj: "PersistableModel | BaseModel",
) -> frozenset[str]:
    """The fields of *obj* that storage must keep inline (DL-08-001).

    Read from *obj*'s own class and, for an activity held as a
    base-vocabulary class, from the semantic class it matches.  A received
    activity is parsed to its base class (``as_Offer``), not to the semantic
    class that declares the contract, and is stored as parsed.  Without the
    second lookup a received ownership-transfer Offer had its transferee
    collapsed to an id the CASE_MANAGER could not read back, and its ledger
    commit refused the bare ``target`` (DL-08-003, CLP-07-018, #4843).
    """
    inline_required = _declared_inline_required_refs(type(obj))
    if isinstance(obj, as_Activity):
        semantic_cls = semantics_to_activity_class().get(
            find_matching_semantics(obj)
        )
        if semantic_cls is not None and not isinstance(obj, semantic_cls):
            inline_required |= _declared_inline_required_refs(semantic_cls)
    return inline_required
