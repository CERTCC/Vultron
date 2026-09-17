---
source: CONCERN-3300
timestamp: '2026-09-17T14:45:55.606486+00:00'
title: lint-docs skipped every _*.md fragment, so the Protocol Specification had no
  automated style coverage
type: learning
---

`lint-docs` Phase 1 dropped "anything matching `not_in_nav`'s generated
patterns", which includes `_*.md`. The Vultron Protocol Specification is
assembled entirely from `_*.md` fragments, so none of it was checked by the tool
whose job is checking it: 73 fragments under `docs/`, 35 of them the
specification, totalling 2,773 lines of normative prose.

Surfaced during the PR #3265 review round. An American-spelling regression
("unmodelled") was reintroduced while rewriting §4.6 and survived `markdownlint`,
`mdlint.sh` and a clean strict build; it was caught only because a verification
pass happened to grep for it. Seven further SG-37 violations were still resident
in the fragments when this was planned (`_cs-dimensions.md:101`,
`_semantic-layer.md:37,69,113,180,182,194` — all `acknowledgement`).

**Root cause.** The `_` prefix was doing double duty. In `mkdocs.yml` it means
"exclude from nav"; `lint-docs` read it as "this is not really a page". Those are
different claims, and the second is false for prose-heavy normative reference
material that merely happens to be *delivered* as fragments. The general form of
the defect is that lint scope was derived from a nav-visibility mechanism —
`not_in_nav` also lists `developer/**` and `agents/*.md`, which the style guide's
scope table puts explicitly *in* scope.

**The gate reported success.** `check-docs-sync` calls `lint-docs` a blocking
gate (DF-09-001). When PR #3265 wrote the 35 fragments, the gate resolved to an
empty target set and passed. A gate that checks nothing and reports clean is
worse than no gate, because the false signal suppresses the review it replaced.

**What planning changed about the fix.** The issue proposed three options; all
three were declined, and two rested on premises the measurements contradict.

- *Exempt by content shape* is dead on arrival. Of 73 fragments, about six are
  genuinely content-free. The rest carry prose, **including the ones that look
  content-free**: `_em_blurb.md` is five lines and a pure admonition;
  `_nda_sidebar.md` is a pure admonition carrying ten lines of substantive
  argument. "Skip pure admonitions" would exempt exactly the wrong files. And
  classifying by content shape means reading every file, which is what linting
  is.
- *Lint the assembled page* gets page scope right but loses source line numbers
  across 2,773 lines, and the assembled artifact cannot be edited.
- *Carve out the specification only* does not avoid the hard part: the 35
  fragments still trip every page-scoped rule.

The load-bearing distinction is **rule scope, not file type**. Per-sentence
rules (spelling, filler, sentence shape, list discipline, Mermaid, reference
voice) apply to the fragment with its own line numbers. Page-scoped rules
(SG-07/09 acronym first use, SG-10/11/12 concept order, SG-21/39/41 furniture,
SG-32/33 diagram warrant) apply to the assembling page — which needs no new
machinery, because `index.md` is not `_`-prefixed and is already a lint target.
Reading its include directives in order is not tooling.

`.markdownlint-cli2.yaml` set the precedent: it disables MD041 ("First line in
file should be a top level header") with the comment *"Disabled because we use
`include-markdown` plugin for merging markdown files"*. The repo had already met
this class of fragment-only artifact and named the rule rather than teaching the
tool about assembly.

**Two further conclusions from the interview.**

The auto-fix guard was the wrong shape. It switched to report-only above 20
target files, but file count is a proxy for whether a fix is a deterministic
substitution or a model rewriting prose. SG-08/35/37 are substitutions and are
safe at any scale (`markdownlint --fix` and `black` run tree-wide with no
threshold); SG-02/24 and SG-17–19 are rewrites whose per-edit risk does not
shrink with volume. The count blocked the safe fixes above 20 files and
permitted the risky ones below it.

`codespell` becomes the mechanical floor for SG-37 — the one style rule with
off-the-shelf tooling. Configured in `pyproject.toml`, run as a stock pre-commit
hook over `docs/`: 94 findings across 31 files. Scope cannot be widened —
`behaviour` appears 1,114 times in `vultron/` and `test/` as
`py_trees.behaviour.Behaviour` across 142 files. Three silent hazards were found
by measurement: `codespell` has no notion of a code fence and would rewrite
`docs/howto/wire_capability.md`'s ten py_trees API references into code that
raises `AttributeError`; run against the repo root it rewrites its own
`ignore-regex` in `pyproject.toml`; and `skip` patterns silently fail to match
when `./`-prefixed, inflating the count from 94 to 222 with no error. The
generalizable rule: what makes `--write-changes` safe is not the dictionary but
an audit that no finding sits inside a code fence, an inline code span, an
external citation title, or a link target.

**Resolved**: 2026-09-17 — implementation tracked in #3318.
Docs PR: <https://github.com/CERTCC/Vultron/pull/3316>.
ADR: `docs/adr/0091-lint-fragments-as-source-page-rules-on-rendered-page.md`.
Spec: `specs/diataxis-requirements.yaml` DF-09-003 (amended), DF-09-007,
DF-09-008, DF-09-009.
Notes: `notes/documentation-strategy.md` § "Nav Visibility Is Not a Content
Class: Fragments vs. Assembly Units".

Also found while planning and fixed in the same PR: skill issue-list queries
truncated at `--limit 200` on a 305-open-issue repo, returning 16 of 34 open
epics and hiding the correct parent epic #1190. Same failure shape — a query
resolving a partial set and reporting success (#3319).
