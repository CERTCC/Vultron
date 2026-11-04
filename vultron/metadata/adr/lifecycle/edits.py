"""Judge one ADR edit: protected sections, amendments and status moves."""

from __future__ import annotations

import datetime as _dt
import re

import frontmatter
from pydantic import ValidationError

from vultron.metadata.adr.lifecycle.epochs import (
    _EPOCH_OF_STATUS,
    EPOCH_STATUS,
    AdrEpoch,
    _effective_epoch,
    epoch_for,
    status_epoch_fault,
)
from vultron.metadata.adr.schema import AdrFrontmatter
from vultron.metadata.file_loading import (
    loads_frontmatter,
)

#: Decision sections an epoch-3 ADR may change only through an Amendment.
_PROTECTED_SECTIONS = ("Decision Outcome", "Considered Options")


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")


_AMENDMENT_TITLE_RE = re.compile(
    r"(?=.*\bAmendment\b)(?=.*\d{4}-\d{2}-\d{2})", re.IGNORECASE
)


_FENCE_RE = re.compile(r"^(```|~~~)")


def _parse_sections(body: str) -> list[tuple[int, str, str]]:
    """Return ``(level, title, own text)`` for each heading, in order.

    Headings inside fenced code blocks are ignored. A section's own text ends
    at the next heading of any level.
    """
    sections: list[tuple[int, str, list[str]]] = []
    in_fence = False
    for line in body.splitlines():
        if _FENCE_RE.match(line):
            in_fence = not in_fence
        match = None if in_fence else _HEADING_RE.match(line)
        if match:
            sections.append((len(match.group(1)), match.group(2) or "", []))
        elif sections:
            sections[-1][2].append(line)
    return [(lvl, title, "\n".join(lines)) for lvl, title, lines in sections]


def _is_amendment_title(title: str) -> bool:
    return bool(_AMENDMENT_TITLE_RE.search(title))


def _protected_text(body: str) -> dict[str, str]:
    """Map each protected section name to its full text.

    A heading belongs to a protected section when its title starts with the
    section name, ignoring case ("Considered Options (request side)" counts).
    The text runs through nested subsections, except dated Amendment blocks,
    which are how the section is allowed to change.
    """
    out: dict[str, list[str]] = {}
    sections = _parse_sections(body)
    for idx, (level, title, text) in enumerate(sections):
        name = next(
            (
                n
                for n in _PROTECTED_SECTIONS
                if title.lower().startswith(n.lower())
            ),
            None,
        )
        if name is None:
            continue
        parts = out.setdefault(name, [])
        parts.append(f"{title}\n{text}")
        skip_below: int | None = None
        for sub_level, sub_title, sub_text in sections[idx + 1 :]:
            if sub_level <= level:
                break
            if skip_below is not None and sub_level > skip_below:
                continue
            skip_below = None
            if _is_amendment_title(sub_title):
                skip_below = sub_level
                continue
            parts.append(f"{sub_title}\n{sub_text}")
    return {k: "\n".join(v).strip() for k, v in out.items()}


def _amendment_count(body: str) -> int:
    """Count dated Amendment headings outside fenced code blocks."""
    return sum(
        1
        for _, title, _ in _parse_sections(body)
        if _is_amendment_title(title)
    )


def _parse_adr(text: str) -> tuple[frontmatter.Post, AdrFrontmatter | None]:
    """Return an ADR text's post and its frontmatter, or None for the latter
    when it fails its schema, which is left to the loader to report."""
    post = loads_frontmatter(text)
    try:
        return post, AdrFrontmatter.model_validate(post.metadata)
    except ValidationError:
        return post, None


def _override_is_new(
    old_fm: AdrFrontmatter | None, new_fm: AdrFrontmatter
) -> bool:
    """Say whether the change adds or changes ``status_override:``.

    An override already on the base was written for some earlier reason, so
    it does not cover a new status decision (MS-14-012).
    """
    old = old_fm.status_override if old_fm else None
    return bool(new_fm.status_override) and new_fm.status_override != old


