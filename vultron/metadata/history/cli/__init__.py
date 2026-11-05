"""CLI entry point for the ``append-history`` tool.

Usage::

    uv run append-history <type> --title "..." --source "..."
    uv run append-history <type> --title "..." --source "..." --file /path/to/body.md
    uv run append-history --from-file plan/incoming/learnings/20260622-SLUG.md

``<type>`` must be one of the ``HistoryEntryType`` values
(``idea``, ``implementation``, ``learning``, ``priority``).

Normal mode (``<type>`` required):

1. Parses ``<type>`` against ``HistoryEntryType``; exits 1 on unknown type.
2. Reads body text from stdin or ``--file <path>``.
3. Constructs a YAML frontmatter block from ``--title``, ``--source``, the
   entry type, and an auto-generated UTC timestamp (HM-07-001).
4. Validates the constructed frontmatter via ``HistoryEntryFrontmatter``
   (includes future-date and tz-aware checks, HM-06-004, HM-06-005).
5. Creates ``plan/history/YYMM/<type>/`` if missing.
6. Writes content (frontmatter + body) to
   ``plan/history/YYMM/<type>/<entry-id>.md``.
7. Regenerates ``plan/history/YYMM/README.md``.
8. Prints the written file path to stdout.

``--from-file`` mode (for ``plan/incoming/learnings/`` processing):

1. Reads the source file as complete content (frontmatter + body).
2. Parses and validates the frontmatter to obtain type, title, source,
   and timestamp (HM-02-001).
3. Moves the entry to ``plan/history/YYMM/<type>/`` using the frontmatter
   timestamp to determine the ``YYMM`` directory.
4. Deletes the source file from ``plan/incoming/``.
5. Prints the written file path to stdout.

An ``implementation`` or ``idea`` entry takes a fixed ``--source``
vocabulary (``source``): ``ISSUE-N`` is posted as a comment on CERTCC/Vultron
issue N, which must exist and not be a pull request, and the comment URL is
printed (HM-08-001, HM-08-002, HM-08-009); ``ISSUE-N-<slug>``
(implementation) and ``IDEA-YYMMDDNN`` (idea) write a file (HM-08-003); any
other source is refused (HM-08-008).

``--from-file`` is mutually exclusive with ``<type>``, ``--title``,
``--source``, ``--file``, and ``--timestamp``.

See ``specs/history-management.yaml`` HM-03, HM-06, HM-07.
See ``specs/build-workflow.yaml`` BW-01 for the incoming-learnings queue.

Submodules, by concern: ``entry`` (building, validating and writing an
entry file), ``source`` (the implementation and idea source vocabulary),
``github`` (the optional GitHub issue comment) and ``commands``
(the argument parser and the two input modes).
"""

from vultron.metadata.history.cli.commands import main
from vultron.metadata.history.cli.entry import append_history_entry

__all__ = [
    "append_history_entry",
    "main",
]
