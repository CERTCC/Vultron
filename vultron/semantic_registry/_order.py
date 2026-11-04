"""Import-time order guard for the semantic registry (SE-03-002).

A pattern that is less specific than a later one in the same ``activity_``
group would shadow it: ``find_matching_semantics()`` returns the first match.
``_validate_registry_order`` refuses such an ordering when the registry is
assembled.
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

from itertools import combinations
from typing import Any

from vultron.errors import RegistryOrderError
from vultron.semantic_registry._entry import SemanticEntry
from vultron.wire.as2.extractor._pattern import (
    ActivityPattern,
    InlineActivityObjectPattern,
)


def _strip_description(d: dict[str, Any]) -> dict[str, Any]:
    """Recursively remove ``description`` keys from a pattern dump dict.

    ``ActivityPattern.description`` is a documentation annotation, not a
    semantic constraint.  Removing it at all levels ensures subset comparisons
    reflect only the fields that actually influence pattern matching.
    """
    result: dict[str, Any] = {}
    for k, v in d.items():
        if k == "description":
            continue
        if isinstance(v, dict):
            result[k] = _strip_description(v)
        else:
            result[k] = v
    return result


def _elem_matches(a: Any, b: Any) -> bool:
    """Return True if element *a* can be covered by element *b*.

    Dicts: every key/value in *a* must appear in *b* (recursive).
    Lists: every element in *a* must match some element in *b*.
    Scalars: equality.
    """
    if isinstance(a, dict) and isinstance(b, dict):
        return _is_subset(a, b)
    if isinstance(a, list) and isinstance(b, list):
        return all(
            any(_elem_matches(item_a, item_b) for item_b in b) for item_a in a
        )
    return bool(a == b)


def _is_subset(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """Return True if *a* is a subset of *b* — every key/value in *a* is
    present in *b* (recursively).  Extra keys in *b* are ignored."""
    if not set(a.keys()).issubset(b.keys()):
        return False
    return all(_elem_matches(a[k], b[k]) for k in a)


def _check_group_order(
    act_type: str, indexed_entries: list[tuple[int, SemanticEntry]]
) -> None:
    """Check ordering for one ``activity_`` group; raise ``RegistryOrderError``
    if a less-specific entry precedes a more-specific one."""
    enriched: list[tuple[int, SemanticEntry, dict[str, Any]]] = []
    for idx, entry in indexed_entries:
        if entry.pattern is None:
            continue
        try:
            dump = _strip_description(
                entry.pattern.model_dump(exclude_none=True)
            )
            enriched.append((idx, entry, dump))
        except Exception:  # noqa: BLE001, S112  # ruff-baseline #3326
            continue

    for (idx_a, entry_a, dump_a), (idx_b, entry_b, dump_b) in combinations(
        enriched, 2
    ):
        # idx_a < idx_b by construction (combinations preserves order).
        # If dump_a ⊂ dump_b strictly, then a is less specific but appears
        # first — the more-specific b would never be reached.
        if _is_subset(dump_a, dump_b) and not _is_subset(dump_b, dump_a):
            raise RegistryOrderError(
                f"Registry ordering violation in '{act_type}' group: "
                f"{entry_a.semantics.name!r} (index {idx_a}) is less specific "
                f"than {entry_b.semantics.name!r} (index {idx_b}) but appears "
                f"first. Move {entry_b.semantics.name!r} before "
                f"{entry_a.semantics.name!r}."
            )


def _check_inline_activity_order(registry: list[SemanticEntry]) -> None:
    """Raise if an entry an inline-activity catch-all would shadow follows it.

    An :class:`InlineActivityObjectPattern` matches every inline activity of
    a verb it does not exclude, which the dump-subset comparison in
    :func:`_check_group_order` cannot see.  So any later entry of the same
    activity type whose object is a nested pattern of an included verb would
    never be reached (SE-03-002).

    Raises:
        RegistryOrderError: When such an entry follows the catch-all.
    """
    for idx, entry in enumerate(registry):
        catch_all = entry.pattern
        if not isinstance(catch_all, InlineActivityObjectPattern):
            continue
        excluded = {str(v) for v in catch_all.excluded_object_verbs}
        for later in registry[idx + 1 :]:
            pattern = later.pattern
            if (
                pattern is not None
                and pattern.activity_ == catch_all.activity_
                and isinstance(pattern.object_, ActivityPattern)
                and str(pattern.object_.activity_) not in excluded
            ):
                raise RegistryOrderError(
                    f"Registry ordering violation in"
                    f" '{catch_all.activity_}' group:"
                    f" {entry.semantics.name!r} takes every inline"
                    f" {pattern.object_.activity_} activity, so"
                    f" {later.semantics.name!r} after it is never reached."
                    f" Move {later.semantics.name!r} before"
                    f" {entry.semantics.name!r}."
                )


def _validate_registry_order(registry: list[SemanticEntry]) -> None:
    """Raise ``RegistryOrderError`` if any less-specific pattern precedes a
    more-specific one within the same ``activity_`` group.

    Called at module load time so that ordering violations are impossible to
    miss.  A pattern *A* is considered less specific than *B* when
    ``dump(A) ⊂ dump(B)`` strictly (A has fewer constraints than B).  When
    A appears before B in the registry, ``find_matching_semantics()`` would
    never reach B — the wrong use case would run silently.

    See ``vultron/wire/as2/AGENTS.md`` for the ordering invariant and
    ``specs/semantic-extraction.yaml`` SE-03-002.

    Args:
        registry: Ordered ``SemanticEntry`` list to validate.

    Raises:
        RegistryOrderError: When a more-specific entry appears after a
            less-specific entry in the same ``activity_`` group.
    """
    groups: dict[str, list[tuple[int, SemanticEntry]]] = {}
    for idx, entry in enumerate(registry):
        if entry.pattern is None:
            continue
        act_type = str(entry.pattern.activity_)
        groups.setdefault(act_type, []).append((idx, entry))

    for act_type, indexed_entries in groups.items():
        if len(indexed_entries) >= 2:
            _check_group_order(act_type, indexed_entries)
    _check_inline_activity_order(registry)
