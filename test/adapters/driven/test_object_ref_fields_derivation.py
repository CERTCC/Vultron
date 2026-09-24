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
"""Object-reference field derivation replaces ``_AS_OBJECT_REF_FIELDS`` (#2936).

The former hand-maintained frozenset is now derived from the wire classes' own
type annotations. These tests prove the change is behaviour-preserving (AC-3)
and lock out reintroduction of the retired restatement (AC-4).
"""

import importlib
import pkgutil

from vultron.adapters.driven.db_record import (
    _activity_object_ref_properties,
    object_ref_fields,
)
from vultron.metadata.base import repo_root
from vultron.wire.as2.vocab.base.objects.base import as_Object

#: The set that ``_AS_OBJECT_REF_FIELDS`` held before #2936, kept here as the
#: fixed oracle the derivation must reproduce.
PREVIOUSLY_HARD_CODED = frozenset(
    {"object_", "target", "origin", "result", "instrument"}
)


def _all_wire_object_classes() -> set[type]:
    """Every ``as_Object`` subclass, with the whole vocab package imported."""
    import vultron.wire.as2.vocab as vocab_pkg

    for module in pkgutil.walk_packages(
        vocab_pkg.__path__, vocab_pkg.__name__ + "."
    ):
        importlib.import_module(module.name)

    def descend(cls: type) -> set[type]:
        found: set[type] = set()
        for sub in cls.__subclasses__():
            found.add(sub)
            found |= descend(sub)
        return found

    return descend(as_Object)


def test_derived_activity_properties_equal_previous_constant():
    """AC-3: the derived Activity ref-property set equals the old constant."""
    assert _activity_object_ref_properties() == PREVIOUSLY_HARD_CODED


def test_object_ref_fields_equal_previous_behaviour_for_every_wire_class():
    """AC-3: for every wire class, the derived set equals ``old ∩ fields``.

    This is the behaviour-preservation proof: the old flat constant was applied
    to every object as ``name in _AS_OBJECT_REF_FIELDS``, which is exactly the
    intersection of the constant with the class's own fields.
    """
    for cls in _all_wire_object_classes():
        expected = PREVIOUSLY_HARD_CODED & frozenset(cls.model_fields)
        assert object_ref_fields(cls) == expected, (
            f"{cls.__name__}: derived {object_ref_fields(cls)} != "
            f"behaviour-preserving {expected}"
        )


def test_object_ref_fields_is_cached_per_class():
    """AC-1: the per-class derivation is memoised (identical object returned)."""
    from vultron.wire.as2.vocab.base.objects.activities.transitive import (
        as_Create,
    )

    assert object_ref_fields(as_Create) is object_ref_fields(as_Create)


def test_narrowed_ref_is_still_named_but_guarded_at_runtime():
    """A model narrowing ``target`` to a URI still lists it (name-keyed)."""
    from vultron.wire.as2.vocab.objects.case_proposal import as_CaseProposal

    # ``target`` is narrowed to a plain URI on as_CaseProposal (CP-01-005) but
    # is still named here; field_admits_object is the runtime guard.
    assert "target" in object_ref_fields(as_CaseProposal)


def test_as_object_ref_fields_constant_is_not_reintroduced():
    """AC-4: the retired ``_AS_OBJECT_REF_FIELDS`` restatement cannot come back.

    Scans the shipped source tree. The one legitimate occurrence is the literal
    in this ratchet itself, which lives under ``test/`` and is excluded.
    """
    banned = "_AS_OBJECT_REF" + "_FIELDS"  # split so this test is not self-hit
    root = repo_root() / "vultron"
    offenders = [
        str(path.relative_to(repo_root()))
        for path in root.rglob("*.py")
        if banned in path.read_text(encoding="utf-8")
    ]
    assert not offenders, (
        f"{banned} is derived from annotations now (#2936); do not "
        f"reintroduce the hand-maintained restatement. Found in: {offenders}"
    )
