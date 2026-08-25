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

"""Tests for the case-initialization payloadSnapshot builders (ADR-0041).

These builders were extracted from the deleted ``nodes/prologue.py`` when
``WritePrologueLedgerEntriesNode`` was removed (Issue #1777); the CaseActor
uses them to commit the same entries natively (CM-22-003).
"""

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.behaviors.case.ledger_snapshots import (
    build_add_case_status_snapshot,
    build_add_participant_status_snapshot,
    build_add_report_to_case_snapshot,
    build_create_case_snapshot,
)
from vultron.core.behaviors.sync.nodes.canonical_entry import (
    _CANONICAL_PAYLOAD_SIGNATURES,
    _CASE_AUTHORED_SIGNATURES,
    _validate_canonical_entry,
)
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.report import VulnerabilityReport
from vultron.core.models.vultron_types import VultronCaseActor

VENDOR_ID = "https://example.org/actors/vendor"
CASE_ACTOR_ID = "https://example.org/actors/case-actor"
CASE_ID = "https://example.org/cases/urn:uuid:snapshot-test"
REPORT_ID = "https://example.org/reports/urn:uuid:report-1"


@pytest.fixture
def dl():
    return SqliteDataLayer("sqlite:///:memory:")


@pytest.fixture
def port():
    return As2WireRenderAdapter()


@pytest.fixture
def vendor_actor(dl):
    actor = VultronCaseActor(id_=VENDOR_ID, name="Vendor Co")
    dl.create(actor)
    return actor


@pytest.fixture
def report(dl):
    r = VulnerabilityReport(id_=REPORT_ID, name="Test Report")
    dl.create(r)
    return r


@pytest.fixture
def case(dl, vendor_actor, report):
    c = VulnerabilityCase(
        id_=CASE_ID, attributed_to=VENDOR_ID, name="Snapshot Test Case"
    )
    c.vulnerability_reports.append(REPORT_ID)
    dl.save(c)
    return c


@pytest.fixture
def participant(dl, case):
    p = CaseParticipant(
        id_=f"{CASE_ID}/participants/vendor",
        attributed_to=VENDOR_ID,
        context=CASE_ID,
        name="Vendor participant",
    )
    dl.create(p)
    return p


class TestSnapshotBuilders:
    def test_build_create_case_snapshot(self, case, port):
        snap = build_create_case_snapshot(case, CASE_ACTOR_ID, CASE_ID, port)
        assert snap["type"] == "Create"
        assert snap["actor"] == CASE_ACTOR_ID
        assert isinstance(snap["object"], dict)
        assert snap["object"]["type"] == "VulnerabilityCase"
        assert snap["context"] == CASE_ID

    def test_build_add_report_to_case_snapshot(self, report, case, port):
        snap = build_add_report_to_case_snapshot(
            report, case, CASE_ACTOR_ID, CASE_ID, port
        )
        assert snap["type"] == "Add"
        assert snap["actor"] == CASE_ACTOR_ID
        assert snap["object"]["type"] == "VulnerabilityReport"
        assert snap["target"]["type"] == "VulnerabilityCase"
        assert snap["context"] == CASE_ID

    def test_build_add_participant_status_snapshot(self, participant, port):
        status = participant.participant_statuses[0]
        snap = build_add_participant_status_snapshot(
            status, participant, CASE_ACTOR_ID, CASE_ID, port
        )
        assert snap["type"] == "Add"
        assert snap["actor"] == CASE_ACTOR_ID
        assert snap["object"]["type"] == "ParticipantStatus"
        assert snap["target"]["type"] == "CaseParticipant"
        assert snap["context"] == CASE_ID

    def test_participant_status_pec_flattened_to_em_consent_state(
        self, participant, port
    ):
        """The PEC dimension is rendered as the flat wire key ``emConsentState``."""
        status = participant.participant_statuses[0]
        snap = build_add_participant_status_snapshot(
            status, participant, CASE_ACTOR_ID, CASE_ID, port
        )
        assert status.consent is not None
        assert "consent" not in snap["object"]
        assert snap["object"]["emConsentState"] == status.consent.state.value

    def test_build_add_case_status_snapshot(self, case, port):
        raw_status = case.case_statuses[0]
        assert isinstance(raw_status, CaseStatus)
        snap = build_add_case_status_snapshot(
            raw_status, case, VENDOR_ID, CASE_ID, port
        )
        assert snap["type"] == "Add"
        assert snap["actor"] == VENDOR_ID
        assert snap["object"]["type"] == "CaseStatus"
        assert snap["target"]["type"] == "VulnerabilityCase"
        assert snap["context"] == CASE_ID


