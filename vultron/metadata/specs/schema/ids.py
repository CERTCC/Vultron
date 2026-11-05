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

#: A slash list of IDs in one group: ``CLP-14-006/007/008``.
_SPEC_ID_SLASH_RE = re.compile(
    rf"\b({_PREFIX}-{_GROUP}-){_INDEX}{_SUFFIX}"
    rf"((?:/{_INDEX}{_SUFFIX})+)\b"
)


def _id_key(spec_id: str) -> tuple[str, int, int] | None:
    """Order *spec_id* by prefix, group and index, ignoring a sub-item letter."""
    match = _ID_PARTS_RE.fullmatch(spec_id)
    if match is None:
        return None
    return match["prefix"], int(match["group"]), int(match["index"])


def written_spec_ids(text: str) -> set[str]:
    """Every requirement ID *text* writes out, sub-item letter kept.

    A slash list ``PREFIX-NN-AAA/BBB`` writes ``PREFIX-NN-BBB`` beside
    ``PREFIX-NN-AAA``. A range writes only its ends: unlike
    :func:`cited_spec_ids`, ``CM-10-001 through CM-10-005`` yields no ID
    between them. These are the IDs a statement cites for SR-13-022, each one
    a reader can see and an author can link or list in ``see_also``.
    """
    found = set(_CITED_ID_RE.findall(text))
    for match in _SPEC_ID_SLASH_RE.finditer(text):
        stem, tail = match.groups()
        found.update(stem + index for index in tail.split("/")[1:])
    return found


def cited_spec_ids(text: str, known_ids: Iterable[str]) -> set[str]:
    """Every requirement ID *text* names, with ranges and slash lists expanded.

    A literal ID, with or without a sub-item letter (``IO-03-003b``), is
    returned whether or not it is known. A range yields every ID in
    *known_ids* with the start's prefix whose group and index lie between its
    ends, inclusive, sub-item IDs included, so it may cross groups but never
    invents an ID; a range whose ends name different prefixes yields only
    those ends. A slash list ``PREFIX-NN-AAA/BBB`` yields ``PREFIX-NN-BBB``
    beside its literal first ID.

    Args:
        text: Prose to scan, such as a decision record's body.
        known_ids: The requirement IDs a range may expand to.

    Returns:
        The IDs *text* names, as a set.
    """
    found = written_spec_ids(text)
    keyed = [(key, i) for i in known_ids if (key := _id_key(i)) is not None]
    for match in _SPEC_ID_RANGE_RE.finditer(text):
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
