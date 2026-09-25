"""Tests for CoreObject base class and CORE_VOCABULARY registry."""

import importlib.util
import pathlib
import tokenize
from typing import Literal

import pytest
from pydantic import BaseModel

import vultron

from vultron.core.models import (
    CORE_VOCABULARY,
    CoreObject,
    find_in_core_vocabulary,
)
from vultron.core.models.base import VULTRON_CONTEXT_URI, CoreRecord
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import (
    CaseLedgerEntry as CoreCaseLedgerEntry,
)
from vultron.core.models.note import VultronNote
from vultron.core.models.activity import VultronActivity
from vultron.core.models.report import VulnerabilityReport
from vultron.core.models.vulnerability_record import VulnerabilityRecord

# --- Inheritance shape ------------------------------------------------------


def test_core_object_extends_the_core_record_root():
    assert issubclass(CoreObject, CoreRecord)
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
    # The bare root is the extractor's minimal reference: its type is the
    # referenced object's, so the class name is never invented for it.
    assert obj.type_ is None
    assert CoreObject(type_="Invite").type_ == "Invite"
    # context_ is a wire concern and defaults to None on the domain side.
    assert obj.context_ is None
    assert obj.published is not None
    assert obj.updated is not None


def test_core_object_context_is_emitted_on_the_as2_path_only():
    """@context appears on the AS2 dump and not on the persistence dump.

    ADR-0099 detail 1 gives one class two serializations, chosen by destination:
    ``by_alias=True`` is inter-actor delivery (camelCase plus ``@context``), a
    plain dump is persistence (Python field names, no ``@context``).  ``context_``
    stays ``exclude=True`` so a stored row never carries it, which is what lets
    core objects round-trip through the DataLayer.

    This previously asserted ``@context`` was absent from *both*.  That held only
    while a paired ``as_*`` class supplied it; deleting those classes took the
    Vultron context off every promoted type and left the AS2 namespace alone on
    the wire, which VM-10-001 (MUST) says "is not sufficient".
    """
    obj = CoreObject.model_validate(
        {"@context": "https://www.w3.org/ns/activitystreams"}
    )
    assert obj.context_ == "https://www.w3.org/ns/activitystreams"

    # Delivery form: the supplied context wins, so a document round-trips with
    # the context it arrived carrying rather than being relabelled.
    as2 = obj.model_dump(by_alias=True, exclude_none=True)
    assert as2["@context"] == "https://www.w3.org/ns/activitystreams"

    # Persistence form: neither the alias nor the field name is stored.
    stored = obj.model_dump(exclude_none=True)
    assert "@context" not in stored
    assert "context_" not in stored


def test_core_object_context_defaults_to_the_vultron_uri_on_the_wire():
    """An object carrying no context still declares the Vultron one.

    VM-10-001 requires it on Vultron-specific types; the ActivityStreams
    namespace alone is not sufficient for types AS2 does not define.
    """
    as2 = CoreObject().model_dump(by_alias=True, exclude_none=True)
    assert as2["@context"] == VULTRON_CONTEXT_URI


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


# --- ADR-0099 detail 4: AS2-shaped stubs sit on the one AS2 root -----------


def test_as2_shaped_vultron_stubs_are_core_objects():
    """``VultronNote`` and the ``VultronActivity`` family carry AS2 object
    fields, so they extend ``CoreObject`` — the one AS2 object root — rather
    than the retired middle level (ADR-0099 detail 4)."""
    for cls in (VultronNote, VultronActivity):
        assert issubclass(cls, CoreObject)


# --- AC-1/#727: migrated types inherit CoreObject ---------------------------


def test_vulnerability_report_inherits_core_object():
    """VulnerabilityReport (migrated in #727) must be a CoreObject subclass."""
    assert issubclass(VulnerabilityReport, CoreObject)
    assert "VulnerabilityReport" in CORE_VOCABULARY
    assert CORE_VOCABULARY["VulnerabilityReport"] is VulnerabilityReport


def test_vulnerability_record_inherits_core_object():
    """VulnerabilityRecord (new in #727) must be a CoreObject subclass."""
    assert issubclass(VulnerabilityRecord, CoreObject)
    assert "VulnerabilityRecord" in CORE_VOCABULARY
    assert CORE_VOCABULARY["VulnerabilityRecord"] is VulnerabilityRecord


