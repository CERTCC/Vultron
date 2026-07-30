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

"""Tests for the demo scenario report tool (DRPT-05).

Covers JSONL→distilled-model parsing (camelCase + snake_case tolerance,
field extraction, merge/de-dup by ``entry_hash``, per-actor replica presence),
both renderers (markdown table structure, self-contained HTML), and a CLI
smoke test (exit code 0, file written, ``--no-open`` honored) plus the
non-zero-exit error paths (DRPT-01-004).
"""

import json
from pathlib import Path

import pytest

from vultron.demo import report
from vultron.demo.report import (
    CaseTimelineEvent,
    ReportError,
    _case_time_range,
    _format_delta,
    _parse_timestamp,
    build_timeline,
    collect_actor_names,
    discover_replicas,
    event_phrase,
    friendly_actor_name,
    friendly_target_noun,
    generate_report,
    group_events_by_case,
    main,
    render_html,
    render_markdown,
)

# ---------------------------------------------------------------------------
# Fixture builders — raw JSONL entry dicts in both spellings
# ---------------------------------------------------------------------------


def _camel_entry(**overrides):
    """A raw ledger entry using camelCase keys (as written to JSONL)."""
    entry = {
        "id": "urn:case:1/log/0",
        "type": "CaseLedgerEntry",
        "caseId": "urn:case:1",
        "logIndex": 0,
        "disposition": "recorded",
        "logObjectId": "urn:uuid:act0",
        "eventType": "validate_report",
        "payloadSnapshot": {
            "type": "Accept",
            "actor": "http://vendor:7999/api/v2/actors/vendor",
            "object": {"id": "urn:uuid:rep1", "type": "VulnerabilityReport"},
            "context": "urn:case:1",
        },
        "prevLogHash": "a" * 64,
        "entryHash": "c0ffee" + "0" * 58,
        "receivedAt": "2026-07-01T12:00:00Z",
    }
    entry.update(overrides)
    return entry


def _snake_entry(**overrides):
    """A raw ledger entry using snake_case keys (tolerance check)."""
    entry = {
        "case_id": "urn:case:1",
        "log_index": 1,
        "disposition": "recorded",
        "event_type": "add_participant_status_to_participant",
        "payload_snapshot": {
            "type": "Add",
            "actor": "http://finder:7999/api/v2/actors/finder",
            "object": {
                "id": "urn:uuid:ps1",
                "type": "ParticipantStatus",
                "attributed_to": "http://finder:7999/api/v2/actors/finder",
                "rm": {"state": "ACCEPTED"},
                "vfd": {"state": "VFd"},
                "case_status": {"pxa": {"state": "Pxa"}},
            },
        },
        "prev_log_hash": "c0ffee" + "0" * 58,
        "entry_hash": "beef" + "0" * 60,
        "received_at": "2026-07-01T13:00:00Z",
    }
    entry.update(overrides)
    return entry


def _write_replicas(root: Path, layout: dict[str, list[dict]]) -> Path:
    """Write ``{actor: [entries]}`` as devlogs JSONL files; return the root."""
    for actor, entries in layout.items():
        actor_dir = root / "demo" / actor
        actor_dir.mkdir(parents=True, exist_ok=True)
        out = actor_dir / "urn_case_1-case-ledger.jsonl"
        with out.open("w", encoding="utf-8") as fh:
            for entry in entries:
                fh.write(json.dumps(entry) + "\n")
    return root


# ---------------------------------------------------------------------------
# DRPT-02 / DRPT-03 — distilled model parsing and friendly naming
# ---------------------------------------------------------------------------


