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
"""Architecture test: every core string field refuses a blank (CS-08-001).

Spec: CS-08-001, CS-08-002, ARCH-10-001

Sibling of ``test_wire_reference_fields_reject_blank``.  Since ADR-0099 made
wire and core one class hierarchy, core reference fields carry the same
blank-string gap as the wire aliases did (#3877).  Core cannot derive "is a
reference" from an ``as_Link`` branch the way the wire ratchet does — a case id
is a bare string — so this test asserts the rule CS-08-001 actually states,
over every string-valued leaf of every field a core model *declares itself*:
scalar, union member, list item or dict value.  Each must refuse ``""`` and
``"   "`` at construction.  Fields a core class only inherits from the wire
base (``as_Object.name``, for one) belong to their declaring class and are the
wire ratchet's to judge; ``owner_of`` keeps them out of this scan.

The only fields allowed to accept a blank are the ones where ``""`` is a
documented sentinel meaning "not yet" (an unacknowledged hash, an endpoint the
model derives itself).  They are a pinned exemption set, not a ratchet
(ARCH-18-005): a sentinel is a documented design choice with no empty end state.
The set is exact in both directions, so one that stops accepting a blank must be
removed and the set never rots into a list of forgotten violations.
"""

import inspect
import sys

import pytest
from pydantic import BaseModel

from test.support.blank_strings import (
    declared_type,
    owner_of,
    rejects_blank,
    string_leaves,
)
from test.support.core_vocab import import_all_core_models

#: Fields where ``""`` is a documented sentinel, never a reference.  Each entry
#: names the meaning its own field description or writer gives the blank:
#:
#: - ``CoreActor.inbox`` / ``outbox``: "not supplied"; the model validator
#:   ``_derive_endpoints_from_id`` replaces it before the instance is returned.
#: - ``VulnerabilityCase.genesis_hash``: pre-genesis storage compatibility; the
#:   model validator enforces non-empty when ``attributed_to`` is present.
#: - ``HashChainLedgerRecord`` / ``CaseLedgerEntry.prev_log_hash``: "first entry"
#:   until the per-case genesis hash is assigned (CLP-08-001).
#: - ``HashChainLedgerRecord`` / ``CaseLedgerEntry.entry_hash``: "not yet
#:   computed"; the model validator fills it.
#: - ``VultronReplicationState.last_acknowledged_hash``: "nothing acknowledged,
#:   replay from genesis" (its description).
#: - ``VultronReplicationState.last_replayed_from_hash``: records the position
#:   ``replay_from_hash`` returned, which is ``""`` for a genesis replay, and
#:   ``should_replay`` compares it to that value (SYNC-15-003).  ``None`` there
#:   means "no replay yet"; ``""`` means "replayed from genesis".
#:
#: permanent: CS-08-001 (a documented "not yet" sentinel is not a reference), #3877
BLANK_SENTINEL_FIELDS: frozenset[str] = frozenset(
    {
        "CoreActor.inbox",
        "CoreActor.outbox",
        "VulnerabilityCase.genesis_hash",
        "HashChainLedgerRecord.prev_log_hash",
        "HashChainLedgerRecord.entry_hash",
        "CaseLedgerEntry.prev_log_hash",
        "CaseLedgerEntry.entry_hash",
        "VultronReplicationState.last_acknowledged_hash",
        "VultronReplicationState.last_replayed_from_hash",
    }
)


def core_model_classes() -> dict[str, type[BaseModel]]:
    """Every ``BaseModel`` subclass defined under ``vultron.core.models``.

    Scans the modules rather than the registries: ``VultronOutbox`` and
    ``HashChainLedgerRecord`` are plain ``BaseModel``s that register nowhere,
    and ARCH-21-001 defines a core model as any ``BaseModel`` subclass in the
    package.
    """
    import_all_core_models()
    found: dict[str, type[BaseModel]] = {}
    for module_name, module in list(sys.modules.items()):
        if not module_name.startswith("vultron.core.models"):
            continue
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, BaseModel) and obj.__module__.startswith(
                "vultron.core.models"
            ):
                found[obj.__qualname__] = obj
    return found


