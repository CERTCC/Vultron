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
"""Text and JSON report rendering (SR-12-005)."""

from __future__ import annotations

import json

from vultron.metadata.specs.backstop._model import (
    MAX_EVIDENCE,
    MONOLITH_GROUP_SPAN,
    GroupHit,
    BackstopReport,
)


def _group_line(hit: GroupHit) -> str:
    evidence = sorted(hit.evidence)
    shown = "; ".join(evidence[:MAX_EVIDENCE])
    if len(evidence) > MAX_EVIDENCE:
        shown += f"; +{len(evidence) - MAX_EVIDENCE} more"
    return f"  {hit.group:<9} [{', '.join(sorted(hit.reqs))}] <- {shown}"


def render_text(
    report: BackstopReport, unresolved: list[GroupHit] | None = None
) -> str:
    """Compact human-readable report."""
    nsym = sum(len(s) for s in report.symbols.values())
    lines = [
        f"spec-backstop: {len(report.symbols)} changed source files, "
        f"{nsym} changed symbols",
    ]
    if not report.symbols:
        lines.append(
            "no Python source in the diff: this tool derives nothing from"
            " docs, YAML, or config changes, so exit 0 here is not evidence"
            " that the manifest covers the change"
        )
    if report.ignored:
        lines.append(
            "not analysed (outside vultron/ and test/): "
            f"{', '.join(sorted(report.ignored))}"
        )
    if report.hubs:
        hubs = ", ".join(f"{n} ({c})" for n, c in sorted(report.hubs.items()))
        lines.append(
            f"hub symbols (imported by >{report.hub_threshold} test files; "
            f"hits shown as INFO): {hubs}"
        )
    if report.monoliths:
        shown = ", ".join(
            f"{p} ({n} groups)" for p, n in sorted(report.monoliths.items())
        )
        lines.append(
            f"catch-all test files (markers span >{MONOLITH_GROUP_SPAN}"
            f" groups; shown as INFO): {shown}"
        )
    lines.append(f"MUST ({len(report.must)} groups):")
    lines += [_group_line(report.must[g]) for g in sorted(report.must)]
    info = " ".join(
        f"{g}({len(report.info[g].reqs)})" for g in sorted(report.info)
    )
    lines.append(f"INFO ({len(report.info)} groups): {info}".rstrip())
    if unresolved is not None:
        lines.append(f"UNRESOLVED by manifest ({len(unresolved)} groups):")
        lines += [_group_line(hit) for hit in unresolved]
    return "\n".join(lines)


def _hit_dict(hit: GroupHit) -> dict[str, object]:
    return {
        "group": hit.group,
        "topic": hit.topic,
        "requirements": sorted(hit.reqs),
        "evidence": sorted(hit.evidence),
    }


def render_json(
    report: BackstopReport, unresolved: list[GroupHit] | None = None
) -> str:
    """Machine-readable report (``--json``)."""
    data: dict[str, object] = {
        "changed": [
            {"path": p, "symbols": sorted(s)}
            for p, s in sorted(report.symbols.items())
        ],
        "must": [_hit_dict(report.must[g]) for g in sorted(report.must)],
        "info": [_hit_dict(report.info[g]) for g in sorted(report.info)],
        "no_signal": report.no_signal,
        "ignored": sorted(report.ignored),
        "hub_threshold": report.hub_threshold,
        "hubs": dict(sorted(report.hubs.items())),
    }
    if unresolved is not None:
        data["unresolved"] = [_hit_dict(hit) for hit in unresolved]
    return json.dumps(data, indent=2)