class TestCaseTimelineEventParsing:
    def test_camelcase_field_extraction(self):
        event = CaseTimelineEvent.from_raw(_camel_entry())
        assert event.log_index == 0
        assert event.event_type == "validate_report"
        assert event.actor_uri == "http://vendor:7999/api/v2/actors/vendor"
        assert event.target_ref == "urn:uuid:rep1"
        assert event.target_type == "VulnerabilityReport"
        assert event.received_at == "2026-07-01T12:00:00Z"
        assert event.entry_hash == "c0ffee" + "0" * 58

    def test_snakecase_field_extraction(self):
        event = CaseTimelineEvent.from_raw(_snake_entry())
        assert event.log_index == 1
        assert event.event_type == "add_participant_status_to_participant"
        assert event.actor_uri == "http://finder:7999/api/v2/actors/finder"

    def test_dimension_states_from_nested_object(self):
        """RM/VFD/PXA states extracted from a nested ParticipantStatus."""
        event = CaseTimelineEvent.from_raw(_snake_entry())
        assert event.rm_state == "ACCEPTED"
        assert event.vfd_state == "VFd"
        assert event.pxa_state == "Pxa"
        assert event.cs_state == "VFd · Pxa"

    def test_dimension_states_from_flat_wire_shape(self):
        """Legacy flat ``rmState``/``vfdState`` spellings are tolerated."""
        raw = _camel_entry(
            eventType="add_participant_status_to_participant",
            payloadSnapshot={
                "type": "Add",
                "actor": "http://vendor:7999/api/v2/actors/vendor",
                "object": {
                    "id": "urn:uuid:ps2",
                    "type": "ParticipantStatus",
                    "rmState": "CLOSED",
                    "vfdState": "VFD",
                },
            },
        )
        event = CaseTimelineEvent.from_raw(raw)
        assert event.rm_state == "CLOSED"
        assert event.vfd_state == "VFD"

    def test_pec_state_from_consent_dimension_object(self):
        """PEC state extracted from ADR-0036 consent dimension object."""
        raw = _snake_entry(
            payload_snapshot={
                "type": "Add",
                "actor": "http://finder:7999/api/v2/actors/finder",
                "object": {
                    "id": "urn:uuid:ps2",
                    "type": "ParticipantStatus",
                    "consent": {"state": "SIGNATORY"},
                },
            }
        )
        event = CaseTimelineEvent.from_raw(raw)
        assert event.pec_state == "SIGNATORY"

    def test_pec_state_from_flat_em_consent_state(self):
        """Legacy emConsentState flat field tolerated."""
        raw = _camel_entry(
            eventType="add_participant_status_to_participant",
            payloadSnapshot={
                "type": "Add",
                "actor": "http://vendor:7999/api/v2/actors/vendor",
                "object": {
                    "id": "urn:uuid:ps3",
                    "type": "ParticipantStatus",
                    "emConsentState": "INVITED",
                },
            },
        )
        event = CaseTimelineEvent.from_raw(raw)
        assert event.pec_state == "INVITED"

    def test_pec_state_from_flat_embargo_consent_state(self):
        """Legacy embargoConsentState flat field tolerated."""
        raw = _camel_entry(
            eventType="add_participant_status_to_participant",
            payloadSnapshot={
                "type": "Add",
                "actor": "http://vendor:7999/api/v2/actors/vendor",
                "object": {
                    "id": "urn:uuid:ps4",
                    "type": "ParticipantStatus",
                    "embargoConsentState": "DECLINED",
                },
            },
        )
        event = CaseTimelineEvent.from_raw(raw)
        assert event.pec_state == "DECLINED"

    def test_pec_state_from_flat_em_consent_state_snake(self):
        """Legacy em_consent_state snake_case short form tolerated."""
        raw = _snake_entry(
            payload_snapshot={
                "type": "Add",
                "actor": "http://finder:7999/api/v2/actors/finder",
                "object": {
                    "id": "urn:uuid:ps5",
                    "type": "ParticipantStatus",
                    "em_consent_state": "SIGNATORY",
                },
            }
        )
        event = CaseTimelineEvent.from_raw(raw)
        assert event.pec_state == "SIGNATORY"

    def test_pec_state_from_flat_embargo_consent_state_snake(self):
        """Legacy embargo_consent_state snake_case long form tolerated."""
        raw = _snake_entry(
            payload_snapshot={
                "type": "Add",
                "actor": "http://finder:7999/api/v2/actors/finder",
                "object": {
                    "id": "urn:uuid:ps6",
                    "type": "ParticipantStatus",
                    "embargo_consent_state": "LAPSED",
                },
            }
        )
        event = CaseTimelineEvent.from_raw(raw)
        assert event.pec_state == "LAPSED"

    def test_pec_state_absent_when_not_in_payload(self):
        """pec_state is None when no consent field is present."""
        event = CaseTimelineEvent.from_raw(_camel_entry())
        assert event.pec_state is None

    def test_em_state_from_case_status(self):
        raw = _camel_entry(
            eventType="add_case_status_to_case",
            payloadSnapshot={
                "type": "Add",
                "actor": "http://vendor:7999/api/v2/actors/vendor",
                "object": {
                    "id": "urn:uuid:cs1",
                    "type": "CaseStatus",
                    "em": {"state": "ACTIVE"},
                    "pxa": {"state": "pxa"},
                },
            },
        )
        event = CaseTimelineEvent.from_raw(raw)
        assert event.em_state == "ACTIVE"

    def test_em_state_from_case_statuses_array(self):
        """EM/CS state extracted from caseStatuses array on VulnerabilityCase."""
        raw = _camel_entry(
            eventType="offer_case_manager_role",
            payloadSnapshot={
                "type": "Offer",
                "actor": "http://vendor:7999/api/v2/actors/case-actor",
                "object": {
                    "id": "urn:uuid:case1",
                    "type": "VulnerabilityCase",
                    "caseStatuses": [
                        {"em": {"state": "ACTIVE"}, "pxa": {"state": "Pxa"}},
                    ],
                },
            },
        )
        event = CaseTimelineEvent.from_raw(raw)
        assert event.em_state == "ACTIVE"
        assert event.pxa_state == "Pxa"

    def test_em_state_from_case_statuses_snake_key(self):
        """case_statuses (snake_case) is also traversed."""
        raw = _camel_entry(
            eventType="offer_case_manager_role",
            payloadSnapshot={
                "type": "Offer",
                "actor": "http://vendor:7999/api/v2/actors/case-actor",
                "object": {
                    "id": "urn:uuid:case1",
                    "type": "VulnerabilityCase",
                    "case_statuses": [
                        {"em": {"state": "PROPOSED"}, "pxa": {"state": "pxa"}},
                    ],
                },
            },
        )
        event = CaseTimelineEvent.from_raw(raw)
        assert event.em_state == "PROPOSED"

    def test_case_statuses_non_list_does_not_crash(self):
        """A non-list caseStatuses value (e.g. corrupt data) is silently ignored."""
        raw = _camel_entry(
            payloadSnapshot={
                "type": "Offer",
                "actor": "http://vendor:7999/api/v2/actors/case-actor",
                "object": {
                    "id": "urn:uuid:case1",
                    "type": "VulnerabilityCase",
                    "caseStatuses": "not-a-list",
                },
            },
        )
        event = CaseTimelineEvent.from_raw(raw)
        assert event.em_state is None

    def test_missing_actor_yields_em_dash_label(self):
        raw = _camel_entry(payloadSnapshot={"type": "Create"})
        event = CaseTimelineEvent.from_raw(raw)
        assert event.actor_uri is None
        assert event.actor_label == "—"

    def test_bare_string_object_reference(self):
        raw = _camel_entry(
            payloadSnapshot={
                "type": "Accept",
                "actor": "http://vendor/actors/vendor",
                "object": "urn:uuid:rep-bare",
            }
        )
        event = CaseTimelineEvent.from_raw(raw)
        assert event.target_ref == "urn:uuid:rep-bare"
        assert event.target_type is None

    def test_accept_wrapper_unwrapped_to_inner_object(self):
        """Accept(object=VulnerabilityReport) → target_type is the report, not Accept."""
        raw = _camel_entry(
            payloadSnapshot={
                "type": "Add",
                "actor": "http://vendor/actors/vendor",
                "object": {
                    "type": "Accept",
                    "object": {
                        "id": "urn:uuid:rep2",
                        "type": "VulnerabilityReport",
                    },
                },
            }
        )
        event = CaseTimelineEvent.from_raw(raw)
        assert event.target_type == "VulnerabilityReport"
        assert event.target_ref == "urn:uuid:rep2"

    def test_nested_wrapper_unwrapped_two_levels(self):
        """Accept(Offer(VulnerabilityReport)) → unwrap both wrappers."""
        raw = _camel_entry(
            payloadSnapshot={
                "type": "Accept",
                "actor": "http://vendor/actors/vendor",
                "object": {
                    "type": "Offer",
                    "object": {
                        "id": "urn:uuid:rep3",
                        "type": "VulnerabilityReport",
                    },
                },
            }
        )
        event = CaseTimelineEvent.from_raw(raw)
        assert event.target_type == "VulnerabilityReport"
        assert event.target_ref == "urn:uuid:rep3"

    def test_invite_wrapper_surfaces_inner_target(self):
        """Accept(Invite(object=Org, target=Case)) → org → case arrow label."""
        raw = _camel_entry(
            eventType="accept_invite_actor_to_case",
            payloadSnapshot={
                "type": "Accept",
                "actor": "http://coordinator/actors/coordinator",
                "object": {
                    "type": "Invite",
                    "object": {
                        "id": "http://coordinator/actors/coordinator",
                        "type": "Organization",
                    },
                    "target": {
                        "id": "urn:uuid:case1",
                        "type": "VulnerabilityCase",
                    },
                },
            },
        )
        event = CaseTimelineEvent.from_raw(raw)
        assert event.target_type == "Organization"
        assert event.target_ref == "http://coordinator/actors/coordinator"
        assert event.activity_target_type == "VulnerabilityCase"
        assert event.target_label == "Coordinator → case"

    def test_offer_with_as_target_populates_activity_target(self):
        """Offer(object=VulnerabilityCase, target=CaseParticipant) → arrow label."""
        raw = _camel_entry(
            eventType="offer_case_manager_role",
            payloadSnapshot={
                "type": "Offer",
                "actor": "http://vendor/actors/case-actor",
                "object": {
                    "id": "urn:uuid:case1",
                    "type": "VulnerabilityCase",
                },
                "target": {
                    "id": "urn:uuid:p1",
                    "type": "CaseParticipant",
                    "attributedTo": "http://vendor/actors/case-actor",
                },
            },
        )
        event = CaseTimelineEvent.from_raw(raw)
        assert event.target_type == "VulnerabilityCase"
        assert event.activity_target_type == "CaseParticipant"
        assert event.target_label == "case → Case Actor"

    def test_short_hash_truncation(self):
        event = CaseTimelineEvent.from_raw(_camel_entry())
        assert event.short_hash == ("c0ffee" + "0" * 58)[:12]
        assert len(event.short_hash) == 12

    def test_non_integer_log_index_degrades_not_crashes(self):
        """A corrupt logIndex coerces to -1 rather than raising ValueError."""
        event = CaseTimelineEvent.from_raw(_camel_entry(logIndex="oops"))
        assert event.log_index == -1

    def test_inline_actor_object_tolerated(self):
        """An inline actor object (not a bare URI) is normalized, not fatal."""
        raw = _camel_entry(
            payloadSnapshot={
                "type": "Accept",
                "actor": {
                    "id": "http://vendor:7999/api/v2/actors/vendor",
                    "type": "Service",
                },
                "object": {"id": "urn:uuid:r", "type": "VulnerabilityReport"},
            }
        )
        event = CaseTimelineEvent.from_raw(raw)
        assert event.actor_uri == "http://vendor:7999/api/v2/actors/vendor"
        assert event.actor_label == "Vendor"


