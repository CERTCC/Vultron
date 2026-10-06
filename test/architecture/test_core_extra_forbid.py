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

from datetime import UTC

import pytest
from pydantic import ValidationError

from test.architecture import _corpus
from test.support.core_vocab import build_core_vocab, import_all_core_models
from vultron.core.models.base import CoreObject
from vultron.core.models.registry import CORE_VOCABULARY
from vultron.errors import VultronProtocolViolationError
from vultron.metadata.base import repo_root


def _all_core_object_subclasses() -> set[type[CoreObject]]:
    import_all_core_models()

    def descend(cls: type) -> set[type]:
        found: set[type] = set()
        for sub in cls.__subclasses__():
            found.add(sub)
            found |= descend(sub)
        return found

    return {c for c in descend(CoreObject)}


def _constructible_vocab() -> list[tuple[str, CoreObject]]:
    """(name, instance) for every CORE_VOCABULARY entry we can minimally build."""
    return build_core_vocab("forbid")[0]


def test_every_core_vocabulary_entry_is_actually_exercised() -> None:
    """The AC-3/AC-4 ratchets must cover every CORE_VOCABULARY entry.

    Both iterate ``_constructible_vocab()``.  If a future core type gains a
    required field ``minimal_kwargs`` cannot synthesise, it would vanish from
    those loops and they would keep passing while checking less.  This makes
    that visible instead: extend ``minimal_kwargs`` (or state the exemption
    here deliberately) rather than letting coverage erode.
    """
    built, unconstructible = build_core_vocab("forbid")
    exercised = {name for name, _ in built}
    expected = {
        name
        for name, cls in CORE_VOCABULARY.items()
        if issubclass(cls, CoreObject)
    }
    missing = {
        n: unconstructible.get(n, "?") for n in sorted(expected - exercised)
    }
    assert exercised == expected, (
        'these CORE_VOCABULARY entries are not exercised by the extra="forbid" '
        f"ratchets: {missing}"
    )


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
    for _name, obj in _constructible_vocab():
        payload = obj.model_dump(mode="json")
        payload["totallyUnknownKey"] = "x"
        with pytest.raises(ValidationError):
            type(obj).model_validate(payload)


def test_participant_status_does_not_drop_wire_spelled_rm_state() -> None:
    """AC-3: the concrete #2232 defect — a lost RM ladder — cannot happen.

    #2232 was *silent loss*: ``rmState`` was discarded and ``rm.state`` fell
    back to ``RM.START`` with no error.  Two distinct outcomes prevent that, and
    this pins both so neither can regress into a drop:

    * ``rm_state``/``rmState`` are declared ``AliasChoices`` on the field, so the
      value is *interpreted* rather than dropped.  (Removing those aliases so the
      flat spellings raise instead is #2289; until then "rejected" is the wrong
      assertion — see ``notes/wire-core-boundary.md``.)
    * a spelling that is **not** an alias is rejected by ``extra="forbid"``.

    Note the required ``context`` is supplied deliberately: without it every
    input here raises on the missing field, so the test would pass while
    asserting nothing about wire spellings at all.
    """
    from vultron.core.models.participant_status import ParticipantStatus
    from vultron.core.states.rm import RM

    for spelling in ("rm_state", "rmState"):
        status = ParticipantStatus.model_validate(
            {"context": "urn:uuid:case-2232", spelling: "RECEIVED"}
        )
        assert status.rm.state == RM.RECEIVED, (
            f"{spelling} was dropped instead of interpreted — the #2232 "
            "silent-loss defect"
        )

    # A non-alias wire spelling has nowhere to land, so forbid rejects it.
    with pytest.raises(ValidationError):
        ParticipantStatus.model_validate(
            {"context": "urn:uuid:case-2232", "participantStatuses": "x"}
        )


def test_round_trip_is_exact_for_every_core_vocabulary_entry() -> None:
    """AC-4: ``type(obj).model_validate(dump(obj)) == obj`` (ARCH-23-005).

    Exercises the computed-field strip and the alias/field-name de-dup: without
    them, a ``@computed_field`` or an injected alias twin would trip
    ``extra="forbid"`` on re-validation.
    """
    for name, obj in _constructible_vocab():
        restored = type(obj).model_validate(obj.model_dump(mode="json"))
        assert restored == obj, f"{name} did not round-trip exactly"


def _sealed_class() -> type[CoreObject]:
    """A test-local ``CoreObject`` whose ``is_sealed`` is a computed bool.

    No production class has a computed field (ARCH-23-005), so the bool
    contract — including the True side, which a vocabulary of minimal objects
    never reaches — is exercised on a local subclass.  Callers request
    ``isolated_core_registries`` so the class stays out of the global
    registries.
    """
    from typing import Literal

    from pydantic import computed_field

    class _Sealed(CoreObject):
        type_: Literal["_Sealed"] = "_Sealed"
        sealed_by: str | None = None

        @computed_field  # type: ignore[misc]
        @property
        def is_sealed(self) -> bool:
            return self.sealed_by is not None

    return _Sealed


def test_true_computed_bool_round_trips(isolated_core_registries) -> None:
    """A computed bool that is True round-trips exactly (ARCH-23-005).

    Exercises the True side so the comparison inside
    ``_check_computed_field_inputs`` cannot be an inverted equality that
    passes vacuously.
    """
    sealed = _sealed_class().model_validate({"sealed_by": "urn:uuid:actor"})
    assert sealed.model_dump()["is_sealed"] is True

    cls = type(sealed)
    assert cls.model_validate(sealed.model_dump(mode="json")) == sealed
    # The camelCase wire form parses too; compared by dump because a parsed
    # document keeps ``@context`` in ``context_``, which the local object
    # never set.
    wire = sealed.model_dump(mode="json", by_alias=True)
    assert wire["isSealed"] is True
    assert cls.model_validate(wire).model_dump() == sealed.model_dump()


