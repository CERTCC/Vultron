---
source: CONCERN-3574
timestamp: '2026-09-24T16:57:37.017897+00:00'
title: Withholding a docs page has two axes; only publication was checked
type: learning
---

## Original concern

A build-time-rendered link to a withheld page is well-formed and 404s, so the
`.md`-suffix assertion planned in #3051 cannot see it.

PR #3573 shipped `href="../../ns/"` on the What's New page after #3549 moved
`docs/ns/` into `draft_docs`. `mkdocs build --strict`, markdownlint, both test
suites, and `docs-withheld` all passed. Only `linkchecker` over the built
`site/` in CI caught it — and only because that PR happened to touch `docs/`,
which is what makes the step eligible.

The generalizable class: any artifact enumerating docs pages can advertise one
that `draft_docs` or `exclude_docs` withholds, and the two declarations live in
different files.

## What the planning established

**Withholding has two axes, and only one had a gate.**

- *Publication axis* — did a withheld artifact produce `site/` files?
  Checked by `docs-withheld` (DOCBW-03-005/006).
- *Reference axis* — does anything still *link to* a path the build did not
  produce? Unchecked. This is the axis #3574 fell through.

**`--strict` is structurally blind to it.** MkDocs rewrites relative `.md`
links with a treeprocessor registered on its own `Markdown` instance.
`markdown-exec` converts a block's output on a **child** instance built from the
parent's extensions, which does not carry that treeprocessor. So a link printed
from an exec block is never rewritten *and never validated*. `--strict` passing
is a claim about the pages MkDocs parsed, not the bytes it emitted.

**Three properties of the gate are load-bearing, and each was derived rather
than assumed:**

1. *Resolution, not link form.* `../../ns/` is exactly what a correctly
   rewritten link to a published page looks like. No form signature separates it
   from a live one, so #3051 AC-6's `.md`-suffix assertion could not have caught
   this incident. Checking resolution subsumes the `.md` case.
2. *Every built HTML file, not a crawl.* Measured on this tree: 87 of 534 built
   pages have no inbound link from `site/index.html` — every `not_in_nav` page,
   the `includes/` fragments, `404.html`. `linkchecker site/index.html` never
   inspects their links and reports success over only what it reached. Widening
   *when* linkchecker runs (#3051 AC-5) cannot widen *what* it covers.
3. *Unconditional.* The withholding declaration (`mkdocs.yml`) and the page that
   advertises the path (a generator under `vultron/metadata/`) are different
   files, so a `docs/`-scoped trigger filter can miss the breaking change
   entirely. That is how #3574 shipped.

**Cost was measured, not asserted**, against the user's constraint of no
massive CI or local slowdown: 65,828 internal references across the built tree
scan in ~2.5 s tuned — a bytes-mode regex plus a one-shot path index replacing
65,828 per-reference `stat` calls; the naive form took 5.2 s — against a full
`mkdocs build` of ~132 s. Roughly 2% overhead, and zero cost to the unit suite,
because the check is a CLI invoked after the build rather than a pytest over
`site/`. Baseline is clean, so no allowlist and no ARCH-18 ratchet.

**No ADR.** The change adds a gate enforcing positions the project already holds
(DF-09-009, DOCBW-03-005/006) and overturns no decision.

**Also fixed as a side effect**: DOCBW-03-003's MUST-skip clause read as the
project's whole position on link checking. It did not forbid a new unconditional
step, but a reader would infer one was forbidden. It is now scoped to the
external-URL step, where the network-per-link cost that motivates it actually
applies.

**Resolved**: 2026-09-24 — implementation tracked in #3634.
Docs PR: <https://github.com/CERTCC/Vultron/pull/3633>.
Spec: `specs/docs-build-workflow.yaml` (DOCBW-03-007 added, DOCBW-03-003 amended).
Notes: `notes/documentation-strategy.md` § "Withholding Has Two Axes, and Only One Was Checked".
Also updated #3051: AC-6 superseded by #3634, AC-5 narrowed to external-URL checking.