class TestFriendlyNaming:
    def test_actor_name_from_uri(self):
        assert (
            friendly_actor_name("http://vendor:7999/api/v2/actors/finder")
            == "Finder"
        )

    def test_actor_name_hyphenated(self):
        assert (
            friendly_actor_name("http://x/actors/case-actor") == "Case Actor"
        )

    def test_actor_name_drops_uuid_suffix(self):
        label = friendly_actor_name("http://x/actors/case-actor-abc123def456")
        assert label == "Case Actor"

    def test_actor_name_none(self):
        assert friendly_actor_name(None) == "—"

    def test_target_noun_known(self):
        assert friendly_target_noun("VulnerabilityReport") == "report"
        assert friendly_target_noun("Note") == "note"

    def test_target_noun_unknown_camelcase_split(self):
        assert friendly_target_noun("SomeNewThing") == "some new thing"

    def test_target_noun_none(self):
        assert friendly_target_noun(None) is None

    def test_event_phrase_known(self):
        # event_phrase() delegates to the SemanticEntry phrase template;
        # named slots are filled with "—" when no slot values are supplied.
        assert event_phrase("validate_report") == "— validated the report"

    def test_event_phrase_fallback_humanizes(self):
        assert event_phrase("some_novel_event") == "some novel event"

    def test_summary_unknown_event_type_humanizes(self):
        """DRPT-03-002: unknown event_type falls back to humanized phrase, capitalised."""
        raw = _camel_entry(eventType="some_novel_event")
        event = CaseTimelineEvent.from_raw(raw)
        assert event.summary == "Some novel event"

    def test_summary_is_active_voice(self):
        event = CaseTimelineEvent.from_raw(_camel_entry())
        assert event.summary == "Vendor validated the report"

    def test_summary_marks_rejected_disposition(self):
        event = CaseTimelineEvent.from_raw(
            _camel_entry(disposition="rejected")
        )
        assert event.summary.endswith("[rejected]")

    def test_summary_no_uri_or_uuid(self):
        """DRPT-03-001: summaries must not contain bare URIs/UUIDs."""
        event = CaseTimelineEvent.from_raw(_camel_entry())
        assert "http" not in event.summary
        assert "urn:uuid" not in event.summary

    def test_summary_no_actor_uri_capitalises_verb(self):
        """When actor_uri is absent the em-dash prefix is dropped and the
        summary is capitalised so it reads as a sentence (DRPT-03-004)."""
        raw = _camel_entry(payloadSnapshot={"type": "Create"})
        event = CaseTimelineEvent.from_raw(raw)
        assert event.actor_uri is None
        assert event.summary == "Validated the report"

    def test_summary_create_case_proposal_has_no_dangling_target(self):
        """CREATE_CASE_PROPOSAL renders without a dangling em-dash (#1787).

        The proposal ``Create`` has no ``target``, so the old
        ``"{actor} proposed a case to {target}"`` phrase rendered
        ``"Vendor proposed a case to —"``.  The summary must read as a
        complete sentence with no trailing/dangling ``"—"``.
        """
        raw = _camel_entry(
            eventType="create_case_proposal",
            payloadSnapshot={
                "type": "Create",
                "actor": "http://vendor:7999/api/v2/actors/vendor",
                "context": "urn:case:1",
            },
        )
        event = CaseTimelineEvent.from_raw(raw)
        assert event.summary == "Vendor proposed a new case"
        assert "—" not in event.summary


# ---------------------------------------------------------------------------
# DRPT-05-005 — _format_delta unit tests (AC-6)
# ---------------------------------------------------------------------------


class TestFormatDelta:
    def test_both_none_returns_em_dash(self):
        assert _format_delta(None, None) == "—"

    def test_received_at_none_returns_em_dash(self):
        assert _format_delta(None, "2026-07-01T12:00:00Z") == "—"

    def test_first_row_no_prev_returns_plus_zero_s(self):
        assert _format_delta("2026-07-01T12:00:00Z", None) == "+0s"

    def test_sub_minute_delta(self):
        assert (
            _format_delta("2026-07-01T12:00:45Z", "2026-07-01T12:00:00Z")
            == "+45s"
        )

    def test_sub_hour_delta(self):
        assert (
            _format_delta("2026-07-01T12:03:15Z", "2026-07-01T12:00:00Z")
            == "+3m 15s"
        )

    def test_multi_hour_delta(self):
        assert (
            _format_delta("2026-07-01T14:03:15Z", "2026-07-01T12:00:00Z")
            == "+2h 3m 15s"
        )

    def test_exact_one_minute(self):
        assert (
            _format_delta("2026-07-01T12:01:00Z", "2026-07-01T12:00:00Z")
            == "+1m 0s"
        )

    def test_exact_one_hour(self):
        assert (
            _format_delta("2026-07-01T13:00:00Z", "2026-07-01T12:00:00Z")
            == "+1h 0m 0s"
        )

    def test_zero_delta_same_timestamp(self):
        assert (
            _format_delta("2026-07-01T12:00:00Z", "2026-07-01T12:00:00Z")
            == "+0s"
        )

    def test_unparseable_received_at_returns_em_dash(self):
        assert _format_delta("not-a-timestamp", "2026-07-01T12:00:00Z") == "—"

    def test_unparseable_prev_returns_em_dash(self):
        assert _format_delta("2026-07-01T12:00:00Z", "bad") == "—"

    def test_negative_delta_clamped_to_zero(self):
        """Out-of-order rows clamp to +0s rather than producing a negative string."""
        assert (
            _format_delta("2026-07-01T11:00:00Z", "2026-07-01T13:00:00Z")
            == "+0s"
        )

    def test_offset_notation_accepted(self):
        assert (
            _format_delta(
                "2026-07-01T12:00:30+00:00", "2026-07-01T12:00:00+00:00"
            )
            == "+30s"
        )


# ---------------------------------------------------------------------------
# DRPT-02-004 / DRPT-02-005 — merge, dedup, presence
# ---------------------------------------------------------------------------


class TestBuildTimeline:
    def test_merge_dedup_by_entry_hash(self):
        shared = _camel_entry()  # same entry_hash in both replicas
        vendor_only = _snake_entry()  # only vendor holds it
        replicas = {
            "finder": [dict(shared)],
            "vendor": [dict(shared), dict(vendor_only)],
        }
        events = build_timeline(replicas)
        # shared entry de-duplicated → 2 canonical events, not 3.
        assert len(events) == 2

    def test_ordered_by_log_index(self):
        replicas = {
            "vendor": [
                _snake_entry(),  # log_index 1
                _camel_entry(),  # log_index 0
            ],
        }
        events = build_timeline(replicas)
        assert [e.log_index for e in events] == [0, 1]

    def test_presence_matrix(self):
        shared = _camel_entry()
        vendor_only = _snake_entry()
        replicas = {
            "finder": [dict(shared)],
            "vendor": [dict(shared), dict(vendor_only)],
        }
        events = build_timeline(replicas)
        by_index = {e.log_index: e for e in events}
        assert by_index[0].present_in == ["finder", "vendor"]
        assert by_index[1].present_in == ["vendor"]

    def test_hashless_entries_not_collapsed(self):
        """Degenerate entries without entry_hash are not merged together."""
        a = _camel_entry(entryHash="", logIndex=0, eventType="create_case")
        b = _camel_entry(entryHash="", logIndex=1, eventType="close_case")
        events = build_timeline({"vendor": [a, b]})
        assert len(events) == 2

    def test_rejected_entries_excluded(self):
        """disposition=rejected entries are silently dropped (DRPT-02-007)."""
        recorded = _camel_entry(logIndex=0, entryHash="a" * 64)
        rejected = _camel_entry(
            logIndex=1,
            entryHash="b" * 64,
            disposition="rejected",
            payloadSnapshot={},
        )
        events = build_timeline({"vendor": [recorded, rejected]})
        assert len(events) == 1
        assert events[0].log_index == 0

    def test_only_rejected_entries_yields_empty_timeline(self):
        """A replica with only rejected entries produces an empty timeline."""
        r1 = _camel_entry(
            logIndex=0, entryHash="a" * 64, disposition="rejected"
        )
        r2 = _camel_entry(
            logIndex=1, entryHash="b" * 64, disposition="rejected"
        )
        events = build_timeline({"vendor": [r1, r2]})
        assert events == []


