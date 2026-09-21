---
title: "A verification clause that names `mkdocs build --strict` does not verify anything about a rendered link — strict cannot see links a build-time block printed"
type: learning
timestamp: "2026-09-21T17:00:00Z"
source: ISSUE-3450
signal: spec-gap
---

DEMOCI-11-009 requires `docs/topics/scenarios/index.md` to render its scenario
table at build time and commit no copy of it. Its verification clause reads:

> `mkdocs build --strict` renders the table, and a test asserts the committed
> page contains no scenario table.

Both halves passed on the first implementation, and the page was broken. The
rendered table's nine links were `href="fv.md"`, `href="fvv.md"` and so on —
`.md` source paths that 404 on the published site, where the pages are served as
`fv/`, `fvv/`. The build exited 0.

**Why strict is blind here.** MkDocs rewrites relative `.md` links to page URLs
with a treeprocessor registered on its *own* `Markdown` instance.
`markdown-exec` converts a block's output on a **child** instance built from the
parent's extension list, which does not carry that treeprocessor. So a link
printed from an exec block is never seen by the code that would rewrite it, and
never seen by the code that would validate it either. It is not that strict
checked the link and passed it; strict never knew there was a link.

This is the gap worth naming: **"the strict build passes" is a claim about the
pages MkDocs parsed, not about the bytes it emitted.** For any page whose
content is produced at build time, the two are different claims, and the spec
clause asserts the weaker one while reading like the stronger one.

**How to apply.** When writing or reviewing a verification clause for a
build-time-rendered page, do not let `mkdocs build --strict` stand as the
verification of anything about the *output*. It verifies that the block ran. Add
an assertion over the artifact:

- for links, check the built `site/` tree — `linkchecker` already errors and
  exits 1 on a missing relative `.md` target, verified against a fixture; or
  assert directly that no internal `href` in `site/` ends in `.md`, which is the
  signature of exactly this defect;
- more generally, assert on the rendered string in a unit test, which is cheap
  and needs no build. ISSUE-3450 pinned the link form that way
  (`test_narrative_links_are_built_site_urls`) plus a second test pinning the
  `use_directory_urls` setting the form depends on, since flipping that setting
  would break every link without failing any build.

The same reasoning applies to the ~183 other `exec="true"` and `:::`
mkdocstrings blocks in `docs/`: any of them that emits a link is in this
position, and no current gate would report it.

The CI-wiring half of this — that the `linkchecker` step exists in
`docs-build-check.yml` but is disabled by both the workflow `paths:` filter and
an in-job `docs_changed` grep for `^docs/` — is tracked on ISSUE-3051 (AC-5,
AC-6) and is not what this entry is about. This entry is about the spec clause:
DEMOCI-11-009's verification text should not imply strict covers the output, and
neither should the next clause written in its shape.

Corroboration needed: one instance. A second witness would be any requirement
whose verification names a build, a lint, or a type-check as evidence for a
property that tool does not actually inspect. Suspected siblings worth checking
when one turns up: clauses that cite `mypy` as verification for a runtime
invariant, or `--strict` for anything about emitted HTML.

Related: [[20260918-3399-bt18-has-no-contract-for-a-refusal-carrying-a-payload]]
is the nearer queued entry in kind — a spec clause that cannot be satisfied as
written. This one is the inverse: a clause that *is* satisfied as written and
still permits the defect it exists to prevent.