class TestSnapshotsPassCanonicalGuard:
    """CLP-07 / CLP-12: every native-init snapshot must survive validation.

    Each case is exercised with ``case_actor_id`` equal to the snapshot actor,
    which is the only configuration that triggers the CLP-07-003 provenance
    check — i.e. the single-actor deployment where the vendor IS the CaseActor.
    """

    def test_create_case(self, case, port):
        _validate_canonical_entry(
            case_id=CASE_ID,
            actor_id=CASE_ACTOR_ID,
            case_actor_id=CASE_ACTOR_ID,
            disposition="recorded",
            payload_snapshot=build_create_case_snapshot(
                case, CASE_ACTOR_ID, CASE_ID, port
            ),
            event_type="create_case",
        )

    def test_add_report_to_case(self, report, case, port):
        _validate_canonical_entry(
            case_id=CASE_ID,
            actor_id=CASE_ACTOR_ID,
            case_actor_id=CASE_ACTOR_ID,
            disposition="recorded",
            payload_snapshot=build_add_report_to_case_snapshot(
                report, case, CASE_ACTOR_ID, CASE_ID, port
            ),
            event_type="add_report_to_case",
        )

    def test_add_participant_status(self, participant, port):
        _validate_canonical_entry(
            case_id=CASE_ID,
            actor_id=CASE_ACTOR_ID,
            case_actor_id=CASE_ACTOR_ID,
            disposition="recorded",
            payload_snapshot=build_add_participant_status_snapshot(
                participant.participant_statuses[0],
                participant,
                CASE_ACTOR_ID,
                CASE_ID,
                port,
            ),
            event_type="add_participant_status_to_participant",
        )

    @pytest.mark.parametrize("actor", [VENDOR_ID, CASE_ACTOR_ID])
    def test_add_case_status(self, case, actor, port):
        """Valid whether stamped with the vendor URI or the CaseActor's own.

        The CaseActor stamps this entry with the vendor URI (the vendor set the
        genesis status), but ``("Add", "CaseStatus")`` is also in
        ``_CASE_AUTHORED_SIGNATURES`` per CLP-12-001 so a CaseActor-authored
        entry is accepted too (Issue #1767).
        """
        raw_status = case.case_statuses[0]
        assert isinstance(raw_status, CaseStatus)
        _validate_canonical_entry(
            case_id=CASE_ID,
            actor_id=CASE_ACTOR_ID,
            case_actor_id=CASE_ACTOR_ID,
            disposition="recorded",
            payload_snapshot=build_add_case_status_snapshot(
                raw_status, case, actor, CASE_ID, port
            ),
            event_type="add_case_status_to_case",
        )


