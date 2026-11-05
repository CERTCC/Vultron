"""The ``--source`` vocabulary for ``implementation`` and ``idea`` entries.

These two entry types accept a fixed set of source forms, so that a source
from some other numbering (``ADR-0041``, ``VCR-005``, a ``YYMM`` date) is never
taken for an issue number (HM-08-001, HM-08-003, HM-08-008):

========================  =====================  ==============================
Entry type                Source                 Output
========================  =====================  ==============================
``implementation``        ``ISSUE-N``            comment on issue N
``implementation``        ``ISSUE-N-<slug>``     file (a detailed record kept
                                                 beside the completion comment)
``idea``                  ``ISSUE-N``            comment on issue N
``idea``                  ``IDEA-YYMMDDNN``      file (an idea with no issue)
========================  =====================  ==============================

Any other source for these types is refused. ``learning``, ``note`` and
``priority`` sources are free-form and always go to a file.
"""

from __future__ import annotations

import re

from vultron.metadata.history.types import HistoryEntryType

#: Entry types whose ``--source`` follows the vocabulary above.
COMMENT_TYPES = frozenset(
    {HistoryEntryType.implementation, HistoryEntryType.idea}
)

_ISSUE_RE = re.compile(r"^ISSUE-([1-9][0-9]*)$", re.ASCII)
_ISSUE_SLUG_RE = re.compile(
    r"^ISSUE-[1-9][0-9]*-[a-z0-9]+(?:-[a-z0-9]+)*$", re.ASCII
)
_IDEA_DATE_RE = re.compile(r"^IDEA-[0-9]{8}$", re.ASCII)
#: A number in some other form, to suggest the ``ISSUE-N`` spelling of it.
_OTHER_NUMBER_RE = re.compile(r"^(?:[A-Za-z]+-)?0*([1-9][0-9]*)$", re.ASCII)

_FILE_FORMS: dict[HistoryEntryType, tuple[re.Pattern[str], str]] = {
    HistoryEntryType.implementation: (_ISSUE_SLUG_RE, "ISSUE-N-<slug>"),
    HistoryEntryType.idea: (_IDEA_DATE_RE, "IDEA-YYMMDDNN"),
}


class SourceRefusedError(ValueError):
    """A ``--source`` the entry type does not accept; the message says why."""


def accepted_forms(entry_type: HistoryEntryType) -> str:
    """The accepted source forms of *entry_type*, for an error message."""
    _, file_form = _FILE_FORMS[entry_type]
    return f"ISSUE-N (a comment on issue N) or {file_form} (a file)"


def classify_source(entry_type: HistoryEntryType, source: str) -> int | None:
    """Return the issue N to comment on, or None when *source* takes a file.

    Only the form is checked; whether issue N exists is for the GitHub lookup
    (``github._confirm_issue``). A type outside :data:`COMMENT_TYPES` always
    takes a file.

    Raises:
        SourceRefusedError: *source* is not one of *entry_type*'s forms
            (HM-08-008). The message names the accepted forms and, for a
            number in another form such as ``TASK-4646``, its ``ISSUE-N``
            spelling.
    """
    if entry_type not in COMMENT_TYPES:
        return None
    if (m := _ISSUE_RE.match(source)) is not None:
        return int(m.group(1))
    file_re, _ = _FILE_FORMS[entry_type]
    if file_re.match(source):
        return None
    message = (
        f"append-history {entry_type.value} does not accept --source "
        f"{source!r}: use {accepted_forms(entry_type)}"
    )
    if (m := _OTHER_NUMBER_RE.match(source)) is not None:
        message += f"; if it names issue {m.group(1)}, use ISSUE-{m.group(1)}"
    raise SourceRefusedError(message)
