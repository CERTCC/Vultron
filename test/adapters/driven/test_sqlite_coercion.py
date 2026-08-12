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

    def test_inline_activity_target_expanded_via_recursion(self, dl):
        """_rehydrate_fields recurses into inline BaseModel objects.

        When Accept.object_ is an inline Offer (kept inline by
        _KEEP_INLINE_NESTED_TYPES), _rehydrate_fields must recurse into the
        Offer and expand its own string reference fields (e.g. target) from
        the DataLayer.  Without recursion the bare-string target causes
        OfferCaseManagerRolePattern to permissively match any
        Offer(VulnerabilityCase), silently mis-routing ownership-transfer
        Accepts as accept_case_manager_role (SE-08-001, ISSUE-2194).
        """
        from vultron.wire.as2.vocab.base.objects.actors import as_Actor
        from vultron.wire.as2.vocab.base.objects.actors import as_Organization
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        org_id = "https://example.org/actors/target-org"
        org = as_Organization(id_=org_id, name="Target Org")
        dl.save(org)

        case = as_VulnerabilityCase()
        # target is a bare string URI — must be expanded on read-back via recursion
        offer = as_Offer(
            object_=case,
            target=org_id,
            actor="https://example.org/actors/sender",
        )
        accept = as_Accept(
            object_=offer,
            actor="https://example.org/actors/accepter",
        )
        # Store Accept only; the Offer is kept inline by _KEEP_INLINE_NESTED_TYPES.
        # The org is found by _rehydrate_fields recursing into the inline Offer.
        dl.create(accept)

        stored = dl.read(accept.id_)

        assert stored is not None
        inline_offer = getattr(stored, "object_", None)
        assert (
            inline_offer is not None
        ), "object_ should be present on stored Accept"
        assert not isinstance(
            inline_offer, str
        ), "Accept.object_ should be the inline Offer, not a bare string"
        assert not isinstance(inline_offer.target, str), (  # type: ignore[union-attr]
            f"Offer.target should be the typed actor after recursion,"
            f" not bare string {inline_offer.target!r}"  # type: ignore[union-attr]
        )
        assert isinstance(inline_offer.target, as_Actor)  # type: ignore[union-attr]


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

    def test_retype_inline_object_refs_recurses_into_sub_activities(self):
        """_retype_inline_object_refs recurses into re-typed inline sub-activities.

        Accept(object_=Offer(object_=CaseLedgerEntry(case_id=...))) — both Offer
        and CaseLedgerEntry are kept inline by _KEEP_INLINE_NESTED_TYPES.
        Without recursion, re-typing the Offer via model_validate parses the inner
        CaseLedgerEntry dict against the base as_Object union (as_Offer.object_ is
        typed Union[as_Object, as_Link, str, CoreObject]), silently dropping
        domain-specific fields such as case_id and event_type.  With the recursive
        call, _retype_inline_object_refs runs again on the re-typed Offer's raw
        sub-data and restores the CaseLedgerEntry to its specific class.
        """
        from vultron.adapters.driven.db_record import Record
        from vultron.wire.as2.vocab.objects.case_ledger_entry import (
            as_CaseLedgerEntry,
        )

        ledger_entry = as_CaseLedgerEntry(
            case_id="https://example.org/cases/retype-recurse-1",
            log_object_id="https://example.org/activities/obj-retype-1",
            event_type="log_entry_committed",
            log_index=0,
        )
        offer = as_Offer(
            object_=ledger_entry,
            actor="https://example.org/actors/sender",
        )
        accept = as_Accept(
            object_=offer,
            actor="https://example.org/actors/accepter",
        )

        record = Record.from_obj(accept)
        result = record.to_obj()

        inner_offer = getattr(result, "object_", None)
        assert (
            inner_offer is not None
        ), "Accept.object_ must be the inline Offer"
        assert not isinstance(
            inner_offer, str
        ), "Accept.object_ must not collapse to a bare string"
        inner_entry = getattr(inner_offer, "object_", None)
        assert isinstance(inner_entry, as_CaseLedgerEntry), (
            f"Offer.object_ should be re-typed to as_CaseLedgerEntry by recursive "
            f"_retype_inline_object_refs; got {type(inner_entry).__name__!r}"
        )
        assert (
            inner_entry.case_id == "https://example.org/cases/retype-recurse-1"
        )
        assert inner_entry.event_type == "log_entry_committed"

    def test_non_activity_object_not_coerced(self, dl):
        """Non-activity objects (e.g. as_VulnerabilityReport) are returned as-is."""
        from vultron.wire.as2.vocab.objects.vulnerability_report import (
            as_VulnerabilityReport,
        )

        report = as_VulnerabilityReport(name="CVE-PLAIN", content="Body")
        dl.save(report)

        result = dl.read(report.id_)

        assert isinstance(result, VulnerabilityReport)