# ---------------------------------------------------------------------------
# DRPT-02-006 — multi-case partitioning (no cross-case interleaving)
# ---------------------------------------------------------------------------


def _case_entry(case_id, log_index, entry_hash, **overrides):
    """A camelCase entry scoped to an explicit case_id / log_index / hash."""
    return _camel_entry(
        caseId=case_id,
        logIndex=log_index,
        entryHash=entry_hash,
        **overrides,
    )


class TestMultiCasePartitioning:
    def test_case_id_extracted(self):
        assert (
            CaseTimelineEvent.from_raw(_camel_entry()).case_id == "urn:case:1"
        )
        assert (
            CaseTimelineEvent.from_raw(_snake_entry()).case_id == "urn:case:1"
        )

    def test_events_not_interleaved_across_cases(self):
        """Two cases whose log_index both restart at 0 stay contiguous."""
        replicas = {
            "vendor": [
                _case_entry("urn:case:B", 0, "b0" + "0" * 62),
                _case_entry("urn:case:A", 0, "a0" + "0" * 62),
                _case_entry("urn:case:B", 1, "b1" + "0" * 62),
                _case_entry("urn:case:A", 1, "a1" + "0" * 62),
            ],
        }
        events = build_timeline(replicas)
        # Case-contiguous ordering: all of A, then all of B — never 0,0,1,1.
        assert [(e.case_id, e.log_index) for e in events] == [
            ("urn:case:A", 0),
            ("urn:case:A", 1),
            ("urn:case:B", 0),
            ("urn:case:B", 1),
        ]

    def test_group_events_by_case(self):
        replicas = {
            "vendor": [
                _case_entry("urn:case:A", 0, "a0" + "0" * 62),
                _case_entry("urn:case:B", 0, "b0" + "0" * 62),
                _case_entry("urn:case:A", 1, "a1" + "0" * 62),
            ],
        }
        grouped = group_events_by_case(build_timeline(replicas))
        assert list(grouped) == ["urn:case:A", "urn:case:B"]
        assert [e.log_index for e in grouped["urn:case:A"]] == [0, 1]
        assert [e.log_index for e in grouped["urn:case:B"]] == [0]

    def test_presence_matrix_is_per_case(self):
        """Same actor dir name across cases must not conflate presence."""
        replicas = {
            "finder": [_case_entry("urn:case:A", 0, "a0" + "0" * 62)],
            "vendor": [_case_entry("urn:case:B", 0, "b0" + "0" * 62)],
        }
        events = build_timeline(replicas)
        by_case = {e.case_id: e for e in events}
        # Case A only in finder's replica; case B only in vendor's — the two
        # actor directories are NOT merged into a single shared presence set.
        assert by_case["urn:case:A"].present_in == ["finder"]
        assert by_case["urn:case:B"].present_in == ["vendor"]


# ---------------------------------------------------------------------------
# DRPT-04 — renderers
# ---------------------------------------------------------------------------


def _sample_events():
    replicas = {
        "finder": [_camel_entry()],
        "vendor": [_camel_entry(), _snake_entry()],
    }
    return build_timeline(replicas), ["finder", "vendor"]


class TestMarkdownRenderer:
    def test_table_structure(self):
        events, actors = _sample_events()
        md = render_markdown(events, actors)
        lines = md.splitlines()
        header = next(ln for ln in lines if ln.startswith("| #"))
        # Distilled field columns + one column per actor.
        assert "| finder | vendor |" in header
        assert "Actor" in header and "Event" in header
        assert "| PEC |" in header
        # Separator row present.
        sep_idx = lines.index(header) + 1
        assert set(lines[sep_idx].replace("|", "").split()) == {"---"}

    def test_one_row_per_event(self):
        events, actors = _sample_events()
        md = render_markdown(events, actors)
        data_rows = [
            ln
            for ln in md.splitlines()
            if ln.startswith("| ") and "---" not in ln and "#" not in ln[:3]
        ]
        assert len(data_rows) == len(events)

    def test_presence_check_marks(self):
        events, actors = _sample_events()
        md = render_markdown(events, actors)
        assert "✓" in md

    def test_summary_appears(self):
        events, actors = _sample_events()
        md = render_markdown(events, actors)
        assert "Vendor validated the report" in md

    def test_pipe_in_actor_dir_name_is_escaped(self):
        """Actor column headers must be cell-escaped like data cells."""
        md = render_markdown(
            build_timeline({"ven|dor": [_camel_entry()]}), ["ven|dor"]
        )
        header = next(ln for ln in md.splitlines() if ln.startswith("| #"))
        assert "ven\\|dor" in header
        assert "| ven|dor |" not in header  # no unescaped column-break

    def test_one_section_per_case(self):
        """Each distinct case_id gets its own ## Case … section (DRPT-02-006)."""
        replicas = {
            "vendor": [
                _camel_entry(caseId="urn:case:A", entryHash="a" * 64),
                _camel_entry(caseId="urn:case:B", entryHash="b" * 64),
            ],
        }
        md = render_markdown(build_timeline(replicas), ["vendor"])
        assert "## Case urn:case:A" in md
        assert "## Case urn:case:B" in md
        assert "- Cases: 2" in md
        # Two header rows — one table per case.
        assert sum(1 for ln in md.splitlines() if ln.startswith("| #")) == 2

    def test_time_column_header_is_delta_t(self):
        """AC-7: ΔT header appears in markdown table (DRPT-04-007)."""
        events, actors = _sample_events()
        md = render_markdown(events, actors)
        header = next(ln for ln in md.splitlines() if ln.startswith("| #"))
        assert "| ΔT |" in header

    def test_time_cells_contain_delta_strings_not_iso(self):
        """AC-7: Time cells show +0s / +Ns, not ISO 8601 timestamps (DRPT-04-007)."""
        replicas = {
            "vendor": [
                _camel_entry(
                    logIndex=0,
                    entryHash="a" * 64,
                    receivedAt="2026-07-01T12:00:00Z",
                ),
                _camel_entry(
                    logIndex=1,
                    entryHash="b" * 64,
                    receivedAt="2026-07-01T12:00:30Z",
                ),
            ],
        }
        events = build_timeline(replicas)
        md = render_markdown(events, ["vendor"])
        data_rows = [
            ln
            for ln in md.splitlines()
            if ln.startswith("| ") and "---" not in ln and "| #" not in ln
        ]
        assert len(data_rows) == 2
        assert "+0s" in data_rows[0]
        assert "+30s" in data_rows[1]
        # ISO timestamps must not appear in the table body cells.
        for row in data_rows:
            assert "2026-07-01T" not in row

    def test_prev_ts_carries_through_none_timestamp_row(self):
        """A None-timestamp row must not reset the prev_ts anchor (DRPT-04-007)."""
        replicas = {
            "vendor": [
                _camel_entry(
                    logIndex=0,
                    entryHash="a" * 64,
                    receivedAt="2026-07-01T12:00:00Z",
                ),
                _camel_entry(
                    logIndex=1,
                    entryHash="b" * 64,
                    receivedAt=None,
                ),
                _camel_entry(
                    logIndex=2,
                    entryHash="c" * 64,
                    receivedAt="2026-07-01T12:01:30Z",
                ),
            ],
        }
        events = build_timeline(replicas)
        md = render_markdown(events, ["vendor"])
        data_rows = [
            ln
            for ln in md.splitlines()
            if ln.startswith("| ") and "---" not in ln and "| #" not in ln
        ]
        assert len(data_rows) == 3
        assert "+0s" in data_rows[0]
        assert "—" in data_rows[1]
        # Third row delta is from row 0 (T+0), not row 1 (which had no ts).
        assert "+1m 30s" in data_rows[2]


