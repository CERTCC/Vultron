"""Markdown and HTML rendering of a case timeline (DRPT-04)."""

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

from __future__ import annotations

import html
import logging
from datetime import datetime

from vultron.demo.report.timeline import (
    CaseTimelineEvent,
    group_events_by_case,
)

# One logger for the whole package, so log records keep its name.
logger = logging.getLogger(__package__)


# ---------------------------------------------------------------------------
# Rendering (DRPT-04)
# ---------------------------------------------------------------------------

_TABLE_HEADERS = [
    "#",
    "ΔT",
    "Actor",
    "Event",
    "Target",
    "RM",
    "EM",
    "CS",
    "Entry",
]


def _md_cell(text: str) -> str:
    """Escape a value for use inside a markdown table cell."""
    return text.replace("|", "\\|").replace("\n", " ")


def _parse_timestamp(ts: str) -> datetime:
    """Parse an ISO 8601 timestamp string to a timezone-aware datetime.

    Handles both ``Z`` suffix (``fromisoformat`` requires ``+00:00`` on
    Python < 3.11) and ``+00:00`` offset forms.
    """
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _format_delta(
    received_at: str | None,
    prev_received_at: str | None,
) -> str:
    """Return a compact delta string between two ``receivedAt`` timestamps.

    - Returns ``"—"`` when ``received_at`` is ``None`` (no timestamp on this row).
    - Returns ``"+0s"`` when ``prev_received_at`` is ``None`` and ``received_at``
      is set (first timestamped row — anchor point).
    - Returns ``"+Ns"`` / ``"+Nm Ns"`` / ``"+Nh Nm Ns"`` for a positive delta;
      no day component (spec: DRPT-04-007).
    """
    if received_at is None:
        return "—"
    if prev_received_at is None:
        return "+0s"
    try:
        dt_curr = _parse_timestamp(received_at)
        dt_prev = _parse_timestamp(prev_received_at)
    except ValueError:
        return "—"
    total_seconds = round((dt_curr - dt_prev).total_seconds())
    total_seconds = max(total_seconds, 0)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"+{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"+{minutes}m {seconds}s"
    return f"+{seconds}s"


def _case_time_range(
    events: list[CaseTimelineEvent],
) -> tuple[str | None, str | None]:
    """Return ``(min_received_at, max_received_at)`` for a list of events.

    Parses each ``received_at`` string via :func:`_parse_timestamp` so
    comparison is chronological regardless of offset notation (``Z`` vs
    ``+00:00``) or future microsecond precision changes. Returns ``(None,
    None)`` when no event carries a timestamp (DRPT-04-006).
    """
    pairs: list[tuple[str, datetime]] = []
    for e in events:
        if e.received_at is None:
            continue
        try:
            pairs.append((e.received_at, _parse_timestamp(e.received_at)))
        except ValueError:
            logger.debug("Skipping unparseable received_at: %r", e.received_at)
    if not pairs:
        return None, None
    first_str, _ = min(pairs, key=lambda p: p[1])
    last_str, _ = max(pairs, key=lambda p: p[1])
    return first_str, last_str


def _render_markdown_case(
    lines: list[str], events: list[CaseTimelineEvent], actors: list[str]
) -> None:
    """Append one case's markdown table (header + rows) to ``lines``."""
    headers = _TABLE_HEADERS + [_md_cell(a) for a in actors]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

    prev_ts: str | None = None
    for event in events:
        delta = _format_delta(event.received_at, prev_ts)
        if event.received_at is not None:
            prev_ts = event.received_at
        row = [
            str(event.log_index),
            _md_cell(delta),
            _md_cell(event.actor_label),
            _md_cell(event.summary),
            _md_cell(event.target_label or ""),
            _md_cell(event.rm_state or ""),
            _md_cell(event.em_state or ""),
            _md_cell(event.cs_state or ""),
            _md_cell(event.short_hash),
        ]
        row += ["✓" if a in event.present_in else "" for a in actors]
        lines.append("| " + " | ".join(row) + " |")


def render_markdown(events: list[CaseTimelineEvent], actors: list[str]) -> str:
    """Render the timeline as a markdown table report (DRPT-04-001).

    Events are partitioned by ``case_id`` into one ``## Case …`` section each
    (DRPT-02-006); within a section there is one row per canonical event over
    the distilled fields, followed by a per-actor replica-presence matrix
    column group (``✓`` = present).
    """
    by_case = group_events_by_case(events)
    lines: list[str] = ["# Case Timeline Report", ""]
    lines.append(f"- Events: {len(events)}")
    lines.append(f"- Cases: {len(by_case)}")
    lines.append(f"- Replicas: {', '.join(actors) if actors else '(none)'}")
    lines.append("")
    lines.append(
        "The trailing per-actor columns are the replica-presence matrix: "
        "`✓` marks the actor replicas that hold each canonical entry."
    )
    lines.append("")

    for case_id, case_events in by_case.items():
        lines.append(f"## Case {_md_cell(case_id or '(unknown)')}")
        lines.append("")
        first, last = _case_time_range(case_events)
        if first is not None and last is not None:
            lines.append(f"- Time range: {_md_cell(first)} – {_md_cell(last)}")
            lines.append("")
        _render_markdown_case(lines, case_events, actors)
        lines.append("")

    return "\n".join(lines).rstrip("\n") + "\n"


