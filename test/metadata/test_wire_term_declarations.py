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
"""Every Vultron wire field has a typed JSON-LD term (VM-10-007 to VM-10-012).

The term check (:mod:`vultron.metadata.wire_context.terms`) runs over every
wire field; each field it refuses today sits in an owner's ratchet in
``test/metadata/wire_term_ratchets.py``, held equal to the violations in both
directions.  The probe tests below give it synthetic classes and contexts,
so each rule is shown to fire.
"""

import json
from pathlib import Path
from typing import Literal

import pytest
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from vultron.core.models.base.context import (
    PropertyValueKind,
    declared_vultron_property,
    vultron_property,
)
from vultron.core.models.case.vulnerability_case import VulnerabilityCase
from vultron.core.models.multikey import Multikey
from vultron.metadata.file_loading import MetadataLoadError
from vultron.metadata.ratchet_markers import baselines_in_source
from vultron.metadata.wire_context import cli, terms as term_check
from vultron.metadata.wire_context.pin import ContextTerms, load_pin
from vultron.metadata.wire_context.sync import (
    CONTEXT_JSONLD_PATH,
    wire_field_classes,
)
from vultron.metadata.wire_context.terms import (
    CITED_CONTEXTS,
    RATCHET_PATH,
    Ratchet,
    TermRule,
    TermViolation,
    check_wire_terms,
    compare,
    load_ratchets,
    term_violations,
    wire_term_violations,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]

_CITED = "https://example.org/cited"
_UNCITED = "https://example.org/uncited"

#: Two synthetic contexts: one cited, one only pinned.
_PINNED = {
    _CITED: ContextTerms(
        top_level=frozenset({"id", "type", "name"}),
        type_scoped={"Key": frozenset({"controller"})},
    ),
    _UNCITED: ContextTerms(top_level=frozenset({"assertionMethod"})),
}


def _violations(*classes: type[BaseModel]) -> list[TermViolation]:
    return term_violations(classes, _PINNED, cited=(_CITED,))


def _keys(*classes: type[BaseModel]) -> set[tuple[str, TermRule]]:
    return {(v.key, v.rule) for v in _violations(*classes)}


class _Probe(BaseModel):
    """A wire object with one field of each outcome."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    name: str = "x"
    context_: str = Field(default="c", serialization_alias="@context")
    secret_note: str = Field(default="s", exclude=True)
    case_id: str = "c"
    assertion_method: str = "k"
    marked_field: str = Field(
        default="m",
        json_schema_extra=vultron_property(
            "A probe property", PropertyValueKind.PLAIN
        ),
    )


class _ProbeChild(_Probe):
    """Inherits its parent's fields and declares one of its own."""

    child_only: str = "c"


class _Key(BaseModel):
    type_: Literal["Key"] = Field(serialization_alias="type")
    controller: str


class _NotAKey(BaseModel):
    controller: str


def _declaring(definition: str, field_name: str = "shared") -> type[BaseModel]:
    model = type(
        f"_Declares{definition.replace(' ', '')}",
        (BaseModel,),
        {
            "__annotations__": {field_name: str},
            field_name: Field(
                default="v",
                json_schema_extra=vultron_property(
                    definition, PropertyValueKind.PLAIN
                ),
            ),
        },
    )
    return model


# --- The real vocabulary ---------------------------------------------------


@pytest.mark.spec("VM-10-007", "VM-10-009", "VM-10-012", "ARCH-18-001")
def test_every_wire_field_of_a_vultron_object_has_a_term() -> None:
    """No unexcused violation and no stale ratchet entry (ARCH-18-006)."""
    report = check_wire_terms()
    assert report.ok, "\n".join(report.lines())


def test_the_check_walks_fields_and_finds_the_known_violations() -> None:
    """A check that found nothing would pass vacuously."""
    keys = {v.key for v in wire_term_violations()}
    assert "CaseLedgerEntry.caseId" in keys
    assert len(wire_field_classes()) > 100


