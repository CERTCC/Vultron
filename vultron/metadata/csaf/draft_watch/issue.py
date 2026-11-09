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
"""The body of the issue the draft-watch job opens (CSAF-05-005, CSAF-05-007)."""

from __future__ import annotations

from collections.abc import Sequence

from vultron.metadata.csaf.draft_watch.compare import (
    PROFILES_FILE,
    DraftChange,
)
from vultron.metadata.csaf.pin import CsafPin

#: How many lines of each diff the issue body quotes at most; a long diff says
#: no more than its first lines.
_DIFF_LINES = 200


#: The longest diff line the issue body quotes in full.
_DIFF_LINE_CHARS = 300


#: The most characters the issue body may hold: GitHub refuses a body over
#: 65,536, and the CI failure that would follow repeats every run.
BODY_LIMIT = 60_000


def _diff_block(lines: Sequence[str], limit: int) -> list[str]:
    shown = [
        line
        if len(line) <= _DIFF_LINE_CHARS
        else f"{line[:_DIFF_LINE_CHARS]} ... ({len(line)} characters)"
        for line in lines[:limit]
    ]
    if len(lines) > limit:
        shown.append(f"... {len(lines) - limit} more lines")
    return [
        "<details><summary>Diff</summary>",
        "",
        # Four backticks, so a fence inside the diff does not close it.
        "````diff",
        *shown,
        "````",
        "",
        "</details>",
    ]


def _fields_section(change: DraftChange) -> list[str]:
    lines = ["## CSAF fields this codebase reads", ""]
    if not change.fields:
        return [
            *lines,
            "None of them changed, so regenerating the models is enough.",
        ]
    lines.append(
        "Each of these sets a case input, so review its mapping in the "
        "crosswalk:"
    )
    lines.append("")
    lines.extend(
        f"- `{a.field.path}` ({', '.join(a.field.specs)}) {a.how}."
        for a in change.fields
    )
    return lines


def _compose(
    change: DraftChange, pin: CsafPin, upstream_commit: str | None, limit: int
) -> str:
    head = (
        f"commit `{upstream_commit}` of {pin.repository}"
        if upstream_commit
        else f"the head of {pin.repository}"
    )
    lines = [
        f"{head} changes what Vultron's CSAF models depend on, compared with "
        f"the pinned revision `{pin.short_commit}` (draft {pin.draft_stage}) "
        "in `third_party/csaf/pin.json`.",
        "",
        *_fields_section(change),
    ]
    if change.problems:
        lines += ["", "## Inputs the pin cannot follow", ""]
        lines += [f"- {problem}" for problem in change.problems]
    if change.changed_modules:
        lines += ["", "## Generated models", ""]
        lines += [f"- `{name}` differs" for name in change.changed_modules]
        lines += ["", *_diff_block(change.model_diff, limit)]
    if change.profiles_diff:
        lines += ["", "## Profile text", "", f"`{PROFILES_FILE}` changed.", ""]
        lines += _diff_block(change.profiles_diff, limit)
    if change.tests_added or change.tests_removed:
        lines += ["", "## Mandatory tests", ""]
        lines += [f"- added: {t}" for t in change.tests_added]
        lines += [f"- removed: {t}" for t in change.tests_removed]
    lines += [
        "",
        "## What to do",
        "",
        "1. Bump the pin: copy the schemas the pin lists from the new upstream "
        "commit into `third_party/csaf/schemas/`, and update the commit, "
        "draft stage, `sources` and `sha256` in `third_party/csaf/pin.json`. "
        "A new source needs a licence file beside it and an entry in "
        "`LICENSE.md`.",
        "2. Regenerate the models: `uv run csaf-models`.",
        "3. Re-check the crosswalk in `docs/reference/csaf_crosswalk/` for "
        "each field above, and run `uv run csaf-corpus --clone <clone>` over "
        "a clone at the new commit.",
        "",
        "Close this issue from the pull request that moves the pin. While it "
        "stays open, the `CSAF Draft Watch` workflow opens no other issue and "
        "does not comment here (CSAF-05-006).",
    ]
    return "\n".join(lines) + "\n"


def render_issue(
    change: DraftChange, pin: CsafPin, upstream_commit: str | None = None
) -> str:
    """Return the body of the issue the job opens for *change*.

    The diffs are quoted shorter and shorter until the body fits in
    :data:`BODY_LIMIT`; a body that still does not fit is cut short.
    """
    limit = _DIFF_LINES
    while True:
        body = _compose(change, pin, upstream_commit, limit)
        if len(body) <= BODY_LIMIT or limit == 0:
            break
        limit //= 2
    if len(body) > BODY_LIMIT:
        cut = "\n\n... the rest of this report is cut short.\n"
        body = body[: BODY_LIMIT - len(cut)] + cut
    return body
