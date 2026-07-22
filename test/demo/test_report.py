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
    build_timeline,
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
        assert event_phrase("validate_report") == "validated the report"

    def test_event_phrase_fallback_humanizes(self):
        assert event_phrase("some_novel_event") == "some novel event"

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

    def test_pipe_in_value_is_escaped(self):
        raw = _camel_entry(receivedAt="a|b")
        md = render_markdown(build_timeline({"vendor": [raw]}), ["vendor"])
        assert "a\\|b" in md

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

    def test_case_id_in_heading_is_escaped(self):
        """A case_id carrying markup is escaped in the <h2> heading."""
        raw = _camel_entry(caseId="urn:case:<x>", entryHash="a" * 64)
        out = render_html(build_timeline({"vendor": [raw]}), ["vendor"])
        assert "<h2>Case urn:case:&lt;x&gt;</h2>" in out
        assert "<x>" not in out


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
