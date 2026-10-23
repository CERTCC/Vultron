---
source: CONCERN-3919
timestamp: '2026-09-30T15:24:25.429859+00:00'
title: Docs currency is checked late and only by build and bugfix
type: learning
---

## Summary

Only `build` and `bugfix` check that `docs/` pages still match a code, spec, or notes change, and both run the check **after** the PR is pushed, as an unrecorded, non-blocking step. `plan-issue`, `pr-triage`, `pr-execute`, `pr-verify`, `pr-ship` and `create-pr` never ask which `docs/` pages a change affects. Every other docs check in the chain fires only when `docs/` was already modified, so it can never catch a page the agent forgot.

## Surface Symptom vs. Underlying Problem

**Surface reading:** few PRs seem to include docs updates, so docs must be drifting broadly from code and specs.

**What the evidence says:** broad drift is not happening. Of the last 60 merged PRs, 53 touch `vultron/`, `specs/` or `notes/`; 29 of those also touch reader-facing `docs/` outside `docs/adr/`, and most of the rest plausibly had no docs impact (skill, CI, plan, test-ratchet, internal refactor). Spec pages (`docs/reference/specs/*`, rendered at build time from YAML), the API reference (19 mkdocstrings `:::` pages) and `docs/reference/examples/*.json` regenerate themselves, so a spec-only PR legitimately carries no docs diff.

**Underlying problem:** docs currency relies on the agent remembering, and nothing enforces or reviews it:

1. `check-docs-sync`, the one skill that asks which pages a change affects, is invoked only by `build` (`build/SKILL.md:386`), `bugfix` (`bugfix/SKILL.md:280`) and `learn`. In build and bugfix it runs after `create-pr`, nothing records that it ran, and bugfix says "Do not block the PR on large updates".
2. The docs checks that do exist trigger only if `docs/` was already modified, so they never fire when docs were forgotten: `AGENTS.md:189` ("`build-docs` — only if `docs/` modified"), `pr-triage/SKILL.md:163`, `pr-triage/REFERENCE.md:137`, `plan-issue/SKILL.md:232`.
3. `pr-triage` Phase 9 reviews whether `notes/` are current (`SKILL.md:156-158`; the REFERENCE.md domain map lists only notes) but never checks `docs/` pages. `pr-verify` and `pr-ship` inherit the gap. Changes made in `pr-execute` fix rounds and hand-authored PRs never get a docs check.
4. `plan-issue` treats docs as optional ("Docs updated — optional for all types", `:413`; `epic.md:60`), and its "Docs Output" means specs, notes and ADRs (`idea.md:31-35`). A known docs impact never becomes an implementation AC, so build's AC check cannot catch its absence.
5. `completeness-doctrine.md` "What Done Means" (`:20-25`) names docstrings, specs, notes and AGENTS.md, but not `docs/`. So FAIL/IMPROVE never applies to a stale docs page.

**Already correct, leave alone:** `check-docs-sync` itself (its three questions per changed area, the small-inline vs. large-deferred split, "never silently skip", PD-03-007), the generated reference and spec pages, and the `mkdocs build --strict` / `docs-links` resolution gates. The problem is where and whether the check is invoked, not how it works.

## Category

- [ ] Top risk
- [x] Technical debt
- [ ] Security
- [ ] Performance / scaling
- [ ] Fragile / high-churn area
- [x] Other — agent workflow / process gate

## Severity

medium. Drift is real but limited so far; it compounds silently in pages nobody rereads.

## Evidence

- **Stale prose left by a feature PR (confirmed at `origin/main`):** PR #3776 closed #2255 on 2026-09-28; its only `docs/` change was `docs/adr/0095-received-side-handler-result.md`. `docs/reference/glossary.md:529` (HandlerResult) still says every received handler returns "always `APPLIED` until the per-handler dispositions are assigned (#2255)".
- **Drift found only by chance during unrelated work, not by any gate:**
  - #3888: ADR-0099 prose still says `accepted-provisional` after graduation; the graduation commit added `lint_suppress: [status_prose_contradiction]` instead of fixing it.
  - #3853: `fv_demo.py` `CLI_HELP` (user-visible `vultron-demo fv --help`) describes a retired step.
  - #3839: `benchmarking_mpcvd.md` gives dimensionality 5, but the CS model has six substates.
- **Older draft-docs path drift:** `docs/developer/how-to/find-your-way-around.md:18,20` names `routers/actors.py` (a package since #970) and `wire/as2/extractor.py` (now a package).
- **No automated guard for prose:** CI (`docs-build-check.yml`) and pre-commit catch broken links, missing symbols, frontmatter and nav sync. Nothing flags a behaviour change whose prose description is now inaccurate. A sweep of every `vultron/...py` path and dotted symbol in `docs/**/*.md` found only the two stale paths above, which shows symbol-level checks are fine and the residual risk is behavioural prose that names no symbol.

## Impact if Ignored

Behavioural prose drift accumulates in pages that describe behaviour without naming a symbol (glossary, use-case pages, tutorials, how-tos). No automated check can catch that kind, so it surfaces only in periodic docs remediation sweeps (recently the closed epic #3511), or by chance, after readers have already been misled. Each PR that skips the check adds to the backlog quietly.

## Suggested Action

For planning, not yet decided:

1. Make docs currency an explicit, recorded gate **before** `create-pr` in `build` and `bugfix`: a checklist line stating either the pages updated or "no docs impact: <reason>", and a PR-body `Docs:` field in `shared/pr-body-guide.md`.
2. Have `pr-triage` (and therefore `pr-ship`) review for `docs/` drift against the diff even when `docs/` is untouched, parallel to its Phase 9 notes-currency check. Have `pr-verify` confirm that `pr-execute` fix rounds re-ran it.
3. Remove the circular "only if `docs/` modified" triggers: `AGENTS.md:189` should separate "which pages are affected" from "build the site".
4. Add `docs/` pages to the completeness doctrine's "What Done Means" list.
5. Have `plan-issue` write known docs impact into implementation ACs.
6. Fix `docs/reference/glossary.md:529` (can land independently).

Coordinate with #3586 (mechanical `notes/` currency checks), which is the notes-side analogue.

**Resolved**: 2026-09-30 — implementation tracked in #3926.
Docs PR: <https://github.com/CERTCC/Vultron/pull/3925>.
Spec: `specs/project-documentation.yaml` (PD-03-008 amended, PD-03-009 added).
