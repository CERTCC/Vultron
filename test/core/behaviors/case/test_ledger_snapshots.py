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

from datetime import timedelta

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
from vultron.core.models._helpers import parse_published
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.report import VulnerabilityReport
from vultron.core.models.case_actor import CaseActor

VENDOR_ID = "https://example.org/actors/vendor"
CASE_ACTOR_ID = "https://example.org/actors/case-actor"
CASE_ID = "https://example.org/cases/urn:uuid:snapshot-test"
REPORT_ID = "https://example.org/reports/urn:uuid:report-1"


@pytest.fixture
def dl():
    return SqliteDataLayer(
        "sqlite:///:memory:",
        actor_id="https://test.example/api/v2/actors/test-actor",
    )


@pytest.fixture
def port():
    return As2WireRenderAdapter()


@pytest.fixture
def vendor_actor(dl):
    actor = CaseActor(id_=VENDOR_ID, name="Vendor Co")
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
    """CLP-07 / CLP-12: every native-init snapshot must survive validation."""

    def test_create_case(self, case, port):
        _validate_canonical_entry(
            case_id=CASE_ID,
            payload_snapshot=build_create_case_snapshot(
                case, CASE_ACTOR_ID, CASE_ID, port
            ),
            event_type="create_case",
        )

    def test_add_report_to_case(self, report, case, port):
        _validate_canonical_entry(
            case_id=CASE_ID,
            payload_snapshot=build_add_report_to_case_snapshot(
                report, case, CASE_ACTOR_ID, CASE_ID, port
            ),
            event_type="add_report_to_case",
        )

    def test_add_participant_status(self, participant, port):
        _validate_canonical_entry(
            case_id=CASE_ID,
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
            payload_snapshot=build_add_case_status_snapshot(
                raw_status, case, actor, CASE_ID, port
            ),
            event_type="add_case_status_to_case",
        )


class TestSnapshotObjectWireReconstitutable:
    """AC-7: every payloadSnapshot object dict revalidates through its wire vocabulary class."""

    def test_create_case_object_wire_reconstitutable(self, case, port):
        from vultron.wire.as2.vocab.base.registry import find_in_vocabulary

        snap = build_create_case_snapshot(case, CASE_ACTOR_ID, CASE_ID, port)
        obj = snap["object"]
        wire_cls = find_in_vocabulary(obj["type"])
        wire_cls.model_validate(obj)

    def test_add_report_object_wire_reconstitutable(self, report, case, port):
        from vultron.wire.as2.vocab.base.registry import find_in_vocabulary

        snap = build_add_report_to_case_snapshot(
            report, case, CASE_ACTOR_ID, CASE_ID, port
        )
        obj = snap["object"]
        wire_cls = find_in_vocabulary(obj["type"])
        wire_cls.model_validate(obj)

    def test_add_participant_status_object_wire_reconstitutable(
        self, participant, port
    ):
        from vultron.wire.as2.vocab.base.registry import find_in_vocabulary

        snap = build_add_participant_status_snapshot(
            participant.participant_statuses[0],
            participant,
            CASE_ACTOR_ID,
            CASE_ID,
            port,
        )
        obj = snap["object"]
        wire_cls = find_in_vocabulary(obj["type"])
        wire_cls.model_validate(obj)

    def test_add_case_status_object_wire_reconstitutable(self, case, port):
        from vultron.wire.as2.vocab.base.registry import find_in_vocabulary

        raw_status = case.case_statuses[0]
        snap = build_add_case_status_snapshot(
            raw_status, case, VENDOR_ID, CASE_ID, port
        )
        obj = snap["object"]
        wire_cls = find_in_vocabulary(obj["type"])
        wire_cls.model_validate(obj)


# Allow-listed camelCase-looking dict-literal keys in vultron/core/.  The seven
# wire aliases this list used to carry belonged to ``_SNAKE_TWINS`` in
# lifecycle.py and are gone: the patch keys are now derived from the fields' own
# aliases (#3485, ADR-0099 detail 2).  What remains is the case-state pattern
# strings, which contain capitals but are not wire keys.
#
# The general form of this narrow scan now lives in
# ``test/architecture/test_core_no_as2_spellings.py``, which covers every string
# literal rather than only dict keys, and tells an alias declaration from a use.
_AC8_ALLOW_LISTED: frozenset[str] = frozenset(
    {
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


class TestSnapshotsCarryPublished:
    """CLP-07-011: a snapshot without ``published`` is not the verbatim activity.

    The commit boundary rejects one that omits it
    (``_validate_entry_timestamps``), so every builder in
    ``ledger_snapshots.py`` has to set it.  These assertions live here rather
    than in the guard's own tests because this file is the ``verification``
    CLP-07-011 names, and because the builders are where the field is *produced*
    — a future edit that drops it should fail next to the cause, not at some
    commit call site three layers away (#2824).
    """

    @pytest.fixture
    def built(self, case, report, participant, port):
        """Every builder's output, keyed by builder name."""
        return {
            "build_create_case_snapshot": build_create_case_snapshot(
                case, CASE_ACTOR_ID, CASE_ID, port
            ),
            "build_add_report_to_case_snapshot": (
                build_add_report_to_case_snapshot(
                    report, case, CASE_ACTOR_ID, CASE_ID, port
                )
            ),
            "build_add_participant_status_snapshot": (
                build_add_participant_status_snapshot(
                    participant.participant_statuses[0],
                    participant,
                    CASE_ACTOR_ID,
                    CASE_ID,
                    port,
                )
            ),
            "build_add_case_status_snapshot": build_add_case_status_snapshot(
                case.case_statuses[0], case, CASE_ACTOR_ID, CASE_ID, port
            ),
        }

    def test_builder_coverage_is_exhaustive(self, built):
        """The fixture above covers every public builder the module exports.

        Without this, a newly added builder would silently escape the
        ``published`` assertion below — the fixture would just not mention it.
        """
        from vultron.core.behaviors.case import ledger_snapshots

        exported = {
            name
            for name in dir(ledger_snapshots)
            if name.startswith("build_") and name.endswith("_snapshot")
        }
        assert exported == set(built), (
            "ledger_snapshots.py builders not covered by this test: "
            f"{sorted(exported - set(built))}"
        )

    def test_every_builder_sets_a_parseable_published(self, built):
        missing = sorted(
            name for name, s in built.items() if not s.get("published")
        )
        assert not missing, f"builders that omit `published`: {missing}"

        unparseable = sorted(
            name
            for name, s in built.items()
            if parse_published(s["published"]) is None
        )
        assert (
            not unparseable
        ), f"builders whose `published` does not parse: {unparseable}"

    def test_published_is_timezone_aware_utc(self, built):
        """A naive stamp would compare against an aware one and raise."""
        for name, snap in built.items():
            parsed = parse_published(snap["published"])
            assert parsed is not None, name
            assert parsed.tzinfo is not None, name
            assert parsed.utcoffset() == timedelta(0), name


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
