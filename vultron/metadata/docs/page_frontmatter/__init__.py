"""Validate the declarations ``docs/`` pages make in their frontmatter.

The keys are ``stakeholder_type``, ``level``, ``page_type`` and ``subject``.

Requirements: specs/diataxis-requirements.yaml DF-11-001, DF-11-003,
DF-11-010, DF-11-012, DF-11-013, DF-11-018, DF-11-025, DF-11-026,
DF-09-009; attribution per MS-17 via :mod:`vultron.metadata.file_loading`.
Schema: :mod:`vultron.metadata.docs.page_schema`.

Every ``docs/**/*.md`` file is one of three things:

* an **include fragment** — a file some page pulls in whole with
  ``{% include-markdown %}`` and that is not itself in the nav, or a
  ``pymdownx.snippets`` ``auto_append`` file. It has no reader of its own, so it
  is excluded from the target set and reported if it declares any of the
  four keys (DF-11-010, DF-11-036, DF-11-026); its hosts' declarations govern
  it.
* a **working-record page** — matched by
  :data:`~vultron.metadata.docs.page_schema.WORKING_RECORD_PATTERNS`. It
  declares ``[project-contributor]``, no ``level`` (DF-11-033), no
  ``page_type`` (DF-11-036) and no ``subject`` (DF-11-026), and it is
  absent from the ``mkdocs.yml`` nav and matched by ``not_in_nav``
  (DF-11-003).
* a **reader-facing page** — everything else. It declares all four keys
  (DF-11-001, DF-11-018, DF-11-025).

A start page (``docs/start/*.md`` other than its ``index.md``) also declares
its reading-path ``thread:``, and no other page may (DF-11-013).

A file matched by ``exclude_docs`` that no page includes is none of the three:
MkDocs never builds it, so it has no reader until a page pulls it in. The
generated occasion fragments wait there for their hosts (ADR-0128).

A page included only from a ``start=`` marker (a user story on its
traceability page, a worked example quoted by the specification's annexes) is
still a page: it has a URL and readers of its own. A page included *whole* has
its frontmatter copied into its host, which would render its declarations
there (DF-11-004), so such a page that declares any of the keys is reported
too.

Every page declares: an undeclared page is a failure. The shrink-only
baseline that let this check land before the content audit (#3526) reached
zero and was retired.

Usage::

    uv run docs-frontmatter   # check (pre-commit, CI)

Submodules, by concern: ``tree`` (classifying the docs tree and reading
include directives) and ``check`` (the frontmatter checks and the CLI).
"""

from vultron.metadata.docs.page_frontmatter.check import (
    check_docs_frontmatter,
    frontmatter_key_lines,
    main,
    validate_thread,
)
from vultron.metadata.docs.page_frontmatter.tree import (
    DocsTree,
    classify_docs_tree,
    include_directives,
)

__all__ = [
    "DocsTree",
    "check_docs_frontmatter",
    "classify_docs_tree",
    "frontmatter_key_lines",
    "include_directives",
    "main",
    "validate_thread",
]
