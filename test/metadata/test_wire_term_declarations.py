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

Each test checks one rule of ADR-0194 against a field that breaks it today, so
each is a strict ``xfail`` naming the Task that makes it hold.  #6422 replaces
the sampled fields with a check over every wire field and its owned ratchets.
"""

import json
from pathlib import Path

import pytest
from pydantic import BaseModel

from vultron.core.models.base.context import VULTRON_PROPERTY_KEY
from vultron.core.models.case.vulnerability_case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.vulnerability_item import (
    VulnerabilityItemId,
    VulnerabilityItemNote,
)
from vultron.metadata.wire_context.sync import CONTEXT_JSONLD_PATH

_REPO_ROOT = Path(__file__).resolve().parents[2]

#: Wire names a ``CaseLedgerEntry`` declares itself and keeps under ADR-0194:
#: each is a Vultron term, so the context document must map it.
_LEDGER_ENTRY_TERMS = (
    "logIndex",
    "logObjectId",
    "semanticType",
    "payloadSnapshot",
    "prevLogHash",
    "entryHash",
    "receivedAt",
)


def _vultron_terms() -> dict[str, object]:
    """The term map of the Vultron context document."""
    document = json.loads((_REPO_ROOT / CONTEXT_JSONLD_PATH).read_text())
    [terms] = [c for c in document["@context"] if isinstance(c, dict)]
    return terms


def _wire_names(model: type[BaseModel]) -> set[str]:
    return {f.alias or name for name, f in model.model_fields.items()}


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="VM-10-007: the context document maps only four properties. "
    "Tracked by #6409 (terms) and #6422 (the check over every field).",
)
@pytest.mark.spec("VM-10-007")
def test_every_wire_field_of_a_vultron_object_has_a_term() -> None:
    assert set(_LEDGER_ENTRY_TERMS) <= _wire_names(CaseLedgerEntry)
    terms = _vultron_terms()
    missing = [name for name in _LEDGER_ENTRY_TERMS if name not in terms]
    assert not missing, f"wire fields with no JSON-LD term: {missing}"


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="VM-10-008: the property marker is a bare flag. Tracked by #6409.",
)
@pytest.mark.spec("VM-10-008")
def test_a_vultron_property_declaration_carries_a_definition_and_kind() -> (
    None
):
    field = VulnerabilityCase.model_fields["ledger_position"]
    extra = field.json_schema_extra
    assert isinstance(extra, dict) and VULTRON_PROPERTY_KEY in extra
    declaration = extra[VULTRON_PROPERTY_KEY]
    assert declaration is not True, "the marker carries no definition or kind"


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="VM-10-009: a vulnerability item note sends AS2 `audience` with a "
    "CSAF meaning. Tracked by #6416.",
)
@pytest.mark.spec("VM-10-009")
def test_a_vultron_field_reuses_no_as2_name() -> None:
    assert "audience" not in _wire_names(VulnerabilityItemNote)


@pytest.mark.xfail(
    strict=True,
    raises=KeyError,
    reason="VM-10-010: the context document has no typed property terms. "
    "Tracked by #6409.",
)
@pytest.mark.spec("VM-10-010")
def test_the_context_types_each_term_by_its_value_kind() -> None:
    terms = _vultron_terms()
    assert terms["payloadSnapshot"] == {
        "@id": "vultron:payloadSnapshot",
        "@type": "@json",
    }
    assert terms["actorParticipantIndex"] == {
        "@id": "vultron:actorParticipantIndex",
        "@container": "@index",
    }


@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="VM-10-012: `text` is an identifier's value on one class and a "
    "note's body on another. Tracked by #6416.",
)
@pytest.mark.spec("VM-10-012")
def test_one_wire_name_has_one_meaning() -> None:
    shared = _wire_names(VulnerabilityItemId) & _wire_names(
        VulnerabilityItemNote
    )
    assert not shared, f"wire names with two meanings: {sorted(shared)}"
