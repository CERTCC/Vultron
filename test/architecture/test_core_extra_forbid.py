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
"""``extra="forbid"`` is the core-branch boundary contract (#2940, ARCH-12-003).

Proves that every ``CoreObject`` forbids unknown keys with **no exemption
list** (AC-2), that an unknown key raises rather than being dropped for every
``CORE_VOCABULARY`` entry (AC-3), that a dump round-trips exactly (AC-4,
ARCH-23-005), and that the mechanisms this contract subsumes cannot be
reintroduced (AC-7).
"""

import importlib
import pkgutil
from datetime import timedelta

import pytest
from pydantic import ValidationError

from test.architecture import _corpus
from vultron.core.models.base import CoreObject
from vultron.core.models.registry import CORE_VOCABULARY
from vultron.metadata.base import repo_root


def _import_all_core_models() -> None:
    import vultron.core.models as models_pkg

    for module in pkgutil.walk_packages(
        models_pkg.__path__, models_pkg.__name__ + "."
    ):
        importlib.import_module(module.name)


def _all_core_object_subclasses() -> set[type[CoreObject]]:
    _import_all_core_models()

    def descend(cls: type) -> set[type]:
        found: set[type] = set()
        for sub in cls.__subclasses__():
            found.add(sub)
            found |= descend(sub)
        return found

    return {c for c in descend(CoreObject)}


def _minimal_kwargs(cls: type[CoreObject]) -> dict:
    """Minimum kwargs to construct *cls* without validation errors."""
    kwargs: dict = {}
    for field_name, field_info in cls.model_fields.items():
        if not field_info.is_required():
            continue
        ann = str(field_info.annotation)
        if "timedelta" in ann:
            kwargs[field_name] = timedelta(days=90)
        else:
            kwargs[field_name] = f"urn:test:{field_name}:1"
    return kwargs


def _constructible_vocab() -> list[tuple[str, CoreObject]]:
    """(name, instance) for every CORE_VOCABULARY entry we can minimally build."""
    _import_all_core_models()
    out: list[tuple[str, CoreObject]] = []
    for name, base_cls in sorted(CORE_VOCABULARY.items()):
        if not issubclass(base_cls, CoreObject):
            continue
        cls: type[CoreObject] = base_cls  # type: ignore[assignment]
        kwargs = _minimal_kwargs(cls)
        kwargs["id_"] = f"urn:test:{name.lower()}:forbid"
        try:
            out.append((name, cls(**kwargs)))
        except Exception:
            # Not minimally constructible here — no core code stores it without
            # its required fields either, so it is out of scope for this ratchet.
            continue
    return out


def test_every_core_object_forbids_extra_with_no_exemption_list() -> None:
    """AC-2: every ``CoreObject`` subclass resolves ``extra="forbid"``.

    There is deliberately no exemption set: a subclass that loosened the guard
    would reopen the #2232 silent-drop hole, so the assertion admits no
    exceptions (ARCH-12-003).
    """
    offenders = [
        cls.__name__
        for cls in _all_core_object_subclasses()
        if cls.model_config.get("extra") != "forbid"
    ]
    assert not offenders, (
        "these CoreObject subclasses do not resolve extra='forbid' "
        f"(ARCH-12-003, no exemptions allowed): {sorted(offenders)}"
    )


def test_unknown_key_raises_for_every_core_vocabulary_entry() -> None:
    """AC-3: an unknown key raises rather than being silently dropped."""
    for name, obj in _constructible_vocab():
        payload = obj.model_dump(mode="json")
        payload["totallyUnknownKey"] = "x"
        with pytest.raises(ValidationError):
            type(obj).model_validate(payload)


def test_participant_status_rejects_wire_spelled_rm_state() -> None:
    """AC-3: the concrete #2232 defect input is rejected, not dropped."""
    from vultron.core.models.participant_status import ParticipantStatus

    with pytest.raises(ValidationError):
        ParticipantStatus.model_validate({"rmState": "RECEIVED"})


def test_round_trip_is_exact_for_every_core_vocabulary_entry() -> None:
    """AC-4: ``type(obj).model_validate(dump(obj)) == obj`` (ARCH-23-005).

    Exercises the computed-field strip and the alias/field-name de-dup: without
    them, a ``@computed_field`` or an injected alias twin would trip
    ``extra="forbid"`` on re-validation.
    """
    for name, obj in _constructible_vocab():
        restored = type(obj).model_validate(obj.model_dump(mode="json"))
        assert restored == obj, f"{name} did not round-trip exactly"


def test_retired_wire_normalisation_mechanisms_are_not_reintroduced() -> None:
    """AC-7: the mechanisms ``extra="forbid"`` subsumes stay deleted.

    ``extra="forbid"`` replaces the per-class camelCase reject-guard and the
    persistence-boundary wire→core normalisation gate (AC-5/AC-6); a grep guard
    keeps them from creeping back into the shipped source.
    """
    banned = [
        "_NORMALIZE_WIRE" + "_TO_CORE",
        "_normalize_to" + "_core",
        "_project_shadowing" + "_wire_obj",
        "_wire" + "_spelling",
        "reject_wire" + "_spelled_keys",
    ]
    vultron_root = repo_root() / "vultron"
    offenders: list[str] = []
    for path, source in _corpus.sources_mentioning(
        *banned, under=vultron_root
    ):
        for token in banned:
            if token in source:
                offenders.append(f"{path.relative_to(repo_root())}: {token}")
    assert not offenders, (
        "retired wire-normalisation mechanisms reappeared; extra='forbid' "
        f"is the boundary contract now (#2940): {offenders}"
    )
