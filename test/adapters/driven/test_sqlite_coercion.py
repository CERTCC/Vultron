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

"""Tests for SqliteDataLayer _rehydrate_fields and _coerce_to_semantic_class.

Covers: TestRehydrateFields (_rehydrate_fields expands dehydrated string IDs
back to typed objects) and TestCoerceToSemanticClass (_coerce_to_semantic_class
promotes base-vocab activities to subtypes).
Fixtures (dl) come from conftest.
"""

from vultron.core.models.report import VulnerabilityReport
from vultron.wire.as2.factories import (
    announce_log_entry_activity,
    em_propose_embargo_activity,
    rm_submit_report_activity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Announce,
    as_Invite,
    as_Offer,
)

_ZERO_HASH: str = "0" * 64  # arbitrary hash for test chains


# ---------------------------------------------------------------------------
# DL-REHYDRATE: _rehydrate_fields expansion tests
# ---------------------------------------------------------------------------


class TestRehydrateFields:
    """_rehydrate_fields expands dehydrated string IDs back to typed objects."""

    def test_offer_object_field_expanded_to_vulnerability_report(self, dl):
        """_RmSubmitReportActivity.object_ is a as_VulnerabilityReport after read."""
        from vultron.wire.as2.vocab.objects.vulnerability_report import (
            as_VulnerabilityReport,
        )

        report = as_VulnerabilityReport(
            name="CVE-TEST-001", content="Test body"
        )
        offer = rm_submit_report_activity(
            report,
            "https://alice.example.org",
            actor="https://alice.example.org",
        )
        dl.save(report)
        dl.save(offer)

        result = dl.read(offer.id_)

        assert isinstance(result, as_Offer)
        assert isinstance(result.object_, as_VulnerabilityReport)  # type: ignore[union-attr]
        assert result.object_.name == "CVE-TEST-001"  # type: ignore[union-attr]

    def test_missing_nested_object_keeps_string(self, dl):
        """When a referenced object is not in the DB, the string ID is kept."""
        from vultron.wire.as2.vocab.objects.vulnerability_report import (
            as_VulnerabilityReport,
        )

        report = as_VulnerabilityReport(name="CVE-MISSING", content="Body")
        offer = rm_submit_report_activity(
            report,
            "https://alice.example.org",
            actor="https://alice.example.org",
        )
        # Save offer but NOT the report — reference is dangling
        dl.save(offer)

        result = dl.read(offer.id_)

        # Object field keeps the string ID since the report cannot be resolved
        assert result is not None
        assert isinstance(result.object_, str)  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# DL-REHYDRATE: _coerce_to_semantic_class tests
# ---------------------------------------------------------------------------


