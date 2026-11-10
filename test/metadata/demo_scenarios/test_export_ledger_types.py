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

"""Drift and shape tests for the generated ledger types (#4729).

``vultron/metadata/demo_scenarios/export_ledger_types.py`` writes
``ui/src/data/ledgerTypes.ts`` from the ``CaseLedgerEntry``,
``ParticipantStatus`` and ``CaseStatus`` models.  These tests fail when the
committed file no longer matches a fresh export, and check that the projection
says what the models write: the wire keys, the enum values and which fields a
line must carry.

To fix a drift failure here::

    uv run export-demo-ledger-types
    git add ui/src/data/ledgerTypes.ts
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import computed_field

from vultron.core.models.base import CoreObject
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.states.cs import CS_d, CS_pxa, CS_vf
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from vultron.metadata.demo_scenarios import export_ledger_types
from vultron.metadata.demo_scenarios.export_ledger_types import (
    LEDGER_TYPES,
    OUTPUT_PATH,
    REGEN_COMMAND,
    LedgerType,
    main,
    project,
    render,
    stale_hint,
)
from vultron.metadata.generated_files import read_committed

ARTIFACT = "ui/src/data/ledgerTypes.ts"
CASE = "urn:uuid:aaaa1111-0000-4000-8000-000000000001"
PUBLISHED = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture(scope="module")
def fields() -> dict[str, dict[str, export_ledger_types.FieldDef]]:
    shapes, _ = project()
    return {
        name: {field.key: field for field in defs}
        for name, defs in shapes.items()
    }


def _instances() -> dict[str, CoreObject]:
    """One populated instance of each exported model."""
    case_status = CaseStatus(context=CASE, published=PUBLISHED)
    status = ParticipantStatus(
        context=CASE,
        attributed_to="http://actor1:7999/api/v2/actors/actor1",
        cvd_role=[CVDRole.VENDOR, CVDRole.DEPLOYER],
        tracking_id="T-1",
        case_status=case_status,
    )
    entry = CaseLedgerEntry(
        case_id=CASE,
        log_index=0,
        log_object_id=f"{CASE}/activity/0",
        semantic_type="create_case",
        payload_snapshot={"type": "Create"},
        prev_log_hash="a" * 64,
        entry_hash="b" * 64,
    )
    return {
        "CaseLedgerEntry": entry,
        "ParticipantStatus": status,
        "CaseStatus": case_status,
    }


# ---------------------------------------------------------------------------
# Drift
# ---------------------------------------------------------------------------


def test_artifact_path_is_the_one_the_hint_names() -> None:
    assert OUTPUT_PATH.as_posix().endswith(ARTIFACT)
    assert ARTIFACT in stale_hint(OUTPUT_PATH)


def test_committed_file_matches_a_fresh_export() -> None:
    # read_committed keeps line endings, so a CRLF copy fails here too.
    assert read_committed(OUTPUT_PATH) == render(), stale_hint(OUTPUT_PATH)


def test_stale_hint_names_the_regeneration_command() -> None:
    assert f"`{REGEN_COMMAND}`" in stale_hint(OUTPUT_PATH)


def test_check_passes_on_the_committed_file() -> None:
    main(["--check"])


def test_check_fails_on_a_stale_file_and_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "ui" / "src" / "data" / "ledgerTypes.ts"
    target.parent.mkdir(parents=True)
    target.write_text("// hand-edited\n", encoding="utf-8")
    monkeypatch.setattr(export_ledger_types, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(export_ledger_types, "OUTPUT_PATH", target)
    with pytest.raises(SystemExit) as excinfo:
        main(["--check"])
    assert excinfo.value.code == stale_hint(target)
    assert target.read_text(encoding="utf-8") == "// hand-edited\n"


def test_check_fails_on_a_missing_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "ui" / "src" / "data" / "ledgerTypes.ts"
    monkeypatch.setattr(export_ledger_types, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(export_ledger_types, "OUTPUT_PATH", target)
    with pytest.raises(SystemExit):
        main(["--check"])
    assert not target.exists()


def test_write_mode_writes_the_export(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "ui" / "src" / "data" / "ledgerTypes.ts"
    monkeypatch.setattr(export_ledger_types, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(export_ledger_types, "OUTPUT_PATH", target)
    main([])
    assert read_committed(target) == render()


# ---------------------------------------------------------------------------
# The projection says what the models write
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name", ["CaseLedgerEntry", "ParticipantStatus", "CaseStatus"]
)
def test_the_projected_keys_are_the_keys_the_model_writes(
    name: str, fields: dict[str, dict[str, export_ledger_types.FieldDef]]
) -> None:
    # A full AS2 dump (no exclude_none) writes every field the model has on
    # the wire, plus the JSON-LD context: the closed world of its keys.
    instance = _instances()[name]
    dumped = instance.model_dump(mode="json", by_alias=True)
    assert set(dumped) == set(fields[name])
    # And the model reads back every key it wrote.
    assert type(instance).model_validate(dumped) is not None


def test_participant_status_carries_vf_and_d_not_the_retired_keys(
    fields: dict[str, dict[str, export_ledger_types.FieldDef]],
) -> None:
    keys = set(fields["ParticipantStatus"])
    assert {"rmState", "vfState", "dState"} <= keys
    assert not keys & {"vfdState", "emConsentState", "vf_state", "d_state"}
    assert "vfdState" not in render()
    assert "emConsentState" not in render()


def test_enum_values_are_the_wire_values() -> None:
    _, enums = project()
    values = {name: list(enum.values) for name, enum in enums.items()}
    assert values == {
        "RmState": [m.name for m in RM],
        "VfState": [m.name for m in CS_vf],
        "DState": [m.name for m in CS_d],
        # cvdRole's own serializer writes the role names, not the values.
        "CvdRole": [m.name for m in CVDRole],
        "EmState": [m.name for m in EM],
        "PxaState": [m.name for m in CS_pxa],
    }


def test_a_written_entry_requires_every_field_the_model_always_writes(
    fields: dict[str, dict[str, export_ledger_types.FieldDef]],
) -> None:
    required = {k for k, f in fields["CaseLedgerEntry"].items() if f.required}
    assert required == {
        "id",
        "type",
        "published",
        "caseId",
        "logIndex",
        "logObjectId",
        "semanticType",
        "payloadSnapshot",
        "prevLogHash",
        "entryHash",
        "receivedAt",
    }


def test_a_received_status_requires_only_what_the_model_refuses_without(
    fields: dict[str, dict[str, export_ledger_types.FieldDef]],
) -> None:
    def required(name: str) -> set[str]:
        return {k for k, f in fields[name].items() if f.required}

    assert required("ParticipantStatus") == {"context"}
    # A received CaseStatus without its sender's time is refused (CLP-15-010).
    assert required("CaseStatus") == {"context", "published"}


def test_the_json_ld_context_is_projected_and_unwritten_fields_are_not(
    fields: dict[str, dict[str, export_ledger_types.FieldDef]],
) -> None:
    assert "@context" in fields["CaseLedgerEntry"]
    assert not set(fields["ParticipantStatus"]) & {
        "previousRmState",
        "forceRmState",
    }


def test_the_rendered_file_types_shapes_against_its_own_vocabulary() -> None:
    text = render()
    assert "export const LEDGER_SHAPES = {" in text
    assert "satisfies Record<LedgerTypeName, LedgerTypeDefinition>" in text
    assert "export type VfState = (typeof VF_STATE_VALUES)[number]" in text
    assert "  vfState?: VfState | null\n" in text


# ---------------------------------------------------------------------------
# Fail fast on what the projection does not know
# ---------------------------------------------------------------------------


class _UnknownKind(CoreObject):
    """No ``type_``, so it is not registered in the core vocabulary."""

    tallies: set[int] = set()


class _Computed(CoreObject):
    """No ``type_``, so it is not registered in the core vocabulary."""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def derived(self) -> str:
        return "x"


def test_an_unknown_annotation_fails_the_export() -> None:
    with pytest.raises(TypeError, match="No ledger shape"):
        project((LedgerType(_UnknownKind, "received"),))


def test_a_computed_field_fails_the_export() -> None:
    with pytest.raises(TypeError, match="computed fields"):
        project((LedgerType(_Computed, "received"),))


def test_the_exported_models_are_the_ledger_line_and_its_statuses() -> None:
    assert [(lt.model, lt.role) for lt in LEDGER_TYPES] == [
        (CaseLedgerEntry, "written"),
        (ParticipantStatus, "received"),
        (CaseStatus, "received"),
    ]
