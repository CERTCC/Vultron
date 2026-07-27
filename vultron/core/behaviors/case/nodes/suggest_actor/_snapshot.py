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

"""Snapshot helpers shared by suggest-actor emit nodes and actor.py."""

from typing import Any

_INLINE_OBJECT_KEYS: frozenset[str] = frozenset(
    {"object", "object_", "target"}
)


def _drop_bare_inline_refs(value: Any) -> Any:
    """Recursively drop bare-string values for inline-object keys.

    ``_validate_canonical_entry`` rejects any ``object``, ``object_``, or
    ``target`` key whose value is a bare ID string.  This helper strips them
    from the snapshot dict before submission so that canonical entry validation
    does not reject valid activities whose factory serialisation left ``target``
    as a bare URI.
    """
    if isinstance(value, dict):
        return {
            k: _drop_bare_inline_refs(v)
            for k, v in value.items()
            if not (k in _INLINE_OBJECT_KEYS and isinstance(v, str))
        }
    if isinstance(value, list):
        return [_drop_bare_inline_refs(item) for item in value]
    return value


def _snapshot_with_context(
    activity_dict: dict[str, Any], case_id: str
) -> dict[str, Any]:
    """Return activity_dict with context set and bare-string inline refs dropped.

    Factory dicts use ``target=case_id`` (a bare string).
    ``_validate_canonical_entry`` rejects bare strings in inline-object fields,
    so we call ``_drop_bare_inline_refs`` and rely on ``context``
    (which we set here) to carry the case reference.
    """
    result = _drop_bare_inline_refs(activity_dict)
    if not isinstance(result, dict):
        result = dict(activity_dict)
    if not result.get("context"):
        result["context"] = case_id
    return result