def test_core_case_ledger_entry_inherits_core_object():
    """CaseLedgerEntry from case_ledger_entry (migrated in #727) must be a CoreObject
    subclass.
    """
    assert issubclass(CoreCaseLedgerEntry, CoreObject)
    assert "CaseLedgerEntry" in CORE_VOCABULARY
    assert CORE_VOCABULARY["CaseLedgerEntry"] is CoreCaseLedgerEntry


def test_vulnerability_case_inherits_core_object():
    """VulnerabilityCase (migrated in #729) must be a CoreObject subclass."""
    assert issubclass(VulnerabilityCase, CoreObject)
    assert "VulnerabilityCase" in CORE_VOCABULARY
    assert CORE_VOCABULARY["VulnerabilityCase"] is VulnerabilityCase


_RETIRED_CORE_ALIASES = frozenset(
    {
        # #3431
        "VultronCase",
        "VultronCaseLedgerEntry",
        "VultronCaseLedgerEntryRef",
        # #3678
        "VultronCaseActor",
        "VultronReport",
        "VultronEmbargoEvent",
        "VultronParticipant",
    }
)


@pytest.mark.parametrize(
    ("module_name", "alias"),
    [
        # #3431
        ("vultron.core.models.case", "VultronCase"),
        ("vultron.core.models.case_ledger_entry", "VultronCaseLedgerEntry"),
        ("vultron.core.models.case_ledger_entry", "VultronCaseLedgerEntryRef"),
        (
            "vultron.wire.as2.vocab.objects.case_ledger_entry",
            "VultronCaseLedgerEntry",
        ),
        (
            "vultron.wire.as2.vocab.objects.case_ledger_entry",
            "VultronCaseLedgerEntryRef",
        ),
        # #3678
        ("vultron.core.models.case_actor", "VultronCaseActor"),
        ("vultron.core.models.report", "VultronReport"),
        ("vultron.core.models.embargo_event", "VultronEmbargoEvent"),
        ("vultron.core.models.case_participant", "VultronParticipant"),
        (
            "vultron.wire.as2.vocab.objects.case_participant",
            "VultronParticipant",
        ),
    ],
)
def test_retired_core_alias_is_gone_from_its_old_home(module_name, alias):
    """Retired ``Vultron``-prefixed aliases are not re-exported (#3431, #3678).

    Each was an assignment alias of its canonical class, never a distinct type,
    so an ``isinstance`` check against the alias could not fail and the
    re-coercion branch it guarded was unreachable. CS-15-001 forbids keeping
    them to spare call sites; this pins that the module that defined each one
    no longer does.
    """
    assert alias in _RETIRED_CORE_ALIASES
    module = importlib.import_module(module_name)
    assert not hasattr(module, alias), f"{module_name}.{alias}"


@pytest.mark.parametrize(
    "module_name",
    ["vultron.core.models.vultron_types", "vultron.core.models.participant"],
)
def test_retired_core_model_shim_modules_are_gone(module_name):
    """The re-export shim modules are deleted, not emptied (#3678, CS-15-001)."""
    assert importlib.util.find_spec(module_name) is None


def test_no_source_module_names_a_retired_core_alias():
    """No identifier anywhere under ``vultron/`` spells a retired alias.

    The per-module checks above catch a re-added definition in its old home;
    this catches one re-introduced anywhere else, or a stale reference.
    """
    package_root = pathlib.Path(vultron.__file__).parent
    offenders = []
    for path in sorted(package_root.rglob("*.py")):
        with path.open("rb") as handle:
            for token in tokenize.tokenize(handle.readline):
                if (
                    token.type == tokenize.NAME
                    and token.string in _RETIRED_CORE_ALIASES
                ):
                    offenders.append(
                        f"{path}:{token.start[0]}: {token.string}"
                    )
    assert offenders == []


# ---------------------------------------------------------------------------
# #2940 cleanup #1 — strip computed-field inputs before re-validation
# ---------------------------------------------------------------------------


