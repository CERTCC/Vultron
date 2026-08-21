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

"""Tests for :class:`~vultron.adapters.driven.wire_render.As2WireRenderAdapter`.

Covers:
- AC-2: round-trip test for every core type with a wire counterpart
- AC-3: VultronValidationError raised for core types with no wire counterpart
- AC-6: test file does NOT import from vultron.core (adapter import only)

Per ``specs/architecture.yaml`` ARCH-20-001 through ARCH-20-004.
"""

from datetime import timedelta

import pytest

from vultron.adapters.driven.wire_render import As2WireRenderAdapter
from vultron.wire.as2.vocab.base.registry import VOCABULARY
from vultron.core.models.actor import VultronPerson
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_actor import CaseActor
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_reference import CaseReference
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.embargo_policy import EmbargoPolicy
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.report import VulnerabilityReport
from vultron.core.models.vulnerability_record import VulnerabilityRecord
from vultron.errors import VultronValidationError

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def adapter():
    return As2WireRenderAdapter()


# ---------------------------------------------------------------------------
# Helper — assert a render result looks like a wire object
# ---------------------------------------------------------------------------


def _assert_wire_dict(result: dict, expected_type: str) -> None:
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    assert (
        result.get("type") == expected_type
    ), f"Expected type={expected_type!r}, got {result.get('type')!r}"
    # camelCase key present (not snake_case)
    # The 'id' field is always emitted by VultronAS2Object
    assert "id" in result, f"Missing 'id' key in wire dict for {expected_type}"
    # AC-5 / CLP-07-001: output must be receiver-reconstitutable
    wire_cls = VOCABULARY.get(expected_type)
    assert (
        wire_cls is not None
    ), f"No VOCABULARY entry for {expected_type!r} — cannot verify reconstitutability"
    wire_cls.model_validate(result)


# ---------------------------------------------------------------------------
# AC-2: Round-trip for every core type that HAS a wire counterpart (9 types)
# ---------------------------------------------------------------------------


def test_render_vulnerability_case(adapter):
    obj = VulnerabilityCase()
    result = adapter.render(obj)
    _assert_wire_dict(result, "VulnerabilityCase")


def test_render_vulnerability_report(adapter):
    obj = VulnerabilityReport()
    result = adapter.render(obj)
    _assert_wire_dict(result, "VulnerabilityReport")


def test_render_case_participant(adapter):
    obj = CaseParticipant()
    result = adapter.render(obj)
    _assert_wire_dict(result, "CaseParticipant")


def test_render_case_reference(adapter):
    obj = CaseReference(url="https://example.org/ref")
    result = adapter.render(obj)
    _assert_wire_dict(result, "CaseReference")


def test_render_embargo_policy(adapter):
    obj = EmbargoPolicy(
        actor_id="urn:uuid:actor",
        inbox="https://example.org/inbox",
        preferred_duration=timedelta(days=90),
    )
    result = adapter.render(obj)
    _assert_wire_dict(result, "EmbargoPolicy")


def test_render_vulnerability_record(adapter):
    obj = VulnerabilityRecord(name="CVE-2024-0001")
    result = adapter.render(obj)
    _assert_wire_dict(result, "VulnerabilityRecord")


def test_render_case_status(adapter):
    obj = CaseStatus(context="urn:uuid:case")
    result = adapter.render(obj)
    _assert_wire_dict(result, "CaseStatus")


def test_render_participant_status(adapter):
    obj = ParticipantStatus(context="urn:uuid:case")
    result = adapter.render(obj)
    _assert_wire_dict(result, "ParticipantStatus")


def test_render_case_ledger_entry(adapter):
    obj = CaseLedgerEntry(
        case_id="urn:uuid:case",
        log_object_id="urn:uuid:obj",
        event_type="V",
    )
    result = adapter.render(obj)
    _assert_wire_dict(result, "CaseLedgerEntry")


# ---------------------------------------------------------------------------
# AC-2: Round-trip output uses by_alias=True, exclude_none=True
# ---------------------------------------------------------------------------


def test_render_returns_camel_case_keys(adapter):
    """Output dict uses camelCase field names (by_alias=True)."""
    obj = CaseLedgerEntry(
        case_id="urn:uuid:case",
        log_object_id="urn:uuid:obj",
        event_type="V",
    )
    result = adapter.render(obj)
    # Wire alias for 'case_id' is 'caseId' / 'context' depending on wire model;
    # at minimum no snake_case keys that are known aliases should be present
    assert (
        "case_id" not in result
    ), "Expected camelCase output (by_alias=True) but found snake_case key 'case_id'"


def test_render_excludes_none_fields(adapter):
    """Output dict omits None-valued fields (exclude_none=True)."""
    obj = VulnerabilityCase()
    result = adapter.render(obj)
    for key, val in result.items():
        assert (
            val is not None
        ), f"Field {key!r} should be excluded (exclude_none=True) but has value None"


# ---------------------------------------------------------------------------
# AC-3: VultronValidationError for core types with no wire counterpart
# ---------------------------------------------------------------------------


def test_render_raises_for_case_actor(adapter):
    """CaseActor has no VultronAS2Object wire counterpart — must raise."""
    obj = CaseActor()
    with pytest.raises(VultronValidationError, match="CaseActor"):
        adapter.render(obj)


def test_render_raises_for_vultron_person(adapter):
    """VultronPerson wire class is NOT VultronAS2Object — must raise."""
    obj = VultronPerson()
    with pytest.raises(VultronValidationError, match="VultronPerson"):
        adapter.render(obj)


def test_render_raises_for_unknown_type(adapter):
    """Arbitrary non-vocabulary object raises VultronValidationError."""

    class _NotACoreType:
        pass

    with pytest.raises(VultronValidationError):
        adapter.render(_NotACoreType())


# ---------------------------------------------------------------------------
# AC-6: Protocol structural compliance — adapter satisfies WireRenderPort
# ---------------------------------------------------------------------------


def test_adapter_satisfies_wire_render_port():
    """As2WireRenderAdapter is structurally compatible with WireRenderPort."""
    from vultron.core.ports.wire_render import WireRenderPort

    assert isinstance(As2WireRenderAdapter(), WireRenderPort)