@pytest.mark.spec("ARCH-18-003")
def test_each_ratchet_names_one_open_owner_and_holds_entries() -> None:
    source = (_REPO_ROOT / RATCHET_PATH).read_text(encoding="utf-8")
    baselines = baselines_in_source(source, Path(RATCHET_PATH))
    ratchets = load_ratchets()
    assert {b.name for b in baselines} == {r.name for r in ratchets}
    for ratchet in ratchets:
        assert len(ratchet.owners) == 1, ratchet.name
        assert ratchet.entries, f"{ratchet.name} is empty: delete it"


@pytest.mark.spec("VM-10-007")
def test_the_cited_contexts_are_pinned() -> None:
    assert set(CITED_CONTEXTS) <= set(load_pin().sources)


@pytest.mark.spec("VM-10-007")
def test_a_multikey_field_takes_its_type_scoped_term() -> None:
    """Multikey's ``controller`` is defined only inside its scoped context."""
    assert Multikey in wire_field_classes()
    assert not [v for v in wire_term_violations() if v.owner == "Multikey"]


@pytest.mark.spec("VM-10-007")
def test_a_case_s_notes_are_a_list_of_note_ids() -> None:
    declaration = declared_vultron_property(
        VulnerabilityCase.model_fields["notes"]
    )
    assert declaration is not None
    assert declaration.kind is PropertyValueKind.LIST
    assert declaration.items is PropertyValueKind.IRI


def _vultron_terms() -> dict[str, object]:
    """The term map of the Vultron context document."""
    document = json.loads((_REPO_ROOT / CONTEXT_JSONLD_PATH).read_text())
    [terms] = [c for c in document["@context"] if isinstance(c, dict)]
    return terms


@pytest.mark.spec("VM-10-008")
def test_a_vultron_property_declaration_carries_a_definition_and_kind() -> (
    None
):
    field = VulnerabilityCase.model_fields["ledger_position"]
    declaration = declared_vultron_property(field)
    assert declaration is not None, "ledgerPosition carries no marker"
    assert declaration.definition
    assert "\n" not in declaration.definition
    assert declaration.kind is PropertyValueKind.PLAIN


@pytest.mark.spec("VM-10-010")
def test_the_context_types_each_term_by_its_value_kind() -> None:
    terms = _vultron_terms()
    assert terms["payloadSnapshot"] == {
        "@id": "vultron:payloadSnapshot",
        "@type": "@json",
    }
    # An index map's values are participant ids, so they are typed as IRIs.
    assert terms["actorParticipantIndex"] == {
        "@id": "vultron:actorParticipantIndex",
        "@type": "@id",
        "@container": "@index",
    }
    assert terms["notes"] == {
        "@id": "vultron:notes",
        "@type": "@id",
        "@container": "@list",
    }


# --- Each rule fires -------------------------------------------------------


@pytest.mark.spec("VM-10-007")
def test_a_field_with_no_term_is_refused() -> None:
    assert ("_Probe.caseId", TermRule.NO_TERM) in _keys(_Probe)


@pytest.mark.spec("VM-10-007")
def test_a_cited_term_a_keyword_a_marked_or_excluded_field_passes() -> None:
    names = {v.wire_name for v in _violations(_Probe)}
    assert not names & {"name", "@context", "secretNote", "markedField"}


@pytest.mark.spec("VM-10-007")
def test_a_term_only_an_uncited_context_defines_is_refused() -> None:
    assert ("_Probe.assertionMethod", TermRule.NO_TERM) in _keys(_Probe)


@pytest.mark.spec("VM-10-007")
def test_a_type_scoped_term_counts_only_for_that_type() -> None:
    assert _keys(_Key) == set()
    assert _keys(_NotAKey) == {("_NotAKey.controller", TermRule.NO_TERM)}


@pytest.mark.spec("VM-10-007")
def test_an_inherited_field_is_one_violation_of_its_declaring_class() -> None:
    keys = {v.key for v in _violations(_Probe, _ProbeChild)}
    assert "_Probe.caseId" in keys
    assert "_ProbeChild.childOnly" in keys
    assert "_ProbeChild.caseId" not in keys


@pytest.mark.spec("VM-10-012")
def test_two_declarations_of_one_name_that_disagree_are_refused() -> None:
    one, other = _declaring("One meaning"), _declaring("Another meaning")
    violations = _violations(one, other)
    assert [v.rule for v in violations] == [TermRule.TWO_MEANINGS]
    assert "One meaning" in violations[0].detail
    assert "Another meaning" in violations[0].detail


