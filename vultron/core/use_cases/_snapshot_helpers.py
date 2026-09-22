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

"""Canonical payload-snapshot construction for case ledger entries.

Split out of ``_helpers.py`` (#3515), which had grown past the CS-18-001 500-line
cap by holding two unrelated concerns.  This is the self-contained one: building
the AS2-shaped, self-inlining ``payloadSnapshot`` that CLP-07-001 defines and
CLP-07-006 requires to carry full nested objects rather than bare ID strings.

``_helpers.py`` re-exports everything here, so no caller needs to change its
import.  Kept private to the use-cases package (``_`` prefix) for the same reason
``_helpers`` is.

Specs: CLP-07-001, CLP-07-006, ARCH-20-001.
"""

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vultron.core.ports.wire_render import WireRenderPort

from vultron.core.models._helpers import _as_id
from vultron.core.models.wire_keys import wire_keys
from vultron.core.ports.case_persistence import CasePersistence

logger = logging.getLogger(__name__)


#: Core field names whose values are object references that a canonical payload
#: snapshot inlines (CLP-07-006).
_SNAPSHOT_REFERENCE_CORE_FIELDS = (
    "object",
    "object_",
    "target",
    "active_embargo",
    "proposed_embargoes",
    "vulnerability_reports",
    "notes",
    "case_participants",
    "case_statuses",
)

#: The same fields under both spellings, because the snapshot being walked may
#: have come from either serialization: the wire render port produces AS2 keys,
#: a plain core ``model_dump`` produces Python field names.  The AS2 spelling is
#: *derived* from the core name by :func:`wire_key` rather than written out
#: here — core code must not type an AS2 spelling (ADR-0099 detail 2).
_SNAPSHOT_REFERENCE_FIELDS = set(_SNAPSHOT_REFERENCE_CORE_FIELDS) | set(
    wire_keys(_SNAPSHOT_REFERENCE_CORE_FIELDS)
)
_SNAPSHOT_INLINE_DEPTH_LIMIT = 8


def _inline_snapshot_reference_value(
    value: Any,
    dl: CasePersistence | None,
    *,
    should_resolve_strings: bool,
    resolving_ids: set[str],
    expected_context: str | None,
    depth: int,
    wire_render_port: "WireRenderPort | None" = None,
) -> Any:
    """Inline nested AS2 object references for canonical payload snapshots."""
    if depth > _SNAPSHOT_INLINE_DEPTH_LIMIT:
        return value

    if isinstance(value, dict):
        inlined: dict[str, Any] = {}
        for key, child in value.items():
            inlined[key] = _inline_snapshot_reference_value(
                child,
                dl,
                should_resolve_strings=(key in _SNAPSHOT_REFERENCE_FIELDS),
                resolving_ids=resolving_ids,
                expected_context=expected_context,
                depth=depth + 1,
                wire_render_port=wire_render_port,
            )
        return inlined

    if isinstance(value, list):
        return [
            _inline_snapshot_reference_value(
                item,
                dl,
                should_resolve_strings=should_resolve_strings,
                resolving_ids=resolving_ids,
                expected_context=expected_context,
                depth=depth + 1,
                wire_render_port=wire_render_port,
            )
            for item in value
        ]

    if (
        not should_resolve_strings
        or dl is None
        or not isinstance(value, str)
        or value in resolving_ids
    ):
        return value

    resolved = dl.read(value)
    if resolved is None or not hasattr(resolved, "model_dump"):
        return value
    resolved_context = _as_id(getattr(resolved, "context", None))
    if (
        expected_context is None
        or resolved_context is None
        or resolved_context != expected_context
    ):
        return value

    resolving_ids.add(value)
    try:
        if wire_render_port is not None:
            dumped = wire_render_port.render(resolved)
        else:
            # ARCH-20-001: the port is the sanctioned route and is used whenever
            # it is injected.  This fallback runs only when no port was supplied
            # — CLI and replay paths — and the object being dumped is being
            # inlined into a payload snapshot, which CLP-07-001 defines as
            # AS2-shaped.  It is the weakest of the seven remaining call sites:
            # ``resolved`` comes from the DataLayer and may be a core-branch
            # object, in which case this *is* core producing a wire shape for
            # one.  It survives only because there is no port to ask; collapsing
            # the rendering port (ADR-0099 Migration) removes the branch.
            dumped = resolved.model_dump(
                mode="json",
                by_alias=True,
                serialize_as_any=True,
                exclude_none=True,
            )
        return _inline_snapshot_reference_value(
            dumped,
            dl,
            should_resolve_strings=False,
            resolving_ids=resolving_ids,
            expected_context=expected_context,
            depth=depth + 1,
            wire_render_port=wire_render_port,
        )
    finally:
        resolving_ids.remove(value)


def build_activity_payload_snapshot(
    activity: Any,
    dl: CasePersistence | None = None,
    wire_render_port: "WireRenderPort | None" = None,
) -> dict[str, Any]:
    """Return a normalized, self-contained payload snapshot for ledger entries.

    If a DataLayer is provided, known nested object-reference fields are inlined
    from storage so canonical CaseLedgerEntry snapshots do not carry bare ID
    strings for protocol-significant nested objects.
    """
    if activity is None or not hasattr(activity, "model_dump"):
        return {}

    # ARCH-20-001 permits this ``by_alias=True``: *activity* is the inbound
    # activity being captured, and the result is the ledger payload snapshot,
    # which CLP-07-001 defines as the AS2 serialization of what arrived.  The
    # AS2 shape is the requirement here, not an accident of the dump.
    snapshot: dict[str, Any] = activity.model_dump(
        mode="json",
        by_alias=True,
        serialize_as_any=True,
        exclude_none=True,
    )
    expected_context = snapshot.get("context")
    if not isinstance(expected_context, str):
        expected_context = None
    inlined = _inline_snapshot_reference_value(
        snapshot,
        dl,
        should_resolve_strings=False,
        resolving_ids=set(),
        expected_context=expected_context,
        depth=0,
        wire_render_port=wire_render_port,
    )
    return inlined if isinstance(inlined, dict) else {}