class TestHtmlRenderer:
    def test_well_formed_document(self):
        events, actors = _sample_events()
        out = render_html(events, actors)
        assert out.startswith("<!DOCTYPE html>")
        assert "<table>" in out and "</table>" in out
        assert out.rstrip().endswith("</html>")

    def test_self_contained_no_external_assets(self):
        """DRPT-04-002: no external CSS/JS/font/network references.

        Full URIs may appear only inside ``title=`` tooltips (secondary
        detail per DRPT-03-001), never as loaded assets — so this asserts the
        absence of ``<link>``/``<script>`` tags and of any ``src``/``href``
        attribute, rather than the absence of the substring ``http``.
        """
        # No actor URIs in the sample here, so no tooltips carry URLs either.
        replicas = {"vendor": [_camel_entry(payloadSnapshot={"type": "X"})]}
        out = render_html(build_timeline(replicas), ["vendor"])
        assert "<style>" in out
        assert "<link" not in out
        assert "<script" not in out
        assert "src=" not in out
        assert "href=" not in out
        assert "http://" not in out
        assert "https://" not in out

    def test_presence_matrix_emoji_cells(self):
        events, actors = _sample_events()
        out = render_html(events, actors)
        assert "✅" in out  # present
        assert "⬜" in out  # absent (finder lacks the vendor-only entry)

    def test_full_uri_retained_as_tooltip(self):
        """DRPT-03-001: full ids allowed only as secondary detail (title=)."""
        events, actors = _sample_events()
        out = render_html(events, actors)
        assert 'title="http://vendor:7999/api/v2/actors/vendor"' in out

    def test_html_escaping(self):
        raw = _camel_entry(
            payloadSnapshot={
                "type": "Accept",
                "actor": "http://x/actors/<script>",
                "object": {"id": "urn:uuid:o", "type": "Note"},
            }
        )
        out = render_html(build_timeline({"vendor": [raw]}), ["vendor"])
        # The malicious actor segment is escaped, not emitted as a live tag.
        assert "&lt;script&gt;" in out

    def test_one_section_per_case(self):
        """Each distinct case_id gets its own <h2>Case …</h2> (DRPT-02-006)."""
        replicas = {
            "vendor": [
                _camel_entry(caseId="urn:case:A", entryHash="a" * 64),
                _camel_entry(caseId="urn:case:B", entryHash="b" * 64),
            ],
        }
        out = render_html(build_timeline(replicas), ["vendor"])
        assert "<h2>Case urn:case:A</h2>" in out
        assert "<h2>Case urn:case:B</h2>" in out
        assert out.count("<table>") == 2
        assert "Cases: 2" in out

    def test_time_column_header_is_delta_t(self):
        """AC-7: ΔT header appears in HTML table (DRPT-04-007)."""
        events, actors = _sample_events()
        out = render_html(events, actors)
        assert "<th>ΔT</th>" in out

    def test_time_cells_contain_delta_strings_not_iso(self):
        """AC-7: Time cells show +0s / +Ns, not ISO 8601 in cell body (DRPT-04-007)."""
        replicas = {
            "vendor": [
                _camel_entry(
                    logIndex=0,
                    entryHash="a" * 64,
                    receivedAt="2026-07-01T12:00:00Z",
                ),
                _camel_entry(
                    logIndex=1,
                    entryHash="b" * 64,
                    receivedAt="2026-07-01T12:00:45Z",
                ),
            ],
        }
        events = build_timeline(replicas)
        out = render_html(events, ["vendor"])
        assert ">+0s<" in out
        assert ">+45s<" in out

    def test_time_cell_iso_retained_as_tooltip(self):
        """AC-7: Full ISO timestamp retained as title= tooltip on ΔT <td> (DRPT-04-007)."""
        replicas = {
            "vendor": [
                _camel_entry(
                    logIndex=0,
                    entryHash="a" * 64,
                    receivedAt="2026-07-01T12:00:00Z",
                ),
            ],
        }
        events = build_timeline(replicas)
        out = render_html(events, ["vendor"])
        assert 'title="2026-07-01T12:00:00Z"' in out

    def test_time_cell_no_tooltip_when_no_timestamp(self):
        """AC-7: No title= attribute when received_at is absent (no ISO to show)."""
        replicas = {
            "vendor": [
                _camel_entry(
                    logIndex=0,
                    entryHash="a" * 64,
                    receivedAt=None,
                ),
            ],
        }
        events = build_timeline(replicas)
        out = render_html(events, ["vendor"])
        # ΔT cell must be <td>—</td> (no title= attribute when no timestamp).
        assert "<td>—</td>" in out

    def test_case_id_in_heading_is_escaped(self):
        """A case_id carrying markup is escaped in the <h2> heading."""
        raw = _camel_entry(caseId="urn:case:<x>", entryHash="a" * 64)
        out = render_html(build_timeline({"vendor": [raw]}), ["vendor"])
        assert "<h2>Case urn:case:&lt;x&gt;</h2>" in out
        assert "<x>" not in out


# ---------------------------------------------------------------------------
# DRPT-02-008 — PEC column in renderers
# ---------------------------------------------------------------------------


def _pec_entry(pec_value: str, **overrides):
    """A raw ledger entry carrying a ParticipantStatus with a consent dimension."""
    return _camel_entry(
        eventType="add_participant_status_to_participant",
        payloadSnapshot={
            "type": "Add",
            "actor": "http://vendor:7999/api/v2/actors/vendor",
            "object": {
                "id": "urn:uuid:ps_pec",
                "type": "ParticipantStatus",
                "consent": {"state": pec_value},
                "rm": {"state": "ACCEPTED"},
            },
        },
        **overrides,
    )


class TestPecColumn:
    def test_pec_state_appears_in_markdown_table(self):
        replicas = {"vendor": [_pec_entry("SIGNATORY")]}
        md = render_markdown(build_timeline(replicas), ["vendor"])
        assert "| PEC |" in md
        assert "SIGNATORY" in md

    def test_pec_state_absent_renders_empty_cell_markdown(self):
        """An entry without PEC state renders an empty PEC cell, not an error."""
        replicas = {"vendor": [_camel_entry()]}
        md = render_markdown(build_timeline(replicas), ["vendor"])
        assert "| PEC |" in md

    def test_pec_state_appears_in_html_table(self):
        replicas = {"vendor": [_pec_entry("LAPSED")]}
        out = render_html(build_timeline(replicas), ["vendor"])
        assert "<th>PEC</th>" in out
        assert "LAPSED" in out

    def test_pec_state_absent_renders_empty_cell_html(self):
        replicas = {"vendor": [_camel_entry()]}
        out = render_html(build_timeline(replicas), ["vendor"])
        assert "<th>PEC</th>" in out

    def test_pec_flat_em_consent_state_extracted(self):
        """Legacy emConsentState flat field surfaces in the report."""
        raw = _camel_entry(
            eventType="add_participant_status_to_participant",
            payloadSnapshot={
                "type": "Add",
                "actor": "http://vendor:7999/api/v2/actors/vendor",
                "object": {
                    "id": "urn:uuid:ps_flat",
                    "type": "ParticipantStatus",
                    "emConsentState": "INVITED",
                },
            },
        )
        replicas = {"vendor": [raw]}
        md = render_markdown(build_timeline(replicas), ["vendor"])
        assert "INVITED" in md

    def test_pec_flat_embargo_consent_state_extracted(self):
        """Legacy embargoConsentState camelCase form surfaces in the report."""
        raw = _camel_entry(
            eventType="add_participant_status_to_participant",
            payloadSnapshot={
                "type": "Add",
                "actor": "http://vendor:7999/api/v2/actors/vendor",
                "object": {
                    "id": "urn:uuid:ps_long",
                    "type": "ParticipantStatus",
                    "embargoConsentState": "DECLINED",
                },
            },
        )
        replicas = {"vendor": [raw]}
        md = render_markdown(build_timeline(replicas), ["vendor"])
        assert "DECLINED" in md


# ---------------------------------------------------------------------------
# DRPT-04-006 — per-case time range
# ---------------------------------------------------------------------------


