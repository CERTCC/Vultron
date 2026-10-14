---
source: NOTES-spec-authoring-rules--advisory-and-priority-gate-history
timestamp: '2026-10-14T14:33:12.430309+00:00'
title: 'spec-authoring-rules: advisory-warning and priority-gate defect history'
type: note
---

Archived from `notes/spec-authoring-rules.md` by #4498: the history of `must_without_verification` as a per-item warning and the list of priority gates that dropped prohibitions (#2466, #2467, #2535, #3612) are defect stories. The rules stay in § "A Priority Gate Names a Tier, Not a Keyword" and § "An Advisory That Is Routinely True Is Not Enforcement".

---

## Removed text

### An Advisory Warning Is Not Enforcement Once the Corpus Outgrows It

`spec-lint`'s per-item `must_without_verification` warning named exactly the
"MUST with nothing checking it" defect — and fired on MS-13-001 and MS-13-002
themselves for as long as they went unenforced. As a per-item `[WARN]` it did
not help, because well over half the corpus's MUST items had no `verification:`
field, so that one warning produced the large majority of the run's `[WARN]`
lines. A defect class
at that volume is indistinguishable from background noise, and a newly-introduced
instance is invisible.

It is now a per-item rule with a per-kind summary. Every unverified MUST-tier
requirement carries `verification_debt: '#N'`, naming the open issue that owns
verifying it, and `spec-lint` fails any item with neither field (MS-10-006). The
default output is one line per kind — the number of marked requirements,
tallied by owner — with the IDs only under `--list-unverified` (MS-10-005). The
number is computed from the markers, so a backfill lowers it without editing
anything else, and the line still shows each backfill issue's progress.

When you add a per-item advisory, decide up front what happens when it is
routinely true: collapse it to a count plus an opt-in listing, mark each
remaining hit with its owning issue, with a terminal state (see
[A Ratchet Needs an Owner and a Terminal State](#a-ratchet-needs-an-owner-and-a-terminal-state)),
or make it a hard error and
dispose of every existing hit. Do not ship a rule at partial adoption: per the
ISSUE-3480 learning, a requirement half-adopted reads as *no rule here*, which is
worse than one nobody has started.

### A Priority Gate Names a Tier, Not a Keyword

RFC 2119 gives `MUST NOT` the same absolute strength as `MUST`, and `SHOULD NOT`
the same strength as `SHOULD`. Every gate that selects requirements by priority
must therefore select a *tier* (MS-02-003). In the code, that means asking the
shared tier definition on `RFC2119Priority` — `spec.priority.is_must_tier` or
`.tier` (MS-02-004) — never
`spec.priority == RFC2119Priority.MUST`. A static test,
`test/metadata/specs/test_priority_tier_gate.py`, fails on any comparison
against an individual member or a priority string under
`vultron/metadata/specs/` or `scripts/`; its allowlist holds exactly one entry,
SR-11-003's selector, and fails if that entry stops matching, so retiring the
exception also retires the allowlist.

The literal comparison is easy to write and fails silently: nothing errors, and
the prohibitions simply drop out. That happened more than once before MS-02-003:

- `must_without_verification` was scoped to "MUST requirements" by the wording
  of the issue that introduced it (#2466), and a unit test then pinned the
  exclusion. The test read as a deliberate decision but only preserved the
  wording of that AC. So the #2467 protocol-tier backfill reported the tier
  complete while most protocol `MUST_NOT`s had no `verification:` at all
  (#2535, #3612). The count now covers both keywords.
- SR-11-003's story gate and SR-11-004's advisory had the same shape. The
  second now covers `SHOULD_NOT` by selecting "below the MUST tier" rather than
  naming keywords. SR-11-003 is the one recorded exception, still `MUST`-only
  because extending it needs stories that do not exist yet (see its `note:`);
  the exception is written once, in `sr_11_003_gate_applies()` in
  `vultron/metadata/specs/lint.py`, and `scripts/backfill_stories.py` selects
  through that predicate rather than carrying a second copy of it.
- `spec-backstop` got it right (`priority in ("MUST", "MUST_NOT")`), but as a
  second hand-written copy of the tiering, which is the drift MS-02-004's
  single shared definition prevents. It now asks `is_must_tier`.

When a priority-scoped rule is proposed, read "MUST" in its AC as the tier
unless the AC explicitly excludes the negative form *and says why*. If you find
a test that asserts a negative form is excluded, trace it to a decision before
you trust it.