def test_core_object_strips_computed_field_input():
    """Cleanup #1: a ``@computed_field`` value in the payload is dropped.

    ``ParticipantStatus.embargo_adherence`` is computed (ADR-0056) and appears
    in ``model_dump()`` output but is not settable.  Under ``extra="forbid"``
    it would be rejected on re-validation unless stripped first; the value is
    re-derived from ``consent``, never taken from the injected key.
    """
    from vultron.core.models.dimensions import PecDimension
    from vultron.core.models.participant_status import ParticipantStatus
    from vultron.core.states.participant_embargo_consent import PEC

    # UNBOUND → not signatory → False, which is what the payload also says, so
    # the redundant key is simply stripped.
    status = ParticipantStatus.model_validate(
        {
            "context": "urn:uuid:case-computed-strip",
            "consent": PecDimension(state=PEC.UNBOUND).model_dump(mode="json"),
            "embargo_adherence": False,
        }
    )
    assert status.embargo_adherence is False

    # And a full dump round-trips (the computed key in the dump is stripped).
    assert ParticipantStatus.model_validate(
        status.model_dump(mode="json")
    ) == (status)

    # Including the camelCase spelling, which is the AS2 wire form every core
    # class emits (ADR-0099 detail 2).  Compared by dump, not ``==``: the wire
    # dump carries ``@context``, and a parsed document keeps it in ``context_``
    # (detail 1), which the locally built ``status`` never set.
    assert (
        ParticipantStatus.model_validate(
            status.model_dump(mode="json", by_alias=True)
        ).model_dump()
        == status.model_dump()
    )


# ---------------------------------------------------------------------------
# #2940 cleanup #3 — drop an alias key's field-name twin
# ---------------------------------------------------------------------------


def test_core_object_drops_alias_shadowed_field_name_twin():
    """Cleanup #3: an alias key beside its field-name twin does not trip forbid.

    ``CaseLedgerEntry._set_id_from_case`` injects the ``id`` alias into a
    payload that already carries the ``id_`` field-name key (from a dump).
    Without the de-dup validator the leftover ``id_`` is an unknown key under
    ``extra="forbid"``; the alias (carrying the derived value) must win.
    """
    entry = CoreCaseLedgerEntry(
        case_id="urn:uuid:case-dedup",
        log_object_id="urn:uuid:logobj-dedup",
        event_type="RS",
    )
    dumped = entry.model_dump(mode="json")
    assert "id_" in dumped  # the dump uses the Python field name
    # Re-validating triggers _set_id_from_case (injects "id") beside "id_".
    restored = CoreCaseLedgerEntry.model_validate(dumped)
    assert restored == entry

    # Direct both-keys payload: the field-name twin is dropped, alias wins.
    both = dict(dumped)
    both["id"] = dumped["id_"]
    assert CoreCaseLedgerEntry.model_validate(both) == entry


def test_case_ledger_entry_derives_id_from_wire_spelled_coordinates():
    """An entry parsed off the wire carries ``caseId``/``logIndex``.

    The derivation must read those too, or a wire-parsed entry keeps a random
    id instead of its ``{case_id}/log/{log_index}`` coordinates.
    """
    entry = CoreCaseLedgerEntry.model_validate(
        {
            "caseId": "urn:uuid:case-wire",
            "logIndex": 3,
            "logObjectId": "urn:uuid:logobj-wire",
            "eventType": "RS",
        }
    )
    assert entry.id_ == "urn:uuid:case-wire/log/3"


# --- #3578 AC-5/AC-6: AS2 envelope spelling on every core vocabulary entry ---

_ENVELOPE_SPELLING = {
    "media_type": "mediaType",
    "start_time": "startTime",
    "end_time": "endTime",
    "attributed_to": "attributedTo",
    "in_reply_to": "inReplyTo",
}


def test_every_core_vocabulary_entry_spells_the_as2_envelope_in_camel_case():
    """Each ``CORE_VOCABULARY`` entry dumps the shared AS2 envelope fields in
    AS2 camelCase, not snake_case (#3578 AC-5).

    Before the alias generator reached every core object (ADR-0099 detail 2),
    ten classes — ``CaseParticipant``, ``CaseActor`` and ``CaseReference``
    among them — dumped ``media_type`` / ``start_time`` / ``end_time`` /
    ``attributed_to`` verbatim.
    """
    from datetime import datetime, timezone

    from test.support.core_vocab import build_core_vocab

    when = datetime(2026, 1, 2, tzinfo=timezone.utc)
    built, unconstructible = build_core_vocab(
        "envelope",
        {
            "media_type": "text/plain",
            "start_time": when,
            "end_time": when,
            "attributed_to": "urn:test:attributed-to:1",
            "in_reply_to": "urn:test:in-reply-to:1",
        },
    )
    assert not unconstructible, unconstructible
    misspelled = {
        name: sorted(
            field
            for field, camel in _ENVELOPE_SPELLING.items()
            if camel not in dumped or field in dumped
        )
        for name, obj in built
        if (dumped := obj.model_dump(by_alias=True, exclude_none=True))
    }
    misspelled = {name: bad for name, bad in misspelled.items() if bad}
    assert not misspelled, f"non-AS2 envelope spelling: {misspelled}"