class TestParseTimestamp:
    def test_z_suffix_parsed(self):
        dt = _parse_timestamp("2026-07-01T12:00:00Z")
        assert dt.tzinfo is not None

    def test_offset_notation_parsed(self):
        dt = _parse_timestamp("2026-07-01T12:00:00+00:00")
        assert dt.tzinfo is not None

    def test_z_and_offset_equal(self):
        assert _parse_timestamp("2026-07-01T12:00:00Z") == _parse_timestamp(
            "2026-07-01T12:00:00+00:00"
        )


class TestCaseTimeRange:
    def test_no_timestamps_returns_none_none(self):
        events = [
            CaseTimelineEvent.from_raw(_camel_entry(receivedAt=None)),
            CaseTimelineEvent.from_raw(
                _camel_entry(entryHash="b" * 64, logIndex=1, receivedAt=None)
            ),
        ]
        assert _case_time_range(events) == (None, None)

    def test_empty_list_returns_none_none(self):
        assert _case_time_range([]) == (None, None)

    def test_returns_min_max_for_multi_event_case(self):
        events = [
            CaseTimelineEvent(
                case_id="urn:case:1",
                log_index=0,
                entry_hash="a" * 64,
                received_at="2026-07-01T10:00:00Z",
            ),
            CaseTimelineEvent(
                case_id="urn:case:1",
                log_index=1,
                entry_hash="b" * 64,
                received_at="2026-07-01T12:00:00Z",
            ),
            CaseTimelineEvent(
                case_id="urn:case:1",
                log_index=2,
                entry_hash="c" * 64,
                received_at="2026-07-01T11:00:00Z",
            ),
        ]
        first, last = _case_time_range(events)
        assert first == "2026-07-01T10:00:00Z"
        assert last == "2026-07-01T12:00:00Z"

    def test_single_timestamp_min_equals_max(self):
        events = [
            CaseTimelineEvent(
                case_id="urn:case:1",
                log_index=0,
                entry_hash="a" * 64,
                received_at="2026-07-01T10:00:00Z",
            ),
        ]
        first, last = _case_time_range(events)
        assert first == last == "2026-07-01T10:00:00Z"

    def test_ignores_none_timestamps_in_mixed_list(self):
        events = [
            CaseTimelineEvent(
                case_id="urn:case:1",
                log_index=0,
                entry_hash="a" * 64,
                received_at=None,
            ),
            CaseTimelineEvent(
                case_id="urn:case:1",
                log_index=1,
                entry_hash="b" * 64,
                received_at="2026-07-01T10:00:00Z",
            ),
        ]
        first, last = _case_time_range(events)
        assert first == last == "2026-07-01T10:00:00Z"

    def test_z_and_offset_notation_compared_chronologically(self):
        """Z suffix and +00:00 offset represent the same instant; sort by value."""
        events = [
            CaseTimelineEvent(
                case_id="urn:case:1",
                log_index=0,
                entry_hash="a" * 64,
                received_at="2026-07-01T12:00:00+00:00",
            ),
            CaseTimelineEvent(
                case_id="urn:case:1",
                log_index=1,
                entry_hash="b" * 64,
                received_at="2026-07-01T10:00:00Z",
            ),
        ]
        first, last = _case_time_range(events)
        assert first == "2026-07-01T10:00:00Z"
        assert last == "2026-07-01T12:00:00+00:00"


class TestMarkdownRendererTimeRange:
    def test_time_range_bullet_present_when_timestamps_exist(self):
        replicas = {"vendor": [_camel_entry()]}
        events = build_timeline(replicas)
        md = render_markdown(events, ["vendor"])
        assert (
            "- Time range: 2026-07-01T12:00:00Z – 2026-07-01T12:00:00Z" in md
        )

    def test_time_range_bullet_omitted_when_no_timestamps(self):
        replicas = {"vendor": [_camel_entry(receivedAt=None)]}
        events = build_timeline(replicas)
        md = render_markdown(events, ["vendor"])
        assert "Time range:" not in md

    def test_time_range_shows_min_max_across_events(self):
        replicas = {
            "vendor": [
                _camel_entry(
                    logIndex=0,
                    entryHash="a" * 64,
                    receivedAt="2026-07-01T10:00:00Z",
                ),
                _camel_entry(
                    logIndex=1,
                    entryHash="b" * 64,
                    receivedAt="2026-07-01T14:00:00Z",
                ),
            ],
        }
        events = build_timeline(replicas)
        md = render_markdown(events, ["vendor"])
        assert "2026-07-01T10:00:00Z" in md
        assert "2026-07-01T14:00:00Z" in md
        assert "Time range:" in md


class TestHtmlRendererTimeRange:
    def test_time_range_meta_present_when_timestamps_exist(self):
        replicas = {"vendor": [_camel_entry()]}
        events = build_timeline(replicas)
        out = render_html(events, ["vendor"])
        assert '<p class="meta">Time range: 2026-07-01T12:00:00Z' in out

    def test_time_range_meta_omitted_when_no_timestamps(self):
        replicas = {"vendor": [_camel_entry(receivedAt=None)]}
        events = build_timeline(replicas)
        out = render_html(events, ["vendor"])
        assert "Time range:" not in out

    def test_time_range_shows_min_max_across_events(self):
        replicas = {
            "vendor": [
                _camel_entry(
                    logIndex=0,
                    entryHash="a" * 64,
                    receivedAt="2026-07-01T09:00:00Z",
                ),
                _camel_entry(
                    logIndex=1,
                    entryHash="b" * 64,
                    receivedAt="2026-07-01T15:00:00Z",
                ),
            ],
        }
        events = build_timeline(replicas)
        out = render_html(events, ["vendor"])
        assert "2026-07-01T09:00:00Z" in out
        assert "2026-07-01T15:00:00Z" in out
        assert "Time range:" in out


# ---------------------------------------------------------------------------
# DRPT-01 — discovery and error paths
# ---------------------------------------------------------------------------


class TestDiscovery:
    def test_discovers_and_groups_by_actor_dir(self, tmp_path):
        _write_replicas(
            tmp_path,
            {"finder": [_camel_entry()], "vendor": [_camel_entry()]},
        )
        replicas = discover_replicas(tmp_path)
        assert set(replicas) == {"finder", "vendor"}
        assert len(replicas["finder"]) == 1

    def test_missing_directory_raises(self, tmp_path):
        with pytest.raises(ReportError, match="does not exist"):
            discover_replicas(tmp_path / "nope")

    def test_no_matching_files_raises(self, tmp_path):
        (tmp_path / "empty").mkdir()
        with pytest.raises(ReportError, match="No.*files found"):
            discover_replicas(tmp_path)

    def test_parse_error_raises(self, tmp_path):
        actor_dir = tmp_path / "demo" / "vendor"
        actor_dir.mkdir(parents=True)
        (actor_dir / "x-case-ledger.jsonl").write_text(
            "{not valid json\n", encoding="utf-8"
        )
        with pytest.raises(ReportError, match="Parse error"):
            discover_replicas(tmp_path)

    def test_blank_lines_skipped(self, tmp_path):
        actor_dir = tmp_path / "demo" / "vendor"
        actor_dir.mkdir(parents=True)
        (actor_dir / "x-case-ledger.jsonl").write_text(
            json.dumps(_camel_entry()) + "\n\n", encoding="utf-8"
        )
        replicas = discover_replicas(tmp_path)
        assert len(replicas["vendor"]) == 1


class TestGenerateReport:
    def test_markdown_end_to_end(self, tmp_path):
        _write_replicas(tmp_path, {"vendor": [_camel_entry()]})
        out = generate_report(tmp_path, "markdown")
        assert out.startswith("# Case Timeline Report")

    def test_html_end_to_end(self, tmp_path):
        _write_replicas(tmp_path, {"vendor": [_camel_entry()]})
        out = generate_report(tmp_path, "html")
        assert out.startswith("<!DOCTYPE html>")


