"""The drafts register every throwaway ``docs-site`` checkout needs.

``uv run docs-site`` generates the Protocol Specification's status box and
the Revision Log status tables from the drafts register (DOCBW-08-004), so it
refuses a tree with no register, and it checks that the Revision Log includes
each draft's table (DOCBW-08-008). A test tree built for another artifact adds
:data:`DRAFTS_FILES` through :func:`with_drafts`.

One unreleased draft is enough. A test about the register itself writes its
own (``test/ci/test_drafts_register.py``).
"""

from __future__ import annotations

from vultron.metadata.docs.drafts_register import (
    REGISTER_PATH,
    REVISION_LOG_PATH,
    include_line,
)

#: ``docs/``-relative files: a register with one open draft, and a Revision
#: Log that includes its status table. The Revision Log is an include host
#: only here: it is in no nav and declares nothing.
DRAFTS_FILES: dict[str, str] = {
    REGISTER_PATH.removeprefix("docs/"): (
        "drafts:\n"
        "  - version: draft-1\n"
        "    status: unreleased\n"
        "    date: 2026-11-06\n"
    ),
    REVISION_LOG_PATH.removeprefix("docs/"): (
        f"# Revision Log\n\n## Draft 1\n\n{include_line('draft-1')}\n"
    ),
}


def with_drafts(files: dict[str, str]) -> dict[str, str]:
    """*files* with the seed register and Revision Log added; *files* wins a clash."""
    return {**DRAFTS_FILES, **files}