class TestSnapshotObjectWireReconstitutable:
    """AC-7: every payloadSnapshot object dict revalidates through its wire vocabulary class."""

    def test_create_case_object_wire_reconstitutable(self, case, port):
        from vultron.wire.as2.vocab.base.registry import VOCABULARY

        snap = build_create_case_snapshot(case, CASE_ACTOR_ID, CASE_ID, port)
        obj = snap["object"]
        wire_cls = VOCABULARY[obj["type"]]
        wire_cls.model_validate(obj)

    def test_add_report_object_wire_reconstitutable(self, report, case, port):
        from vultron.wire.as2.vocab.base.registry import VOCABULARY

        snap = build_add_report_to_case_snapshot(
            report, case, CASE_ACTOR_ID, CASE_ID, port
        )
        obj = snap["object"]
        wire_cls = VOCABULARY[obj["type"]]
        wire_cls.model_validate(obj)

    def test_add_participant_status_object_wire_reconstitutable(
        self, participant, port
    ):
        from vultron.wire.as2.vocab.base.registry import VOCABULARY

        snap = build_add_participant_status_snapshot(
            participant.participant_statuses[0],
            participant,
            CASE_ACTOR_ID,
            CASE_ID,
            port,
        )
        obj = snap["object"]
        wire_cls = VOCABULARY[obj["type"]]
        wire_cls.model_validate(obj)

    def test_add_case_status_object_wire_reconstitutable(self, case, port):
        from vultron.wire.as2.vocab.base.registry import VOCABULARY

        raw_status = case.case_statuses[0]
        snap = build_add_case_status_snapshot(
            raw_status, case, VENDOR_ID, CASE_ID, port
        )
        obj = snap["object"]
        wire_cls = VOCABULARY[obj["type"]]
        wire_cls.model_validate(obj)


# Allow-listed camelCase dict-literal keys in vultron/core/ that are
# documented as intentional (not snapshot construction):
#   _SNAKE_TWINS in lifecycle.py — wire→snake reverse-lookup table
#   case_states/patterns/ — state pattern strings, not wire keys
_AC8_ALLOW_LISTED: frozenset[str] = frozenset(
    {
        "rmState",
        "vfdState",
        "emState",
        "pxaState",
        "emConsentState",
        "caseStatus",
        # case_states pattern strings (contain uppercase but are not wire keys)
        "v..P..",
        "v..pX.",
        "vF....",
        "vfdP..",
        "vfd..A",
        "vfd.X.",
    }
)


class TestSnapshotsNoCoreCamelCaseKeys:
    """AC-8: no vultron/core/ module constructs snapshot dicts with camelCase keys.

    The builders must produce wire-shaped output via the port — not by
    constructing dicts with hardcoded camelCase key strings.  Uses an AST
    dict-literal key scan (narrower than a constant scan) to avoid false
    positives from Pydantic field aliases and registry lookups.
    """

    def test_no_camel_case_dict_keys_in_core(self):
        import ast
        import pathlib

        import vultron.core

        core_dir = pathlib.Path(vultron.core.__file__).parent
        violations: list[tuple[str, str]] = []
        for py in sorted(core_dir.rglob("*.py")):
            try:
                tree = ast.parse(py.read_text())
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Dict):
                    continue
                for key in node.keys:
                    if not isinstance(key, ast.Constant):
                        continue
                    v = key.value
                    if (
                        isinstance(v, str)
                        and len(v) > 1
                        and v[0].islower()
                        and any(c.isupper() for c in v[1:])
                        and v not in _AC8_ALLOW_LISTED
                    ):
                        violations.append((str(py.relative_to(core_dir)), v))
        assert violations == [], (
            "Unexpected camelCase dict-literal keys in vultron/core/ "
            f"(add to _AC8_ALLOW_LISTED if intentional): {violations}"
        )


def test_native_init_signatures_are_canonical_and_case_authored():
    """CLP-12-001 / CLP-12-002: every native-init signature is registered.

    ``_CASE_AUTHORED_SIGNATURES`` MUST be a superset of the four
    case-initialization pairs the CaseActor commits natively, and all four MUST
    also be canonical payload signatures.
    """
    native_init = {
        ("Create", "VulnerabilityCase"),
        ("Add", "VulnerabilityReport"),
        ("Add", "ParticipantStatus"),
        ("Add", "CaseStatus"),
    }
    assert native_init <= _CASE_AUTHORED_SIGNATURES
    assert native_init <= set(_CANONICAL_PAYLOAD_SIGNATURES)