# ---------------------------------------------------------------------------
# DRPT-05-003 — CLI smoke test
# ---------------------------------------------------------------------------


class TestCli:
    def test_exit_zero_and_file_written(self, tmp_path):
        _write_replicas(tmp_path, {"vendor": [_camel_entry()]})
        out_file = tmp_path / "report.md"
        rc = main([str(tmp_path), "--output", str(out_file)])
        assert rc == 0
        assert out_file.exists()
        assert out_file.read_text(encoding="utf-8").startswith(
            "# Case Timeline Report"
        )

    def test_no_open_suppresses_browser(self, tmp_path, monkeypatch):
        _write_replicas(tmp_path, {"vendor": [_camel_entry()]})
        calls: list[str] = []
        monkeypatch.setattr(
            report.webbrowser, "open", lambda url: calls.append(url)
        )
        out_file = tmp_path / "report.html"
        rc = main(
            [
                str(tmp_path),
                "--format",
                "html",
                "--output",
                str(out_file),
                "--no-open",
            ]
        )
        assert rc == 0
        assert out_file.exists()
        assert calls == []

    def test_html_opens_browser_without_no_open(self, tmp_path, monkeypatch):
        _write_replicas(tmp_path, {"vendor": [_camel_entry()]})
        calls: list[str] = []
        monkeypatch.setattr(
            report.webbrowser, "open", lambda url: calls.append(url)
        )
        out_file = tmp_path / "report.html"
        rc = main(
            [str(tmp_path), "--format", "html", "--output", str(out_file)]
        )
        assert rc == 0
        assert len(calls) == 1
        assert calls[0].startswith("file://")

    def test_missing_dir_nonzero_exit(self, tmp_path):
        rc = main([str(tmp_path / "nope")])
        assert rc == 1

    def test_no_files_nonzero_exit(self, tmp_path):
        rc = main([str(tmp_path)])
        assert rc == 1

    def test_default_output_path(self, tmp_path):
        _write_replicas(tmp_path, {"vendor": [_camel_entry()]})
        rc = main([str(tmp_path), "--format", "html"])
        assert rc == 0
        assert (tmp_path / "case-timeline-report.html").exists()

    def test_devlogs_dir_env_default(self, tmp_path, monkeypatch):
        _write_replicas(tmp_path, {"vendor": [_camel_entry()]})
        monkeypatch.setenv("DEVLOGS_DIR", str(tmp_path))
        out_file = tmp_path / "out.md"
        rc = main(["--output", str(out_file)])
        assert rc == 0
        assert out_file.exists()


# ---------------------------------------------------------------------------
# DRPT-03 — actor name resolution from payload snapshots
# ---------------------------------------------------------------------------

#: A UUID-based actor URI that produces a hex-fragment label without name resolution.
_UUID_ACTOR_URI = (
    "http://vendor:7999/api/v2/actors/9e580519-a1e7-421f-b727-9c09af18815a"
)


def _entry_with_named_actor(**overrides):
    """A camelCase ledger entry whose actor is an inline Organization with a name."""
    return _camel_entry(
        payloadSnapshot={
            "type": "Accept",
            "actor": {
                "id": _UUID_ACTOR_URI,
                "type": "Organization",
                "name": "Vendor",
            },
            "object": {"id": "urn:uuid:rep1", "type": "VulnerabilityReport"},
        },
        **overrides,
    )


def _entry_with_uuid_actor(**overrides):
    """A camelCase ledger entry whose actor is a bare UUID-based URI."""
    return _camel_entry(
        payloadSnapshot={
            "type": "Accept",
            "actor": _UUID_ACTOR_URI,
            "object": {"id": "urn:uuid:rep2", "type": "VulnerabilityReport"},
        },
        **overrides,
    )


