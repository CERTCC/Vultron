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

"""Check that a ledger entry's ``semantic_type`` is the registry's label (ADR-0140).

An entry stores its semantic type so that replay can route on one string, but
the type is never chosen apart from the payload: it must equal what
:func:`~vultron.semantic_registry.find_matching_semantics` returns for the
entry's ``payload_snapshot`` (ADR-0140 item 3, #4724).

:func:`registry_label` classifies one snapshot, and
:func:`label_mismatches` lists every entry whose stored type differs.  The
in-process demo and per-actor-store harnesses call them on every entry their
scenarios leave behind.

A snapshot carries a nested object bare where its sender named one the case
already holds (CLP-07-006), and a bare object satisfies no ``object_`` type
(SE-01-006), so the CASE_MANAGER labels such a payload after rehydrating it.
A caller that holds the CASE_MANAGER's store passes it as *dl*, and the
payload is rehydrated against it before it is labelled.
"""

from collections.abc import Iterable, Mapping
from typing import Any

from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.ports.datalayer import DataLayer
from vultron.semantic_registry import find_matching_semantics
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.rehydration import rehydrate
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity


def registry_label(
    payload_snapshot: Mapping[str, Any], dl: DataLayer | None = None
) -> str:
    """The semantic type the registry assigns to *payload_snapshot*.

    *dl*, when given, is the store the payload is rehydrated against first.

    Raises:
        VultronParseError: when the snapshot is not a parseable AS2 activity,
            which ADR-0140 item 2 rules out for every ledger payload.
    """
    activity = parse_activity(dict(payload_snapshot))
    if dl is not None:
        rehydrated = rehydrate(activity, dl)
        assert isinstance(rehydrated, as_Activity)
        activity = rehydrated
    return find_matching_semantics(activity).value


def label_mismatch(
    semantic_type: str,
    payload_snapshot: Mapping[str, Any],
    dl: DataLayer | None = None,
) -> str | None:
    """Why *semantic_type* is not the registry's label for the payload, or ``None``.

    An unparseable payload is a mismatch too, described rather than raised,
    so a caller collects every one before it fails (EH-07-001).
    """
    try:
        label = registry_label(payload_snapshot, dl)
    except Exception as exc:  # noqa: BLE001 — reported, not raised
        label = f"<unparseable: {type(exc).__name__}: {exc}>"
    if label == semantic_type:
        return None
    return (
        f"semantic type {semantic_type!r}, but the registry labels"
        f" its {payload_snapshot.get('type')!r} payload {label!r}"
    )


def label_mismatches(
    entries: Iterable[CaseLedgerEntry], dl: DataLayer | None = None
) -> list[str]:
    """One message per entry whose ``semantic_type`` is not its registry label.

    *dl* is passed to :func:`label_mismatch` for each entry.
    """
    return [
        f"case '{entry.case_id}' entry {entry.log_index}: {reason}"
        for entry in entries
        if (
            reason := label_mismatch(
                entry.semantic_type, entry.payload_snapshot, dl
            )
        )
        is not None
    ]


__all__ = ["label_mismatch", "label_mismatches", "registry_label"]
