"""Tests for CoreObject base class and CORE_VOCABULARY registry."""

from typing import Literal

import pytest
from pydantic import BaseModel

from vultron.core.models import (
    CORE_VOCABULARY,
    CoreObject,
    VultronObject,
    find_in_core_vocabulary,
)
from vultron.core.models.base import VultronBase
from vultron.core.models.case import VultronCase
from vultron.core.models.note import VultronNote
from vultron.core.models.report import VultronReport

# --- Inheritance shape ------------------------------------------------------


def test_core_object_inherits_vultron_object():
    assert issubclass(CoreObject, VultronObject)
    assert issubclass(CoreObject, VultronBase)
    assert issubclass(CoreObject, BaseModel)


def test_core_object_has_required_as2_fields():
    """AC-2: CoreObject must carry the AS2 fields the domain needs."""
    fields = set(CoreObject.model_fields.keys())
    for required in (
        "id_",
        "type_",
        "name",
        "attributed_to",
        "published",
        "updated",
        "context_",
    ):
        assert (
            required in fields
        ), f"CoreObject missing required field {required!r}"


def test_core_object_default_instance():
    obj = CoreObject()
    assert obj.id_.startswith("urn:uuid:")
    # Bare CoreObject is treated as concrete by the type-from-classname validator.
    assert obj.type_ == "CoreObject"
    # context_ is a wire concern and defaults to None on the domain side.
    assert obj.context_ is None
    assert obj.published is not None
    assert obj.updated is not None


def test_core_object_context_alias_serializes_as_at_context():
    obj = CoreObject.model_validate(
        {"@context": "https://www.w3.org/ns/activitystreams"}
    )
    assert obj.context_ == "https://www.w3.org/ns/activitystreams"
    dumped = obj.model_dump(by_alias=True, exclude_none=True)
    assert "@context" in dumped
    assert dumped["@context"] == "https://www.w3.org/ns/activitystreams"
    assert "context_" not in dumped


def test_core_object_context_empty_string_rejected():
    """NonEmptyString rule applies to context_ too."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        CoreObject.model_validate({"@context": ""})


# --- CORE_VOCABULARY registration ------------------------------------------


@pytest.fixture
def isolated_vocab():
    """Snapshot CORE_VOCABULARY around a test, restoring it after."""
    snapshot = dict(CORE_VOCABULARY)
    try:
        yield
    finally:
        CORE_VOCABULARY.clear()
        CORE_VOCABULARY.update(snapshot)


def test_concrete_subclass_registers(isolated_vocab):
    class CoreVocabFixtureConcrete(CoreObject):
        type_: Literal["CoreVocabFixtureConcrete"] = "CoreVocabFixtureConcrete"

    assert "CoreVocabFixtureConcrete" in CORE_VOCABULARY
    assert (
        CORE_VOCABULARY["CoreVocabFixtureConcrete"] is CoreVocabFixtureConcrete
    )
    assert find_in_core_vocabulary("CoreVocabFixtureConcrete") is (
        CoreVocabFixtureConcrete
    )


def test_subclass_without_type_override_does_not_register(isolated_vocab):
    class CoreVocabFixtureAbstract(CoreObject):
        pass

    assert "CoreVocabFixtureAbstract" not in CORE_VOCABULARY


def test_subclass_with_union_type_override_does_not_register(isolated_vocab):
    class CoreVocabFixtureUnion(CoreObject):
        # Optional[str] — an abstract intermediate base, must not register.
        type_: str | None = None

    assert "CoreVocabFixtureUnion" not in CORE_VOCABULARY


def test_registry_key_is_class_name_verbatim(isolated_vocab):
    """Core uses wire-style names with no prefix; key must equal __name__."""

    class VulnerabilityCaseRegistryProbe(CoreObject):
        type_: Literal["VulnerabilityCaseRegistryProbe"] = (
            "VulnerabilityCaseRegistryProbe"
        )

    assert "VulnerabilityCaseRegistryProbe" in CORE_VOCABULARY
    # No "as_" or other prefix stripping.
    assert "CaseRegistryProbe" not in CORE_VOCABULARY


def test_find_in_core_vocabulary_raises_on_unknown():
    with pytest.raises(KeyError):
        find_in_core_vocabulary("ThisTypeDoesNotExist")


def test_registry_robust_under_future_annotations(tmp_path, isolated_vocab):
    """Regression: PEP 563 string annotations must not bypass the union skip.

    Under ``from __future__ import annotations``, raw entries in
    ``__annotations__`` are strings, so inspecting them with
    ``isinstance(..., types.UnionType)`` falsely registers abstract
    intermediate bases.  The implementation must resolve annotations
    via ``typing.get_type_hints`` (which uses the class's module
    globals) instead of pattern-matching the raw annotation values.

    The check has to run in a real importable module — the
    ``__future__`` directive only takes effect at compile time on a
    proper module, and ``typing.get_type_hints`` needs the class's
    ``__module__`` to point at a module whose globals contain
    ``Literal``.
    """
    import importlib
    import sys
    import textwrap

    module_dir = tmp_path / "future_annot_pkg"
    module_dir.mkdir()
    (module_dir / "__init__.py").write_text("")
    (module_dir / "fixtures.py").write_text(textwrap.dedent("""
            from __future__ import annotations
            from typing import Literal
            from vultron.core.models import CoreObject

            class FutureAnnotAbstract(CoreObject):
                type_: str | None = None

            class FutureAnnotConcrete(CoreObject):
                type_: Literal["FutureAnnotConcrete"] = "FutureAnnotConcrete"
            """))
    sys.path.insert(0, str(tmp_path))
    try:
        mod = importlib.import_module("future_annot_pkg.fixtures")
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("future_annot_pkg.fixtures", None)
        sys.modules.pop("future_annot_pkg", None)

    assert "FutureAnnotAbstract" not in CORE_VOCABULARY
    assert "FutureAnnotConcrete" in CORE_VOCABULARY
    assert CORE_VOCABULARY["FutureAnnotConcrete"] is mod.FutureAnnotConcrete


# --- AC-4: legacy Vultron* stubs are untouched ------------------------------


def test_legacy_vultron_stubs_do_not_inherit_core_object():
    """AC-4: existing Vultron* core stubs are not migrated yet.

    They must still inherit from VultronObject (not CoreObject), and
    therefore must not appear in CORE_VOCABULARY.
    """
    for cls in (VultronCase, VultronReport, VultronNote):
        assert issubclass(cls, VultronObject)
        assert not issubclass(cls, CoreObject), (
            f"{cls.__name__} prematurely inherits CoreObject; "
            "issue #724 AC-4 forbids migrating legacy stubs in this change."
        )
        assert cls.__name__ not in CORE_VOCABULARY