def _status_move_faults(
    name: str,
    old_fm: AdrFrontmatter,
    new_fm: AdrFrontmatter,
    today: _dt.date,
    *,
    tested: bool,
) -> list[str]:
    """Refuse a status change that is not forward to its epoch (MS-14-012).

    A move back is always refused: a status only moves forward. A promotion
    ahead of the epoch, including one out of a retired or rejected status,
    needs a ``status_override:`` that this edit adds or changes: an override
    already on the base was written for some earlier reason.
    """
    old_epoch = _EPOCH_OF_STATUS.get(old_fm.status)
    new_epoch = _EPOCH_OF_STATUS.get(new_fm.status)
    if new_epoch is None or old_fm.status is new_fm.status:
        return []
    if old_epoch is not None and new_epoch < old_epoch:
        return [
            f"{name}: status moved back from '{old_fm.status.value}' to "
            f"'{new_fm.status.value}'; a status only moves forward, so keep "
            f"it, or supersede the ADR (MS-14-012)"
        ]
    if old_epoch is new_epoch or _override_is_new(old_fm, new_fm):
        return []
    remedy = (
        "add or change 'status_override:' with a human's reason; an "
        "override already on the base does not count (MS-14-012)"
    )
    epoch = epoch_for(new_fm.updated, today, tested=tested)
    if new_epoch > epoch:
        return [
            f"{name}: status moved to '{new_fm.status.value}', ahead of "
            f"epoch {int(epoch)} ('{EPOCH_STATUS[epoch].value}') on {today}; "
            f"{remedy}"
        ]
    return []


def edit_faults(
    name: str,
    old_text: str | None,
    new_text: str,
    today: _dt.date,
    *,
    tested_on_base: bool = False,
    tested_on_head: bool = False,
) -> list[str]:
    """Return the lifecycle faults in an edit of one ADR (MS-14-007).

    ``old_text`` is ``None`` for a new ADR. ``tested_on_base`` and
    ``tested_on_head`` say whether the ADR has a test-verified dependent
    before and after the change.

    - A material edit (``updated`` moved, or a new ADR) must leave ``status``
      on the epoch for that date, counting the dependents after the change,
      unless a ``status_override`` says why. An edit that leaves ``updated``
      alone is not held to this: drift on an untouched ADR is the scheduled
      report's.
    - A status change must move forward (MS-14-012). It must not move ahead
      of the epoch unless the edit adds or changes a ``status_override``.
    - Bumping ``updated`` on an ADR that was past epoch 1 needs a
      ``status_override`` (MS-14-024).
    - Changing Decision Outcome or Considered Options of an epoch-3 ADR needs a
      new dated Amendment block (MS-14-009).

    The epoch an ADR "was" in is the later of its computed epoch and the one
    its status names, since a status ahead of the clock stands.
    """
    new, new_fm = _parse_adr(new_text)
    if new_fm is None:
        return []
    if old_text is None:
        fault = status_epoch_fault(name, new_fm, today, tested=tested_on_head)
        return [fault] if fault else []
    old, old_fm = _parse_adr(old_text)
    if old_fm is None:
        return []

    faults: list[str] = []
    if new_fm.updated != old_fm.updated:
        epoch_fault = status_epoch_fault(
            name, new_fm, today, tested=tested_on_head
        )
        if epoch_fault:
            faults.append(epoch_fault)
    faults.extend(
        _status_move_faults(name, old_fm, new_fm, today, tested=tested_on_head)
    )
    old_epoch = _effective_epoch(old_fm, today, tested=tested_on_base)

    if (
        new_fm.updated > old_fm.updated
        and old_epoch > AdrEpoch.PROPOSED
        and not new_fm.status_override
    ):
        faults.append(
            f"{name}: 'updated' moved {old_fm.updated} -> {new_fm.updated} "
            f"on an ADR in epoch {int(old_epoch)}; supersede it or amend it, "
            f"or record a human's reason in 'status_override:' (MS-14-024)"
        )

    if old_fm.status in _EPOCH_OF_STATUS and old_epoch is AdrEpoch.SETTLED:
        old_sections = _protected_text(old.content)
        new_sections = _protected_text(new.content)
        changed = [
            title
            for title in _PROTECTED_SECTIONS
            if old_sections.get(title) != new_sections.get(title)
        ]
        if changed and _amendment_count(new.content) <= _amendment_count(
            old.content
        ):
            faults.append(
                f"{name}: {' and '.join(changed)} changed on an epoch-3 ADR "
                f"without a new dated Amendment block (a heading naming "
                f"'Amendment' and a YYYY-MM-DD date); amend it or supersede "
                f"it with a new ADR (MS-14-009)"
            )
    return faults