@pytest.mark.spec("VM-10-012")
def test_two_declarations_that_agree_pass() -> None:
    first = _declaring("Same meaning")
    second = type("_Again", (first,), {})
    assert _violations(first, second, _declaring("Same meaning")) == []


@pytest.mark.spec("VM-10-009")
def test_a_vultron_property_named_like_a_pinned_term_is_refused() -> None:
    """Pinned is enough: citing the context later must not redefine it."""
    for term in ("name", "assertionMethod"):
        model = _declaring(f"Not the external {term}", term)
        assert (
            f"{model.__qualname__}.{term}",
            TermRule.EXTERNAL_NAME,
        ) in _keys(model)


def test_a_cited_context_with_no_pinned_copy_is_refused() -> None:
    with pytest.raises(ValueError, match="no pinned copy"):
        term_violations([_Probe], _PINNED, cited=("https://example.org/x",))


def test_the_message_names_the_field_its_class_and_the_rule() -> None:
    [violation] = [v for v in _violations(_Probe) if v.wire_name == "caseId"]
    message = violation.message()
    assert "`caseId`" in message
    assert "_Probe" in message
    assert "VM-10-007" in message


# --- The ratchets are held equal in both directions -----------------------

_FOUND = TermViolation("Cls", "field", TermRule.NO_TERM)


@pytest.mark.spec("ARCH-18-001")
def test_an_excused_violation_passes() -> None:
    report = compare(
        [_FOUND], [Ratchet("KNOWN_X", (1,), frozenset({_FOUND.key}))]
    )
    assert report.ok


@pytest.mark.spec("ARCH-18-001")
def test_a_violation_no_ratchet_excuses_fails() -> None:
    report = compare([_FOUND], [])
    assert report.unexcused == (_FOUND,)


@pytest.mark.spec("ARCH-18-006")
def test_an_entry_whose_field_is_fixed_fails() -> None:
    ratchet = Ratchet("KNOWN_X", (6410,), frozenset({"Cls.gone"}))
    report = compare([], [ratchet])
    assert report.stale == ((ratchet, "Cls.gone"),)
    assert "#6410" in report.lines()[0]


def test_an_entry_in_two_ratchets_fails() -> None:
    ratchets = [
        Ratchet(name, (1,), frozenset({_FOUND.key}))
        for name in ("KNOWN_A", "KNOWN_B")
    ]
    report = compare([_FOUND], ratchets)
    assert report.duplicated == ((_FOUND.key, ("KNOWN_A", "KNOWN_B")),)


def _write_ratchets(root: Path, body: str) -> None:
    path = root / RATCHET_PATH
    path.parent.mkdir(parents=True)
    path.write_text(body, encoding="utf-8")


def test_ratchets_are_read_with_their_owners(tmp_path: Path) -> None:
    _write_ratchets(
        tmp_path,
        '# owner: #7\nKNOWN_A = frozenset({"C.f"})\nKNOWN_B = frozenset()\n',
    )
    assert load_ratchets(tmp_path) == [
        Ratchet("KNOWN_A", (7,), frozenset({"C.f"})),
        Ratchet("KNOWN_B", (), frozenset()),
    ]


def test_a_ratchet_that_is_not_a_literal_is_refused(tmp_path: Path) -> None:
    _write_ratchets(tmp_path, "# owner: #7\nKNOWN_A = frozenset(other)\n")
    with pytest.raises(MetadataLoadError, match="KNOWN_A"):
        load_ratchets(tmp_path)


# --- The CLI runs the same check -------------------------------------------


@pytest.mark.spec("VM-10-007")
def test_wire_context_check_refuses_an_unexcused_field(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        term_check, "check_wire_terms", lambda: compare([_FOUND], [])
    )
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["--check"])
    assert exit_info.value.code == 1
    err = capsys.readouterr().err
    assert "`field` on Cls breaks VM-10-007" in err
    assert RATCHET_PATH in err


def test_wire_context_check_passes_on_the_real_vocabulary(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cli.main(["--check"])
    assert "in sync" in capsys.readouterr().out