def _html_cell(text: str, title: str | None = None) -> str:
    """Return an escaped ``<td>`` cell, optionally with a ``title`` tooltip."""
    attr = f' title="{html.escape(title, quote=True)}"' if title else ""
    return f"<td{attr}>{html.escape(text)}</td>"


def _html_presence_row(event: CaseTimelineEvent, actors: list[str]) -> str:
    """Return the ``<td>`` cells for the replica-presence matrix (DRPT-04-003)."""
    cells: list[str] = []
    for actor in actors:
        present = actor in event.present_in
        symbol = "✅" if present else "⬜"
        label = "present" if present else "absent"
        cells.append(
            f'<td class="presence" title="{html.escape(actor)}: {label}">'
            f"{symbol}</td>"
        )
    return "".join(cells)


_HTML_STYLE = """
:root { color-scheme: light dark; }
body {
  font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  margin: 2rem; line-height: 1.4;
}
h1 { margin-bottom: 0.25rem; }
h2 { margin-top: 2rem; font-size: 1.1rem; }
.meta { color: #666; margin-bottom: 1rem; }
table { border-collapse: collapse; width: 100%; font-size: 0.9rem; }
th, td {
  border: 1px solid #ccc; padding: 0.35rem 0.5rem; text-align: left;
  vertical-align: top;
}
th { background: #f0f0f0; }
td.presence { text-align: center; }
th.presence-group { text-align: center; }
code { font-family: ui-monospace, monospace; }
""".strip()


def _render_html_case_table(
    events: list[CaseTimelineEvent], actors: list[str]
) -> str:
    """Return the ``<table>`` element for one case's events."""
    head_cells = "".join(f"<th>{html.escape(h)}</th>" for h in _TABLE_HEADERS)
    presence_head = "".join(
        f'<th class="presence-group" title="Replica presence: {html.escape(a)}">'
        f"{html.escape(a)}</th>"
        for a in actors
    )

    body_rows: list[str] = []
    prev_ts: str | None = None
    for event in events:
        delta = _format_delta(event.received_at, prev_ts)
        if event.received_at is not None:
            prev_ts = event.received_at
        cells = [
            _html_cell(str(event.log_index)),
            _html_cell(delta, title=event.received_at or None),
            _html_cell(event.actor_label, title=event.actor_uri or None),
            _html_cell(event.summary),
            _html_cell(
                event.target_label or "", title=event.target_ref or None
            ),
            _html_cell(event.rm_state or ""),
            _html_cell(event.em_state or ""),
            _html_cell(event.cs_state or ""),
            _html_cell(event.short_hash, title=event.entry_hash or None),
        ]
        body_rows.append(
            f"<tr>{''.join(cells)}{_html_presence_row(event, actors)}</tr>"
        )

    return (
        "<table>\n<thead>\n<tr>"
        f"{head_cells}{presence_head}</tr>\n</thead>\n<tbody>\n"
        + "\n".join(body_rows)
        + "\n</tbody>\n</table>"
    )


def render_html(events: list[CaseTimelineEvent], actors: list[str]) -> str:
    """Render the timeline as a self-contained static HTML report.

    All styling is inlined in a ``<style>`` block; the document references no
    external CSS, JS, fonts, or network assets, so it renders identically
    offline (DRPT-04-002). Events are partitioned by ``case_id`` into one
    ``<h2>Case …</h2>`` + table section each (DRPT-02-006). The per-actor
    replica-presence matrix is rendered as a per-actor emoji cell per event
    (DRPT-04-003). Full URIs/ids are retained only as ``title`` tooltips
    (DRPT-03-011).
    """
    by_case = group_events_by_case(events)
    sections: list[str] = []
    for case_id, case_events in by_case.items():
        first, last = _case_time_range(case_events)
        time_range_html = ""
        if first is not None and last is not None:
            time_range_html = (
                f'<p class="meta">Time range: {html.escape(first)}'
                f" – {html.escape(last)}</p>\n"
            )
        sections.append(
            f"<h2>Case {html.escape(case_id or '(unknown)')}</h2>\n"
            + time_range_html
            + _render_html_case_table(case_events, actors)
        )

    replicas_label = html.escape(", ".join(actors) if actors else "(none)")
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>Case Timeline Report</title>\n"
        f"<style>\n{_HTML_STYLE}\n</style>\n"
        "</head>\n<body>\n"
        "<h1>Case Timeline Report</h1>\n"
        f'<p class="meta">Events: {len(events)} &middot; '
        f"Cases: {len(by_case)} &middot; Replicas: {replicas_label}</p>\n"
        '<p class="meta">The trailing per-actor columns are the '
        "replica-presence matrix (✅ present, ⬜ absent).</p>\n"
        + "\n".join(sections)
        + "\n</body>\n</html>\n"
    )