def test_contradicted_computed_bool_raises_protocol_violation(
    isolated_core_registries,
) -> None:
    """AC-2: a supplied computed value that contradicts the derived value
    raises VultronProtocolViolationError for both snake_case and camelCase
    spellings (ARCH-23-005, EH-07-001).
    """
    cls = _sealed_class()
    for spelling in ("is_sealed", "isSealed"):
        with pytest.raises(ValidationError) as exc_info:
            cls.model_validate({spelling: True})
        msg = str(exc_info.value)
        assert "is_sealed" in msg, (
            f"Error for spelling {spelling!r} did not name the field: {msg}"
        )
        assert "supplied True" in msg, (
            f"Error for spelling {spelling!r} did not include supplied value: {msg}"
        )
        error = _protocol_violation(exc_info.value)
        assert [v.dimensions for v in error.violations] == [("is_sealed",)]


def _protocol_violation(exc: ValidationError) -> VultronProtocolViolationError:
    """Return the ``VultronProtocolViolationError`` Pydantic wrapped in *exc*."""
    error = exc.errors()[0].get("ctx", {}).get("error")
    assert isinstance(error, VultronProtocolViolationError), exc
    return error


@pytest.mark.parametrize(
    ("data", "expected_spelling"),
    [
        # camelCase agrees with derived (False); snake_case contradicts.
        ({"is_sealed": True, "isSealed": False}, "is_sealed"),
        # snake_case agrees; camelCase contradicts.
        ({"is_sealed": False, "isSealed": True}, "isSealed"),
    ],
)
def test_disagreeing_duplicate_spellings_cannot_mask_a_contradiction(
    data: dict[str, bool], expected_spelling: str, isolated_core_registries
) -> None:
    """Both spellings supplied with different values: the contradicting one is
    refused whichever spelling carries it (ARCH-23-005, EH-07-001).

    Keying supplied values by canonical field name let the last-iterated
    spelling win, so one ordering was accepted while the reverse was refused.
    """
    with pytest.raises(ValidationError) as exc_info:
        _sealed_class().model_validate(data)
    error = _protocol_violation(exc_info.value)
    assert len(error.violations) == 1
    assert repr(expected_spelling) in error.violations[0].message


def test_all_computed_field_contradictions_named_in_one_error(
    isolated_core_registries,
) -> None:
    """AC-2: every contradicted computed field is carried in one error as
    structured ``Violation`` data (EH-07-001, EH-07-003).

    A test-local CoreObject subclass with two computed fields is used to
    prove the multi-violation contract.  ``isolated_core_registries`` keeps that subclass out
    of the process-global core registries.
    """
    from typing import Literal

    from pydantic import computed_field

    class _TwoComputedFields(CoreObject):
        type_: Literal["_TwoComputedFields"] = "_TwoComputedFields"
        base_val: int = 3

        @computed_field  # type: ignore[misc]
        @property
        def doubled(self) -> int:
            return self.base_val * 2

        @computed_field  # type: ignore[misc]
        @property
        def tripled(self) -> int:
            return self.base_val * 3

    with pytest.raises(ValidationError) as exc_info:
        _TwoComputedFields.model_validate({"doubled": 999, "tripled": 888})
    msg = str(exc_info.value)
    assert "doubled" in msg, f"First contradicted field not named: {msg}"
    assert "tripled" in msg, f"Second contradicted field not named: {msg}"
    error = _protocol_violation(exc_info.value)
    assert sorted(v.dimensions for v in error.violations) == [
        ("doubled",),
        ("tripled",),
    ]
    # str() renders the whole set, one line per violation (EH-07-003).
    assert str(error).count("supplied") == 2


def test_json_mode_dump_round_trips_for_non_bool_computed_field(
    isolated_core_registries,
) -> None:
    """A ``mode="json"`` dump of a computed field of any type round-trips
    (ARCH-23-005).

    A bool's JSON form equals its Python form, so a comparison that only
    accepts the Python value would go unseen.  A ``datetime`` computed field arrives from a JSON dump as
    a string and must still be recognised as matching.
    """
    from datetime import datetime
    from typing import Literal

    from pydantic import computed_field

    class _DatetimeComputed(CoreObject):
        type_: Literal["_DatetimeComputed"] = "_DatetimeComputed"

        @computed_field  # type: ignore[misc]
        @property
        def when(self) -> datetime:
            return datetime(2026, 1, 1, tzinfo=UTC)

    obj = _DatetimeComputed()
    assert _DatetimeComputed.model_validate(obj.model_dump(mode="json")) == obj
    assert _DatetimeComputed.model_validate(obj.model_dump()) == obj

    with pytest.raises(ValidationError) as exc_info:
        _DatetimeComputed.model_validate({"when": "2025-12-31T00:00:00Z"})
    assert [
        v.dimensions for v in _protocol_violation(exc_info.value).violations
    ] == [("when",)]


def test_retired_embargo_adherence_refused_at_parse() -> None:
    """An inbound ParticipantStatus carrying the retired embargoAdherence key
    is refused at parse (ADR-0122), not accepted with the value set aside.
    """
    import pytest

    from vultron.wire.as2.parser import (
        VultronParseValidationError,
        parse_activity,
    )

    body = {
        "type": "Announce",
        "actor": "https://example.org/actors/alice",
        "object": {
            "type": "ParticipantStatus",
            "context": "urn:uuid:case-received-path",
            "embargoAdherence": True,
        },
        "published": "2026-01-01T00:00:00+00:00",
    }
    with pytest.raises(VultronParseValidationError, match="ADR-0122"):
        parse_activity(body)


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