class TestActorNameResolution:
    def test_collect_actor_names_extracts_id_name_pairs(self):
        replicas = {"vendor": [_entry_with_named_actor()]}
        names = collect_actor_names(replicas)
        assert _UUID_ACTOR_URI in names
        assert names[_UUID_ACTOR_URI] == "Vendor"

    def test_collect_actor_names_ignores_objects_without_name(self):
        entry = _camel_entry(
            payloadSnapshot={
                "type": "Accept",
                "actor": {"id": _UUID_ACTOR_URI, "type": "Organization"},
                "object": {"id": "urn:uuid:r", "type": "VulnerabilityReport"},
            }
        )
        names = collect_actor_names({"vendor": [entry]})
        assert _UUID_ACTOR_URI not in names

    def test_collect_actor_names_first_writer_wins(self):
        """When two entries carry the same URI, the first name is kept."""
        e1 = _entry_with_named_actor(entryHash="a" * 64)
        e2 = _camel_entry(
            entryHash="b" * 64,
            payloadSnapshot={
                "type": "Accept",
                "actor": {
                    "id": _UUID_ACTOR_URI,
                    "type": "Organization",
                    "name": "SomeOtherName",
                },
                "object": {"id": "urn:uuid:r2", "type": "VulnerabilityReport"},
            },
        )
        names = collect_actor_names({"vendor": [e1, e2]})
        assert names[_UUID_ACTOR_URI] == "Vendor"

    def test_collect_actor_names_empty_name_ignored(self):
        entry = _camel_entry(
            payloadSnapshot={
                "type": "Accept",
                "actor": {
                    "id": _UUID_ACTOR_URI,
                    "type": "Organization",
                    "name": "   ",
                },
                "object": {"id": "urn:uuid:r", "type": "VulnerabilityReport"},
            }
        )
        names = collect_actor_names({"vendor": [entry]})
        assert _UUID_ACTOR_URI not in names

    def test_collect_actor_names_scans_list_valued_actor_field(self):
        """A list-valued ``actor`` field harvests names from each element."""
        other_uri = "http://vendor:7999/api/v2/actors/other-uuid"
        entry = _camel_entry(
            payloadSnapshot={
                "type": "Announce",
                "actor": [
                    {
                        "id": _UUID_ACTOR_URI,
                        "type": "Organization",
                        "name": "Vendor",
                    },
                    {"id": other_uri, "type": "Person", "name": "Finder"},
                ],
                "object": {"id": "urn:uuid:r", "type": "VulnerabilityReport"},
            }
        )
        names = collect_actor_names({"vendor": [entry]})
        assert names[_UUID_ACTOR_URI] == "Vendor"
        assert names[other_uri] == "Finder"

    def test_collect_actor_names_scans_list_valued_object_field(self):
        """A list-valued ``object`` field recurses into each element."""
        entry = _camel_entry(
            payloadSnapshot={
                "type": "Create",
                "actor": "http://vendor:7999/api/v2/actors/vendor",
                "object": [
                    {"id": "urn:uuid:r", "type": "VulnerabilityReport"},
                    {
                        "id": _UUID_ACTOR_URI,
                        "type": "CaseActor",
                        "name": "CaseManager",
                    },
                ],
            }
        )
        names = collect_actor_names({"vendor": [entry]})
        assert names[_UUID_ACTOR_URI] == "CaseManager"

    def test_collect_actor_names_scans_list_valued_target_field(self):
        """A list-valued ``target`` field recurses into each element."""
        entry = _camel_entry(
            payloadSnapshot={
                "type": "Offer",
                "actor": "http://vendor:7999/api/v2/actors/vendor",
                "object": {"id": "urn:uuid:c", "type": "VulnerabilityCase"},
                "target": [
                    {
                        "id": _UUID_ACTOR_URI,
                        "type": "Person",
                        "name": "Coordinator",
                    },
                ],
            }
        )
        names = collect_actor_names({"vendor": [entry]})
        assert names[_UUID_ACTOR_URI] == "Coordinator"

    def test_collect_actor_names_scans_list_valued_origin_field(self):
        """A list-valued ``origin`` field recurses into each element."""
        entry = _camel_entry(
            payloadSnapshot={
                "type": "Move",
                "actor": "http://vendor:7999/api/v2/actors/vendor",
                "origin": [
                    {
                        "id": _UUID_ACTOR_URI,
                        "type": "Group",
                        "name": "OriginGroup",
                    },
                ],
            }
        )
        names = collect_actor_names({"vendor": [entry]})
        assert names[_UUID_ACTOR_URI] == "OriginGroup"

    def test_collect_actor_names_list_edge_cases_are_safe_noops(self):
        """Empty, scalar, None, mixed, and nested lists never raise or leak."""
        entry = _camel_entry(
            payloadSnapshot={
                "type": "Announce",
                # empty list
                "actor": [],
                # list of scalars/None mixed with a valid actor dict
                "object": [
                    "http://vendor:7999/api/v2/actors/scalar",
                    None,
                    {
                        "id": _UUID_ACTOR_URI,
                        "type": "Person",
                        "name": "MixedActor",
                    },
                ],
                # nested list-of-lists still reaches the inner actor dict
                "target": [
                    [
                        {
                            "id": "http://vendor:7999/api/v2/actors/nested",
                            "type": "Organization",
                            "name": "NestedActor",
                        },
                    ],
                ],
            }
        )
        names = collect_actor_names({"vendor": [entry]})
        assert names[_UUID_ACTOR_URI] == "MixedActor"
        assert (
            names["http://vendor:7999/api/v2/actors/nested"] == "NestedActor"
        )

    def test_friendly_actor_name_uses_actor_names_map(self):
        names = {_UUID_ACTOR_URI: "Vendor"}
        assert (
            friendly_actor_name(_UUID_ACTOR_URI, actor_names=names) == "Vendor"
        )

    def test_friendly_actor_name_falls_back_without_map(self):
        """Without actor_names, UUID-based URIs get a hex-fragment label, not 'Vendor'."""
        label = friendly_actor_name(_UUID_ACTOR_URI)
        assert label != "Vendor"

    def test_friendly_actor_name_falls_back_for_unknown_uri(self):
        names = {"http://other/actors/someone": "Someone"}
        label = friendly_actor_name(
            "http://vendor:7999/api/v2/actors/finder", actor_names=names
        )
        assert label == "Finder"

    def test_build_timeline_populates_actor_display_name(self):
        """actor_display_name is set when the actor URI appears in payloads."""
        entry_with_name = _entry_with_named_actor(entryHash="a" * 64)
        entry_uuid_only = _entry_with_uuid_actor(
            entryHash="b" * 64, logIndex=1
        )
        replicas = {"vendor": [entry_with_name, entry_uuid_only]}
        events = build_timeline(replicas)
        by_hash = {e.entry_hash: e for e in events}
        named = by_hash["a" * 64]
        uuid_only = by_hash["b" * 64]
        # Both events share the same actor URI; the name is resolved for both
        # because collect_actor_names scans all entries before assigning.
        assert named.actor_display_name == "Vendor"
        assert uuid_only.actor_display_name == "Vendor"

    def test_actor_label_uses_display_name_over_uri_heuristic(self):
        """actor_label returns display name instead of hex-fragment label."""
        entry = _entry_with_named_actor()
        replicas = {"vendor": [entry]}
        events = build_timeline(replicas)
        assert events[0].actor_label == "Vendor"

    def test_actor_label_fallback_when_no_display_name(self):
        """When no display name is found, actor_label falls back to URI segment."""
        entry = _camel_entry(
            payloadSnapshot={
                "type": "Accept",
                "actor": "http://vendor:7999/api/v2/actors/finder",
                "object": {"id": "urn:uuid:r", "type": "VulnerabilityReport"},
            }
        )
        replicas = {"vendor": [entry]}
        events = build_timeline(replicas)
        assert events[0].actor_label == "Finder"

    def test_build_timeline_populates_target_display_name(self):
        """target_display_name is set when the target URI is a known actor."""
        entry = _camel_entry(
            payloadSnapshot={
                "type": "Invite",
                "actor": "http://vendor:7999/api/v2/actors/case-actor",
                "object": {
                    "id": _UUID_ACTOR_URI,
                    "type": "Organization",
                    "name": "Vendor",
                },
            }
        )
        replicas = {"vendor": [entry]}
        events = build_timeline(replicas)
        assert events[0].target_display_name == "Vendor"
        assert events[0].target_label == "Vendor"

    def test_build_timeline_populates_activity_target_display_name(self):
        """activity_target_display_name is set when activity_target_ref is a known actor."""
        entry = _camel_entry(
            eventType="accept_invite_actor_to_case",
            payloadSnapshot={
                "type": "Accept",
                "actor": "http://vendor:7999/api/v2/actors/case-actor",
                "object": {
                    "type": "Invite",
                    "object": {
                        "id": _UUID_ACTOR_URI,
                        "type": "Organization",
                        "name": "Vendor",
                    },
                    "target": {
                        "id": "urn:uuid:case1",
                        "type": "VulnerabilityCase",
                    },
                },
            },
        )
        replicas = {"vendor": [entry]}
        events = build_timeline(replicas)
        # activity_target_ref is "urn:uuid:case1" — not an actor, so no display name.
        # But the object (Vendor) should have its target_display_name set.
        assert events[0].target_display_name == "Vendor"
        # activity_target is a VulnerabilityCase URI, not an actor, so no display name.
        assert events[0].activity_target_display_name is None

    def test_build_timeline_populates_activity_target_display_name_uuid_actor(
        self,
    ):
        """activity_target_display_name set when activity_target is a UUID actor."""
        entry = _camel_entry(
            eventType="offer_case_manager_role",
            payloadSnapshot={
                "type": "Offer",
                "actor": "http://vendor:7999/api/v2/actors/case-actor",
                "object": {
                    "id": "urn:uuid:case1",
                    "type": "VulnerabilityCase",
                },
                "target": {
                    "id": _UUID_ACTOR_URI,
                    "type": "Organization",
                    "name": "Vendor",
                    "attributedTo": _UUID_ACTOR_URI,
                },
            },
        )
        replicas = {"vendor": [entry]}
        events = build_timeline(replicas)
        assert events[0].activity_target_display_name == "Vendor"
        assert events[0].target_label == "case → Vendor"

    def test_summary_no_hex_fragments_with_uuid_actor(self):
        """DRPT-03-001: summaries must not contain hex fragments for UUID actors."""
        entry = _entry_with_named_actor()
        replicas = {"vendor": [entry]}
        events = build_timeline(replicas)
        summary = events[0].summary
        assert "9e580519" not in summary
        assert "Vendor" in summary


# ---------------------------------------------------------------------------
# Console-script entry point (pyproject [project.scripts])
# ---------------------------------------------------------------------------


class TestConsoleScript:
    """Guard the ``vultron-demo-report`` console-script wiring (DRPT-01-005).

    Console-script wrappers invoke the target ``main`` with **no** arguments
    and propagate its return value via ``sys.exit`` — so the entry point must
    resolve to a real callable that accepts zero args. This has been a latent
    breakage source for other demo entry points (see the BT-demo learning on
    zero-arg ``main``); assert it directly rather than only via ``python -m``.
    """

    def test_entry_point_registered_and_resolves_to_main(self):
        from importlib.metadata import entry_points

        scripts = entry_points(group="console_scripts")
        matches = [e for e in scripts if e.name == "vultron-demo-report"]
        assert matches, "vultron-demo-report console script is not registered"
        assert matches[0].value == "vultron.demo.report:main"
        # Resolving the entry point must yield our main() callable.
        assert matches[0].load() is main

    def test_main_callable_with_no_args(self, tmp_path, monkeypatch):
        """main() must run with zero positional args (console-script contract)."""
        _write_replicas(tmp_path, {"vendor": [_camel_entry()]})
        monkeypatch.setenv("DEVLOGS_DIR", str(tmp_path))
        monkeypatch.setattr("sys.argv", ["vultron-demo-report"])
        rc = main()
        assert rc == 0
        assert (tmp_path / "case-timeline-report.md").exists()