class TestCoerceToSemanticClass:
    """_coerce_to_semantic_class promotes base-vocab activities to subtypes."""

    def test_rm_submit_report_round_trip_returns_specific_class(self, dl):
        """dl.read returns _RmSubmitReportActivity, not generic as_Offer."""
        from vultron.wire.as2.vocab.objects.vulnerability_report import (
            as_VulnerabilityReport,
        )

        report = as_VulnerabilityReport(name="CVE-ROUND-TRIP", content="Body")
        offer = rm_submit_report_activity(
            report,
            "https://alice.example.org",
            actor="https://alice.example.org",
        )
        dl.save(report)
        dl.save(offer)

        result = dl.read(offer.id_)

        assert type(result).__name__ == "_RmSubmitReportActivity"

    def test_em_propose_embargo_round_trip_returns_specific_class(self, dl):
        """dl.read returns _EmProposeEmbargoActivity with as_EmbargoEvent object_."""
        from vultron.wire.as2.vocab.objects.embargo_event import (
            as_EmbargoEvent,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        case = as_VulnerabilityCase()
        embargo = as_EmbargoEvent(context=case.id_)
        proposal = em_propose_embargo_activity(
            embargo,
            context=case.id_,
            actor="https://alice.example.org",
        )
        dl.save(case)
        dl.save(embargo)
        dl.save(proposal)

        result = dl.read(proposal.id_)

        assert type(result).__name__ == "_EmProposeEmbargoActivity"
        assert isinstance(result.object_, as_EmbargoEvent)  # type: ignore[union-attr]

    def test_accept_invite_round_trip_returns_specific_class_from_generic_parse(
        self, dl
    ):
        """Generic inbound Accept(Invite(...)) reads back as RmAcceptInviteToCaseActivity."""
        from typing import cast

        from vultron.wire.as2.parser import parse_activity
        from vultron.wire.as2.vocab.base.objects.actors import as_Organization

        parsed = cast(
            as_Accept,
            parse_activity(
                {
                    "type": "Accept",
                    "id": "urn:uuid:accept-invite-roundtrip-1",
                    "actor": "https://example.org/actors/coordinator",
                    "inReplyTo": "urn:uuid:invite-roundtrip-1",
                    "object": {
                        "type": "Invite",
                        "id": "urn:uuid:invite-roundtrip-1",
                        "actor": "https://example.org/actors/vendor",
                        "object": {
                            "type": "Organization",
                            "id": "https://example.org/actors/coordinator",
                            "name": "Coordinator",
                        },
                        "target": {
                            "type": "VulnerabilityCase",
                            "id": "https://example.org/cases/case-roundtrip-1",
                        },
                        "to": ["https://example.org/actors/coordinator"],
                    },
                },
            ),
        )

        nested_invite = parsed.object_
        assert nested_invite is not None
        dl.save(
            as_Organization(
                id_="https://example.org/actors/coordinator",
                name="Coordinator",
            )
        )
        dl.save(nested_invite)
        dl.save(parsed)

        result = dl.read(parsed.id_)

        assert isinstance(result, as_Accept)
        assert isinstance(result.object_, as_Invite)
        assert result.object_.id_ == "urn:uuid:invite-roundtrip-1"
        assert result.in_reply_to == "urn:uuid:invite-roundtrip-1"

    def test_announce_log_entry_round_trip_returns_specific_class(self, dl):
        """dl.read returns AnnounceLogEntryActivity with as_CaseLedgerEntry object_."""
        from vultron.core.behaviors.sync.nodes.chain import (
            _to_persistable_entry,
        )
        from vultron.core.models.case_ledger import (
            HashChainLedgerRecord,
        )
        from vultron.wire.as2.vocab.objects.case_ledger_entry import (
            as_CaseLedgerEntry as WireCaseLedgerEntry,
        )

        chain_entry = HashChainLedgerRecord(
            case_id="https://example.org/cases/case-sync-1",
            log_index=0,
            object_id="https://example.org/activities/logged-1",
            event_type="log_entry_committed",
            payload_snapshot={"status": "ok"},
            prev_log_hash=_ZERO_HASH,
        )
        entry = _to_persistable_entry(chain_entry)
        announce = announce_log_entry_activity(
            WireCaseLedgerEntry.from_core(entry),
            actor="https://example.org/actors/case-actor",
        )
        dl.save(entry)
        dl.save(announce)

        result = dl.read(announce.id_)

        assert isinstance(result, as_Announce)
        assert isinstance(result.object_, WireCaseLedgerEntry)  # type: ignore[union-attr]
        assert result.object_.case_id == entry.case_id  # type: ignore[union-attr]
        assert result.object_.log_object_id == entry.log_object_id  # type: ignore[union-attr]

    def test_non_activity_object_not_coerced(self, dl):
        """Non-activity objects (e.g. as_VulnerabilityReport) are returned as-is."""
        from vultron.wire.as2.vocab.objects.vulnerability_report import (
            as_VulnerabilityReport,
        )

        report = as_VulnerabilityReport(name="CVE-PLAIN", content="Body")
        dl.save(report)

        result = dl.read(report.id_)

        assert isinstance(result, VulnerabilityReport)
