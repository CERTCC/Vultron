"""Identifier shapes for the spec schema: requirement, ADR, story and issue
IDs.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Annotated

from pydantic import StringConstraints

#: The parts of the ID grammar (MS-04-001), shared by every ID pattern below.
#: ``_SUFFIX`` is the optional sub-item letter of an ID such as ``IO-03-003b``.
_PREFIX = r"[A-Z]{2,8}"


_GROUP = r"\d{2}"


_INDEX = r"\d{3}"


_SUFFIX = r"[a-z]?"

#: The ID grammar as pattern text, for a caller that composes it into a larger
#: expression: a requirement ID with its optional sub-item letter, and a
#: group ID (``PREFIX-NN``).
SPEC_ID_PATTERN = rf"{_PREFIX}-{_GROUP}-{_INDEX}{_SUFFIX}"


SPEC_GROUP_PATTERN = rf"{_PREFIX}-{_GROUP}"

#: A fully-qualified requirement ID as it appears in prose — ``PREFIX-NN-NNN``
#: (MS-04-001): 2–8 uppercase letters, two-digit group, three-digit index.
#: ``\b`` on both sides keeps ``ADR-0001``, semantic versions, and a prefix
#: that merely ends in another topic's letters from matching. Shared by the
#: spec linter, bundle-fit, and the citation ratchets so the ID grammar is
#: defined once.
SPEC_ID_CITATION_RE = re.compile(rf"\b{_PREFIX}-{_GROUP}-{_INDEX}\b")

#: A literal ID as :func:`cited_spec_ids` reads it: the citation grammar plus
#: an optional sub-item letter.
_CITED_ID_RE = re.compile(rf"\b{_PREFIX}-{_GROUP}-{_INDEX}{_SUFFIX}\b")

#: A whole requirement ID split into the parts a range compares.
_ID_PARTS_RE = re.compile(
    rf"(?P<prefix>{_PREFIX})-(?P<group>{_GROUP})-(?P<index>{_INDEX}){_SUFFIX}"
)

#: A range of requirement IDs: a full start ID, then either a range word and a
#: full end ID (``CM-10-001 through CM-10-005``) or a dash or ``..`` and an end
#: that is a full ID, ``NN-NNN`` or ``NNN`` (``CM-10-001–005``,
#: ``CSB-18-002..004``). A word before a bare number is prose, not a range:
#: ``CM-10-001 to 100 actors`` must not expand a whole group. A plain hyphen is
#: not a range mark either: ``CM-10-001-005`` is too close to an ID typo.
_SPEC_ID_RANGE_RE = re.compile(
    rf"\b(?P<prefix>{_PREFIX})-(?P<group>{_GROUP})-(?P<index>{_INDEX}){_SUFFIX}"
    r"\s*(?:\b(?:through|thru|to)\s+"
    rf"(?P<word_prefix>{_PREFIX})-(?P<word_group>{_GROUP})-"
    rf"(?P<word_index>{_INDEX})"
    r"|(?:–|—|\.\.)\s*"
    rf"(?:(?:(?P<dash_prefix>{_PREFIX})-)?(?P<dash_group>{_GROUP})-)?"
    rf"(?P<dash_index>{_INDEX})"
    rf"){_SUFFIX}\b"
)


def _id_key(spec_id: str) -> tuple[str, int, int] | None:
    """Order *spec_id* by prefix, group and index, ignoring a sub-item letter."""
    match = _ID_PARTS_RE.fullmatch(spec_id)
    if match is None:
        return None
    return match["prefix"], int(match["group"]), int(match["index"])


#: A requirement ID as :func:`written_spec_ids` reads it, its parts named.
_WRITTEN_ID_RE = re.compile(
    rf"\b(?P<prefix>{_PREFIX})-(?P<group>{_GROUP})-(?P<index>{_INDEX})"
    rf"(?P<suffix>{_SUFFIX})\b"
)

#: An ID end written after another ID: a slash-list member (``/003``) or a
#: range end (``–003``, ``..11-002``), each with its own sub-item letter. A
#: bare-number end must follow its mark with no space: ``CM-10-001 — 100
#: actors`` is prose and writes no second ID. A group-qualified end may be set
#: off by spaces (``CM-10-001 — 11-002``), as :data:`_SPEC_ID_RANGE_RE` reads.
_WRITTEN_TAIL_RE = re.compile(
    r"(?:(?P<mark>/|–|—|\.\.)|\s*(?:–|—|\.\.)\s*(?=\d{2}-\d{3}))"
    rf"(?:(?P<group>{_GROUP})-)?(?P<index>{_INDEX})(?P<suffix>{_SUFFIX})\b"
)


def written_spec_ids(text: str) -> set[str]:
    """Every requirement ID *text* writes out, sub-item letter kept.

    Each full ID is read, then each end written straight after it in turn, so
    chains and mixed forms (``CM-10-001/002–004``, ``CM-10-001–003/005``) are
    read whole. A slash list ``PREFIX-NN-AAA/BBB`` writes ``PREFIX-NN-BBB``
    beside ``PREFIX-NN-AAA``. A range writes only its ends, a short end such as
    the ``003`` of ``CM-10-001–003`` or the ``003b`` of ``IO-03-003a–003b``
    included; a backward one (``CM-10-005–002``) is no range, so its short end
    is not an ID. Unlike :func:`cited_spec_ids`, ``CM-10-001 through
    CM-10-005`` yields no ID between them. A letter written straight after an
    ID reads as its sub-item letter, so a plural such as ``CM-10-001s`` writes
    ``CM-10-001s``, which spec-lint reports as naming no requirement. These
    are the IDs a statement cites for SR-13-022, each one a reader can see and
    an author can link or list in ``see_also``.
    """
    found: set[str] = set()
    for match in _WRITTEN_ID_RE.finditer(text):
        found.add(match[0])
        prefix, group = match["prefix"], match["group"]
        last = (int(group), int(match["index"]), match["suffix"])
        pos = match.end()
        while (tail := _WRITTEN_TAIL_RE.match(text, pos)) is not None:
            group = tail["group"] or group
            end = (int(group), int(tail["index"]), tail["suffix"])
            if tail["mark"] == "/" or end > last:
                found.add(f"{prefix}-{group}-{tail['index']}{tail['suffix']}")
            last, pos = end, tail.end()
    return found


def _is_spaced_short_end(match: re.Match[str]) -> bool:
    """Whether a range *match* ends in a bare number set off by a space."""
    return (
        match["dash_index"] is not None
        and match["dash_group"] is None
        and re.search(r"\s", match[0]) is not None
    )


def cited_spec_ids(text: str, known_ids: Iterable[str]) -> set[str]:
    """Every requirement ID *text* names, with ranges and slash lists expanded.

    Every ID :func:`written_spec_ids` reads is returned whether or not it is
    known: a literal ID, with or without a sub-item letter (``IO-03-003b``),
    a slash-list member, and a range's written ends, a short end such as the
    ``009`` of ``CM-10-001–009`` included. A range adds every ID in
    *known_ids* with the start's prefix whose group and index lie between its
    ends, inclusive, sub-item IDs included, so its interior may cross groups
    but never invents an ID; a range whose ends name different prefixes adds
    nothing beyond those ends. A space between a dash and a bare-number end
    makes it prose, not a range (``CM-10-001 — 100 actors``); a
    group-qualified end (``CM-10-001 — 11-002``) is still a range.

    Args:
        text: Prose to scan, such as a decision record's body.
        known_ids: The requirement IDs a range may expand to.

    Returns:
        The IDs *text* names, as a set.
    """
    found = written_spec_ids(text)
    keyed = [(key, i) for i in known_ids if (key := _id_key(i)) is not None]
    for match in _SPEC_ID_RANGE_RE.finditer(text):
        if _is_spaced_short_end(match):
            continue
        prefix = match["prefix"]
        end_prefix = match["word_prefix"] or match["dash_prefix"] or prefix
        if end_prefix != prefix:
            continue
        end_group = (
            match["word_group"] or match["dash_group"] or match["group"]
        )
        end_index = match["word_index"] or match["dash_index"]
        low = (prefix, int(match["group"]), int(match["index"]))
        high = (prefix, int(end_group), int(end_index))
        found.update(i for key, i in keyed if low <= key <= high)
    return found


SpecIdStr = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Z]{2,8}(-\d{2}(-\d{3}[a-z]?)?)?$"),
]

# Structured ADR reference (SR-02, MS-11-004): ``ADR-NNNN`` form. Kept separate
# from SpecIdStr — ADR IDs are four-digit and would not match the spec ID
# pattern — so an amended ADR can be traced to its dependent specs via the edges
# graph rather than only free-text rationale prose.
AdrIdStr = Annotated[
    str,
    StringConstraints(pattern=r"^ADR-\d{4}$"),
]

#: The shape of a user-story ID (SR-11-002). A named constant because the
#: story-page catalog scanner decides from a filename which pages are stories
#: (``docs/story_pages.py``), and a second copy of the pattern would let the
#: two disagree: a widened pattern the scanner did not learn would make every
#: citation of a new page a hard TRACE-03-001 error and drop the page from
#: both generated artifacts.
STORY_ID_PATTERN = r"^story_\d{4}_\d{3}$"


StoryIdStr = Annotated[
    str,
    StringConstraints(pattern=STORY_ID_PATTERN),
]

#: The issue that owns verifying an unverified MUST-tier requirement
#: (MS-10-006): one GitHub reference in ``#N`` form. Quote it in YAML —
#: ``verification_debt: #12`` is a comment and loads as null.
IssueRefStr = Annotated[
    str,
    StringConstraints(pattern=r"^#[1-9]\d*$"),
]
