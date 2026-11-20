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

from test.support.act_clock import ACT_AT
from test.support.case_owner import CASE_OWNER_ID, INBOUND_CASE_OWNERSHIP
from test.support.future_dates import days_from_now
from test.support.objects import authored_at, make
from vultron.core.models.report import VulnerabilityReport
from vultron.wire.as2.factories import (
    add_log_entry_activity,
    em_propose_embargo_activity,
    rm_submit_report_activity,
)
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Add,
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

        report = make(
            as_VulnerabilityReport, name="CVE-TEST-001", content="Test body"
        )
        offer = rm_submit_report_activity(
            report,
            "https://alice.example.org",
            actor="https://alice.example.org",
            at=authored_at(),
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

        report = make(
            as_VulnerabilityReport, name="CVE-MISSING", content="Body"
        )
        offer = rm_submit_report_activity(
            report,
            "https://alice.example.org",
            actor="https://alice.example.org",
            at=authored_at(),
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
        from vultron.core.models.actor import CoreActor
        from vultron.wire.as2.vocab.base.objects.actors import (
            as_Actor,
            as_Organization,
        )

        org_id = "https://example.org/actors/target-org"
        org = make(as_Organization, id_=org_id, name="Target Org")
        dl.save(org)

        case_id = "urn:uuid:case-sqlite-coerce-00000000000001"
        # target is a bare string URI — must be expanded on read-back via recursion
        offer = make(
            as_Offer,
            object_=case_id,
            target=org_id,
            actor="https://example.org/actors/sender",
        )
        accept = make(
            as_Accept,
            object_=offer,
            actor="https://example.org/actors/accepter",
        )
        # Store Accept only; the Offer is kept inline by _KEEP_INLINE_NESTED_TYPES.
        # The org is found by _rehydrate_fields recursing into the inline Offer.
        dl.create(accept)

        stored = dl.read(accept.id_)

        assert stored is not None
        inline_offer = getattr(stored, "object_", None)
        assert inline_offer is not None, (
            "object_ should be present on stored Accept"
        )
        assert not isinstance(inline_offer, str), (
            "Accept.object_ should be the inline Offer, not a bare string"
        )
        assert not isinstance(inline_offer.target, str), (  # type: ignore[union-attr]
            f"Offer.target should be the typed actor after recursion,"
            f" not bare string {inline_offer.target!r}"  # type: ignore[union-attr]
        )
        assert isinstance(inline_offer.target, (as_Actor, CoreActor))  # type: ignore[union-attr]

    def test_minimal_peer_target_reads_back_as_its_actor_reference(self, dl):
        """A stored minimal peer fills a target as its actor reference.

        The abstract ``CoreActor`` record, kept when only the peer's URI is
        known (ADR-0159), has a core class name for its ``type``.  It fills
        the slot as an activity carries it, typed ``Actor`` (AKM-05-017), so
        the wire-only matcher still routes the embargo Invite (VM-06-013).
        """
        from vultron.core.models.actor import CoreActor
        from vultron.wire.as2.vocab.objects.embargo_event import (
            as_EmbargoEvent,
        )

        invitee = "https://example.org/actors/minimal-peer"
        dl.create(make(CoreActor, id_=invitee, published=None, updated=None))
        case_id = "urn:uuid:case-sqlite-coerce-minimal-peer"
        embargo = make(
            as_EmbargoEvent, context=case_id, end_time=days_from_now(45)
        )
        proposal = em_propose_embargo_activity(
            embargo,
            context=case_id,
            actor="https://example.org/actors/proposer",
            invitee=invitee,
            at=authored_at(),
        )
        dl.save(embargo)
        dl.save(proposal)

        result = dl.read(proposal.id_)

        assert type(result).__name__ == "_EmProposeEmbargoActivity"
        target = result.target  # type: ignore[union-attr]
        assert (target.id_, target.type_) == (invitee, "Actor")

    def test_typed_actor_target_reads_back_as_held(self, dl):
        """A stored actor of a concrete class fills a target as held."""
        from vultron.core.models.actor import VultronPerson

        person_id = "https://example.org/actors/a-person"
        dl.save(make(VultronPerson, id_=person_id, name="A Person"))
        invite = make(
            as_Invite,
            object_="https://example.org/things/x",
            target=person_id,
            actor="https://example.org/actors/sender",
        )
        dl.create(invite)

        result = dl.read(invite.id_)

        assert isinstance(result.target, VultronPerson)  # type: ignore[union-attr]
        assert result.target.type_ == "Person"  # type: ignore[union-attr]


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

        report = make(
            as_VulnerabilityReport, name="CVE-ROUND-TRIP", content="Body"
        )
        offer = rm_submit_report_activity(
            report,
            "https://alice.example.org",
            actor="https://alice.example.org",
            at=authored_at(),
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

        case = make(as_VulnerabilityCase, attributed_to=CASE_OWNER_ID)
        embargo = make(
            as_EmbargoEvent, context=case.id_, end_time=days_from_now(45)
        )
        proposal = em_propose_embargo_activity(
            embargo,
            context=case.id_,
            actor="https://alice.example.org",
            invitee="https://alice.example.org",
            at=authored_at(),
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
                    # Required on every inbound activity (ISSUE-3149).
                    "published": "2026-03-04T05:06:07+00:00",
                    "inReplyTo": "urn:uuid:invite-roundtrip-1",
                    "object": {
                        "type": "Invite",
                        "published": "2026-01-01T00:00:00+00:00",
                        "id": "urn:uuid:invite-roundtrip-1",
                        "actor": "https://example.org/actors/vendor",
                        "object": {
                            "type": "Organization",
                            "id": "https://example.org/actors/coordinator",
                            "name": "Coordinator",
                        },
                        "target": {
                            **INBOUND_CASE_OWNERSHIP,
                            "type": "VulnerabilityCase",
                            "published": "2026-01-01T00:00:00+00:00",
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
            make(
                as_Organization,
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

    def test_add_log_entry_round_trip_returns_specific_class(self, dl):
        """dl.read returns AddLogEntryActivity with as_CaseLedgerEntry object_."""
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
            semantic_type="log_entry_committed",
            payload_snapshot={
                "id": "https://example.org/activities/logged-1",
                "status": "ok",
            },
            prev_log_hash=_ZERO_HASH,
            received_at=ACT_AT,
        )
        entry = _to_persistable_entry(chain_entry)
        announce = add_log_entry_activity(
            entry,
            actor="https://example.org/actors/case-actor",
            at=authored_at(),
        )
        dl.save(entry)
        dl.save(announce)

        result = dl.read(announce.id_)

        assert isinstance(result, as_Add)
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
        domain-specific fields such as case_id and semantic_type.  With the recursive
        call, _retype_inline_object_refs runs again on the re-typed Offer's raw
        sub-data and restores the CaseLedgerEntry to its specific class.
        """
        from vultron.adapters.driven.db_record import Record
        from vultron.wire.as2.vocab.objects.case_ledger_entry import (
            as_CaseLedgerEntry,
        )

        ledger_entry = make(
            as_CaseLedgerEntry,
            case_id="https://example.org/cases/retype-recurse-1",
            log_object_id="https://example.org/activities/obj-retype-1",
            semantic_type="log_entry_committed",
            log_index=0,
            received_at=ACT_AT,
            published=ACT_AT,
        )
        offer = make(
            as_Offer,
            object_=ledger_entry,
            actor="https://example.org/actors/sender",
        )
        accept = make(
            as_Accept,
            object_=offer,
            actor="https://example.org/actors/accepter",
        )

        record = Record.from_obj(accept)
        result = record.to_obj()

        inner_offer = getattr(result, "object_", None)
        assert inner_offer is not None, (
            "Accept.object_ must be the inline Offer"
        )
        assert not isinstance(inner_offer, str), (
            "Accept.object_ must not collapse to a bare string"
        )
        inner_entry = getattr(inner_offer, "object_", None)
        assert isinstance(inner_entry, as_CaseLedgerEntry), (
            f"Offer.object_ should be re-typed to as_CaseLedgerEntry by recursive "
            f"_retype_inline_object_refs; got {type(inner_entry).__name__!r}"
        )
        assert (
            inner_entry.case_id == "https://example.org/cases/retype-recurse-1"
        )
        assert inner_entry.semantic_type == "log_entry_committed"

    def test_bare_object_activity_is_kept_as_its_base_class(self, dl):
        """A stored activity whose object cannot be rehydrated is not coerced.

        Its type is unknown (SE-01-006), so an ``Invite`` naming an object
        the store does not hold, in a case's context, is read back as an
        ``Invite``, not as the embargo proposal its verb's first pattern
        with a case context names.
        """
        invite = make(
            as_Invite,
            actor="https://alice.example.org",
            object_="https://example.org/cases/c1/embargo_events/unheld",
            context="https://example.org/cases/c1",
        )
        dl.save(invite)

        result = dl.read(invite.id_)

        assert type(result) is as_Invite
        assert result.object_ == (  # type: ignore[union-attr]
            "https://example.org/cases/c1/embargo_events/unheld"
        )

    def test_non_activity_object_not_coerced(self, dl):
        """Non-activity objects (e.g. as_VulnerabilityReport) are returned as-is."""
        from vultron.wire.as2.vocab.objects.vulnerability_report import (
            as_VulnerabilityReport,
        )

        report = make(as_VulnerabilityReport, name="CVE-PLAIN", content="Body")
        dl.save(report)

        result = dl.read(report.id_)

        assert isinstance(result, VulnerabilityReport)


class TestCoerceByReferenceFields:
    """A by-reference field rehydration expanded coerces by id (#5513).

    The stored row's base class (``as_Read``, ``as_Invite``) admits an
    object in the field, so :func:`rehydrate_fields` expands it, and the
    pattern match needs the expanded type.  The semantic class declares the
    field a plain URI, so coercion must hand it the object's id, not the
    object: a correct dispatch logs no WARNING (SL-01-005).
    """

    def test_read_ledger_round_trips_without_warning(self, dl, caplog):
        """A stored Read(<case>/ledger) reads back as _ReadLedgerActivity."""
        import logging

        from vultron.core.behaviors.sync.nodes.chain import (
            _to_persistable_entry,
        )
        from vultron.core.models.case_ledger import HashChainLedgerRecord
        from vultron.wire.as2.factories import read_ledger_at_entry_activity

        entry = _to_persistable_entry(
            HashChainLedgerRecord(
                case_id="https://example.org/cases/case-read-5513",
                log_index=0,
                object_id="https://example.org/activities/logged-5513",
                semantic_type="log_entry_committed",
                payload_snapshot={
                    "id": "https://example.org/activities/logged-5513",
                    "status": "ok",
                },
                prev_log_hash=_ZERO_HASH,
                received_at=ACT_AT,
            )
        )
        read = read_ledger_at_entry_activity(
            entry,
            actor="https://example.org/actors/reporter",
            at=authored_at(),
        )
        dl.save(entry)
        dl.save(read)

        with caplog.at_level(logging.WARNING):
            result = dl.read(read.id_)

        assert type(result).__name__ == "_ReadLedgerActivity"
        # The ledger has no record of its own, so it is kept inline
        # (ADR-0204).
        assert result.object_.id_ == (  # type: ignore[union-attr]
            "https://example.org/cases/case-read-5513/ledger"
        )
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]

    def test_full_case_invite_round_trips_without_warning(self, dl, caplog):
        """A stored full-case Invite reads back as _RmInviteToFullCaseActivity."""
        import logging

        from vultron.core.models.ledger_position import LedgerPosition
        from vultron.wire.as2.factories import rm_invite_to_full_case_activity
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        case = make(as_VulnerabilityCase, attributed_to=CASE_OWNER_ID)
        invite = rm_invite_to_full_case_activity(
            "https://example.org/actors/vendor",
            case,
            LedgerPosition(log_index=0, entry_hash=_ZERO_HASH),
            actor="https://example.org/actors/case-actor",
            at=authored_at(),
        )
        dl.save(case)
        dl.save(invite)

        with caplog.at_level(logging.WARNING):
            result = dl.read(invite.id_)

        assert type(result).__name__ == "_RmInviteToFullCaseActivity"
        # The case rides whole in ``object`` and the invitee in ``target``
        # (ADR-0205).
        assert result.object_.id_ == case.id_  # type: ignore[union-attr]
        assert (
            result.target.id_  # type: ignore[union-attr]
            == "https://example.org/actors/vendor"
        )
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]

    def test_full_case_invite_reply_round_trips_without_warning(
        self, dl, caplog
    ):
        """A stored Accept(full-case Invite) coerces its embedded Invite too.

        The Invite rides inline in the reply, carrying the case whole in its
        ``object`` (ADR-0205); the reply's class embeds the full-case Invite
        class, which the read-back still validates as (#5513).
        """
        import logging

        from vultron.core.models.ledger_position import LedgerPosition
        from vultron.wire.as2.factories import (
            rm_accept_full_case_invite_activity,
            rm_invite_to_full_case_activity,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        case = make(as_VulnerabilityCase, attributed_to=CASE_OWNER_ID)
        position = LedgerPosition(log_index=0, entry_hash=_ZERO_HASH)
        invite = rm_invite_to_full_case_activity(
            "https://example.org/actors/vendor",
            case,
            position,
            actor="https://example.org/actors/case-actor",
            at=authored_at(),
        )
        accept = rm_accept_full_case_invite_activity(
            invite,
            position,
            actor="https://example.org/actors/vendor",
            at=authored_at(),
        )
        dl.save(case)
        dl.save(invite)
        dl.save(accept)

        with caplog.at_level(logging.WARNING):
            result = dl.read(accept.id_)

        assert type(result).__name__ == "_RmAcceptFullCaseInviteActivity"
        assert result.object_.object_.id_ == case.id_  # type: ignore[union-attr]
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


class TestCollapseByReferenceFields:
    """Each branch of ``_collapse_by_reference_fields`` (#5513).

    ``_AddStatusToCaseActivity.target`` is a by-reference field: the class
    declares it a plain URI, the case's status history (ADR-0204).
    """

    _HISTORY = "https://example.org/cases/case-5513/statuses"

    @staticmethod
    def _add(target: object) -> object:
        from vultron.wire.as2.vocab.base.objects.activities.transitive import (
            as_Add,
        )

        return as_Add.model_construct(
            id_="https://example.org/activities/add-5513",
            actor="https://example.org/actors/case-actor",
            object_="https://example.org/cases/case-5513/status/1",
            target=target,
            context="https://example.org/cases/case-5513",
        )

    @staticmethod
    def _collapse(obj: object, semantics: str) -> object:
        from vultron.adapters.driven.datalayer_sqlite.hydration.coercion import (
            _collapse_by_reference_fields,
        )
        from vultron.core.models.events import MessageSemantics
        from vultron.semantic_registry import semantics_to_activity_class

        return _collapse_by_reference_fields(
            obj,  # type: ignore[arg-type]
            semantics_to_activity_class()[MessageSemantics[semantics]],
        )

    def test_object_collapses_to_its_id(self):
        from vultron.wire.as2.vocab.base.objects.collections import (
            as_OrderedCollection,
        )

        history = make(as_OrderedCollection, id_=self._HISTORY)
        result = self._collapse(self._add(history), "ADD_CASE_STATUS_TO_CASE")
        assert result.target == self._HISTORY  # type: ignore[attr-defined]

    def test_bare_id_is_left_alone(self):
        add = self._add(self._HISTORY)
        assert self._collapse(add, "ADD_CASE_STATUS_TO_CASE") is add

    def test_object_without_an_id_is_left_alone(self):
        from vultron.wire.as2.vocab.base.objects.base import as_Object

        nameless = as_Object.model_construct(id_=None)
        add = self._add(nameless)
        assert self._collapse(add, "ADD_CASE_STATUS_TO_CASE") is add

    def test_field_that_admits_an_object_keeps_it(self):
        """The full-case Invite carries the case whole in ``object``
        (ADR-0205), so a case there is kept."""
        from vultron.wire.as2.vocab.base.objects.activities.transitive import (
            as_Invite,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        case = make(as_VulnerabilityCase, attributed_to=CASE_OWNER_ID)
        invite = as_Invite.model_construct(
            id_="https://example.org/activities/invite-5513",
            actor="https://example.org/actors/case-actor",
            object_=case,
            target="https://example.org/actors/vendor",
        )
        assert self._collapse(invite, "INVITE_ACTOR_TO_FULL_CASE") is invite
