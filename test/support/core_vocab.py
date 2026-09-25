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

"""Build a minimal instance of every ``CORE_VOCABULARY`` entry.

Shared by the architecture ratchets that must cover *every* core vocabulary
entry (``extra="forbid"``, ``dl.read()`` round-trip) and by the rendering
port's golden test, so the "what is the least a core type needs" rule lives in
one place.
"""

import importlib
import pkgutil
from datetime import timedelta
from typing import Any

from vultron.core.models.base import CoreObject
from vultron.core.models.registry import CORE_VOCABULARY


def import_all_core_models() -> None:
    """Import every module under ``vultron.core.models`` so registries fill."""
    import vultron.core.models as models_pkg

    for module in pkgutil.walk_packages(
        models_pkg.__path__, models_pkg.__name__ + "."
    ):
        importlib.import_module(module.name)


def minimal_kwargs(cls: type[CoreObject]) -> dict[str, Any]:
    """Return the minimum kwargs to construct *cls* without validation errors."""
    kwargs: dict[str, Any] = {}
    for field_name, field_info in cls.model_fields.items():
        if not field_info.is_required():
            continue
        ann = str(field_info.annotation)
        if "timedelta" in ann:
            kwargs[field_name] = timedelta(days=90)
        else:
            kwargs[field_name] = f"urn:test:{field_name}:1"
    return kwargs


def build_core_vocab(
    id_suffix: str, extra: dict[str, Any] | None = None
) -> tuple[list[tuple[str, CoreObject]], dict[str, str]]:
    """Minimally construct every ``CoreObject`` entry of ``CORE_VOCABULARY``.

    Returns ``(built, unconstructible)``: ``built`` is ``(name, instance)`` in
    name order; ``unconstructible`` maps each entry that could not be built
    from synthesised kwargs to the reason.  Callers claiming coverage of every
    entry MUST assert on ``unconstructible`` rather than drop it silently.
    """
    import_all_core_models()
    built: list[tuple[str, CoreObject]] = []
    unconstructible: dict[str, str] = {}
    for name, base_cls in sorted(CORE_VOCABULARY.items()):
        if not issubclass(base_cls, CoreObject):
            continue
        kwargs = minimal_kwargs(base_cls)
        kwargs["id_"] = f"urn:test:{name.lower()}:{id_suffix}"
        kwargs.update(extra or {})
        try:
            built.append((name, base_cls(**kwargs)))
        except Exception as exc:  # noqa: PERF203
            unconstructible[name] = f"{type(exc).__name__}: {exc}"
    return built, unconstructible