def string_fields(cls: type[BaseModel]) -> dict[str, object]:
    """``{field name: declared type}`` for the string-valued fields *cls* declares."""
    return {
        name: declared_type(field)
        for name, field in cls.model_fields.items()
        if owner_of(cls, name) is cls and string_leaves(declared_type(field))
    }


def blank_admitting_string_fields(cls: type[BaseModel]) -> list[str]:
    """Names of the string-valued fields of *cls* that accept a blank."""
    return [
        name
        for name, annotation in string_fields(cls).items()
        if not rejects_blank(annotation)
    ]


@pytest.mark.spec("CS-08-001")
@pytest.mark.spec("CS-08-002")
@pytest.mark.spec("ARCH-10-001")
def test_every_core_string_field_rejects_a_blank() -> None:
    """No core model carries ``""`` or ``"   "`` in a string-valued field."""
    offenders: list[str] = []
    blank_ok: set[str] = set()
    examined = 0
    for qualname, cls in sorted(core_model_classes().items()):
        for name, annotation in string_fields(cls).items():
            examined += 1
            key = f"{qualname}.{name}"
            if rejects_blank(annotation):
                continue
            if key in BLANK_SENTINEL_FIELDS:
                blank_ok.add(key)
                continue
            offenders.append(f"{key}: {annotation}")

    assert examined, (
        "no core string fields were examined — the test is vacuous"
    )
    assert not offenders, (
        "these core string fields accept a blank (CS-08-001). Declare the "
        "string as NonEmptyString — as the item type for a list, the value "
        'type for a dict — or, only for a documented "not yet" sentinel, '
        "add the field to BLANK_SENTINEL_FIELDS with its reason:\n"
        + "\n".join(f"  {o}" for o in offenders)
    )
    assert blank_ok == BLANK_SENTINEL_FIELDS, (
        "BLANK_SENTINEL_FIELDS lists fields that no longer accept a blank; "
        "remove them so the set stays exact: "
        f"{sorted(BLANK_SENTINEL_FIELDS - blank_ok)}"
    )


def test_the_scan_covers_the_fields_3877_named() -> None:
    """The fields the issue enumerated are in scope, so the check is not vacuous."""
    classes = core_model_classes()
    assert {"context", "in_reply_to"} <= set(
        string_fields(classes["VultronCreateCaseActivity"])
    )
    assert "result" in string_fields(classes["VultronAccept"])
    assert {"to", "cc"} <= set(string_fields(classes["VultronActivity"]))
    assert {
        "case_participants",
        "actor_participant_index",
        "parent_cases",
    } <= set(string_fields(classes["VulnerabilityCase"]))
    assert {"embargo", "replaces"} <= set(
        string_fields(classes["EmbargoRegisterEntry"])
    )


def test_ratchet_flags_a_bare_str_reference_field() -> None:
    """A deliberately bad model proves the check can fail, in every shape.

    A plain ``BaseModel`` outside the package: it is never scanned, so it
    cannot leak into other tests, and it is handed to the checker directly.
    """

    from vultron.primitives import NonEmptyString

    class _Bad(BaseModel):
        scalar: str | None = None
        items: list[str] = []
        values: dict[NonEmptyString, str] = {}
        keys: dict[str, NonEmptyString] = {}
        union: str | int | None = None

    class _Good(BaseModel):
        count: int = 0
        both: dict[NonEmptyString, NonEmptyString] = {}
        items: list[NonEmptyString] = []

    assert blank_admitting_string_fields(_Bad) == [
        "scalar",
        "items",
        "values",
        "keys",
        "union",
    ]
    assert blank_admitting_string_fields(_Good) == []
