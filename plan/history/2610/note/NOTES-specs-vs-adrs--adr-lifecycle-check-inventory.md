---
source: NOTES-specs-vs-adrs--adr-lifecycle-check-inventory
timestamp: '2026-10-14T14:33:14.178850+00:00'
title: 'specs-vs-adrs: ADR lifecycle check inventory and provisional-tense story'
type: note
---

Archived from `notes/specs-vs-adrs.md` by #4498: the item-by-item list of what `adr-lifecycle-check`, `adr-added-reference-check` and `adr-status-drift` check restated MS-14-007..012 and MS-15-006 and the tools' own behavior; the ADR-0075 story is history. The rules stay in § "ADR Lifecycle: Epochs and Edit Tiers" and § "A Provisional ADR Phrases an Unbuilt Contract in the Future Tense"; the checks are specified by MS-14 and MS-15-006.

---

## Removed text

**What is checked (MS-14-007, MS-14-009, MS-14-010, MS-14-012, MS-15-006).**
Three fields are required on every ADR (MS-14-008); `date` is the older spelling
of `created` and may stay. Epochs are counted in whole days (14 and 28) because
`updated` is a date. Retired and rejected ADRs have no epoch. A
`status_override:` with a human's reason holds a status off its epoch. The
reason is a human's, written for that one ADR: a tooling rollout or an agent
never writes a placeholder override, because an override hides the ADR from
the drift report and nothing would ever prompt the promised review (#4521).

- `spec-lint` never fails a status the clock has made stale (MS-14-007). It
  warns on a `proposed` ADR with a test-verified dependent and no override,
  because that needs no clock (MS-14-010).
- The `adr-lifecycle-check` pre-commit hook compares the working tree with
  `HEAD`; the `ADR Lifecycle` pull-request workflow runs the same check against
  the merge base. The dependents are counted on each side of the change. It
  fails:
  - a material edit (`updated` moved, or a new ADR) whose status is not its
    epoch on that date, without an override (MS-14-007);
  - a status change that moves back, ever, or one that moves ahead of the
    epoch without a `status_override:` the change adds or changes
    (MS-14-012);
  - a change that gives a `proposed` ADR its first test-verified dependent
    without setting it to `accepted-provisional`, or adding or changing a
    `status_override:` (MS-14-010). The change need not touch the ADR, so the
    workflow also runs when only `specs/` or `test/` changes; the local hook
    runs only when an ADR is staged, and counts only test files git tracks;
  - a bump of `updated` on an ADR past epoch 1, without an override (MS-14-009);
  - a changed Decision Outcome or Considered Options section on an epoch-3 ADR,
    unless the edit adds a heading naming "Amendment" and a `YYYY-MM-DD` date.
  For the last two, an ADR's epoch is the later of its computed epoch and the
  one its status names, since a status ahead of the clock stands: an `accepted`
  ADR is epoch 3 however recently it was updated. An ADR held by a
  `status_override:` is in the epoch its status names.
- The hourly `adr-status-drift` workflow lists each ADR whose status is behind
  its epoch on `main`, never one ahead of it.
- The `adr-added-reference-check` pre-commit hook (MS-15-006) also compares an
  edited ADR with `HEAD`, and fails a backticked path or code symbol the edit
  *adds* that resolves nowhere — class names, called names and class members
  included, not only underscored constants. A reference already on the base
  never fails, so no refactor can trip it (ADR-0127). A record that annotates a
  removed name opts out with `lint_suppress: [phantom_symbol_ref]` or
  `[phantom_path_ref]` (MS-15-007).
- Both hooks also run in the `ADR Lifecycle` pull-request workflow against the
  merge base, so skipping a local hook does not bypass them.
- A test-verified dependent is found by checking that the named test file
  exists, not that it passes.
- `uv run adr-index --epochs` prints each live ADR's epoch, status and revision.
  The generated `index.md` shows only the revision (`*(revision N)*`, when above
  1), because the epoch depends on today's date and the spec corpus, and the
  index is compared byte for byte.

### A Provisional ADR Must Phrase an Unbuilt Contract in the Future Tense

The `accepted-provisional` status warns that the *decision* is unvalidated, but
it does not stop the prose from asserting an *enforcement contract* in the
present, definite tense of a shipped one. That is a distinct trap: a reader (or
a downstream note that quotes the ADR verbatim) takes "the validator raises
`X` on violation" as a fact about the code, when it names an intended behavior
that was never built — and nothing ties the sentence to a test, so the drift is
silent. ADR-0075 did exactly this: it stated that `ParticipantStatus`
construction "validates role-dimension invariants… raising `VultronValidationError`",
a `mode="after"` raise that was never written (the real validator is a
`mode="before"` auto-seed that deliberately does not raise). `notes/case-state-model.md`
copied the claim, and a bug (#2860) was filed on the false premise that the
invariant was unenforced — when it is in fact enforced at the guard layer.

**How to apply:**

- When writing a provisional (or proposed) ADR, phrase any not-yet-built
  enforcement in the **future or conditional** tense ("will raise", "is expected
  to refuse") until a linked regression test pins it. Reserve present-tense
  "raises / refuses / validates" for behavior that a test actually exercises.
- Before relying on a provisional ADR's present-tense enforcement claim — or a
  note that cites one — grep for the named validator/guard and confirm it truly
  raises or refuses. The claim may be aspirational.
- This is the tense-level companion to the cardinal rule above: the status must
  match the *decision's* confidence, and the prose tense must match the
  *implementation's* build state.

Source: ISSUE-2860

## Where the Authoritative Rules Live

| Artifact | Location |
|---|---|
| Normative requirements (MS-11) | `specs/meta-specifications.yaml` |
| Human-facing guidance ("when to write an ADR") | `docs/adr/index.md` |
| This decision table and heuristic | `notes/specs-vs-adrs.md` (this file) |
| Agent-facing shorthand | `AGENTS.md` "Change Protocol" section |

## ADR "What Is Removed" Lists Are Scoped to One Use, Not Global Existence

Grep the spec corpus for MUSTs describing the *operation* a node implements
before deleting it. An ADR may list a component as removed from one specific
initialization flow while spec entries still require it in another.

Source: ISSUE-1777; see also `notes/bt-pitfalls.md`
