---
title: Specs vs. ADRs — Delineation Guidelines
status: active
kind: guidance
description: >
  When to write a spec entry, an ADR, or both (MS-11); why an ADR is a
  historical record while specs and notes carry the current state (ADR-0127),
  so no refactor obliges an ADR edit and no scrub is owed; back-edges from live
  records; the externally-observable test for what belongs in specs/; choosing
  an ADR status and the epoch and edit-tier lifecycle (ADR-0120, MS-14); and
  never restating drift-prone counts in long-lived docs (MS-16).
related_specs:
  - specs/meta-specifications.yaml (MS-11, MS-12, MS-14, MS-15, MS-16)
  - specs/spec-registry.yaml (SR-07-017)
  - specs/architecture.yaml (ARCH-18-005)
  - specs/demo-ci.yaml (DEMOCI-11-008)
related_notes:
  - notes/spec-authoring-rules.md
  - notes/agentic-workflow.md
  - notes/documentation-sweeps.md
  - notes/user-story-catalog.md
  - notes/git-workflow-pitfalls.md
---

# Specs vs. ADRs — Delineation Guidelines

How to decide between a spec entry, an ADR, or both. The normative rules are
MS-11-001 through MS-11-008 in `specs/meta-specifications.yaml`; the human-facing
version is `docs/adr/index.md`.

---

## Decision Table

| Question | Decision | Rationale |
|---|---|---|
| Primary purpose of a spec | Capture testable requirements (what the system must do) | Specs are consumed by implementation agents; they need RFC 2119 language, not narrative |
| Primary purpose of an ADR | Record why a choice was made over alternatives that were evaluated | The key signal is "options were weighed and one was rejected" |
| When to create both | When a significant architectural decision also generates recurring testable requirements | The ADR answers "why?"; the spec answers "what must I do?" |
| When a spec alone suffices | When the approach is uncontested — no real fork existed | Creating an ADR for an obvious choice adds noise to the decision log |
| When an ADR alone suffices | When the decision is a one-time structural/process choice with no per-change requirement | Not every decision produces enforceable requirements |
| Cross-referencing | Spec `rationale` field SHOULD cite the ADR; ADR "More Information" SHOULD list spec IDs | Bidirectional links preserve traceability in both directions |

### Decision-Tree Heuristic

```text
1. Am I capturing what the system must/should/may do?
   YES → Write a spec entry.

2. Did I evaluate and reject at least one meaningful alternative?
   YES → Write an ADR.

3. Does the decision also produce recurring testable requirements?
   YES (to 2) → Write both an ADR and a spec entry.

4. Is the approach obvious/uncontested with no real fork?
   YES → Spec entry only. No ADR needed.

5. Is this a one-time structural choice with no per-change requirement?
   YES → ADR only. No spec entry needed.
```

Worked examples: **ADR only** — ADR-0006 (CalVer) and ADR-0014 (SHA-pinned
Actions), one-time choices with no per-change requirement. **Spec only** —
MS-04-001 (ID format) and CS-08-002 (non-empty strings), uncontested rules.
**Both** — ADR-0009 (hexagonal architecture) and the ARCH layer rules; ADR-0016
(SQLModel DataLayer) and the DataLayer requirements.

### Cross-Referencing Pattern

Cite the ADR in the per-requirement `rationale` (not the group `description`)
and in the `adr:` field; list the generated requirements in the ADR's "More
Information" section (MS-11-004):

```yaml
rationale: >
  Rules for DataLayer writes derived from ADR-0016
  (docs/adr/0016-sqlmodel-sqlite-datalayer.md).
```

```markdown
## More Information

Generated spec requirements: `datalayer.yaml` DL-01 through DL-03.
```

---

## An ADR Is a Historical Record; Specs and Notes Are the Current State

An ADR answers what we decided and why, given what we knew at the time — an
answer that cannot go stale, because the past does not change (ADR-0127). Specs
and notes describe the current codebase and carry a currency obligation an ADR
does not. Consequences:

- **A refactor is never responsible for updating an ADR.** When an ADR names a
  function or path later renamed or deleted, the decision still stands; only its
  description of the code has aged. Nothing fails on a stale symbol in an ADR
  body, deliberately.
- **A constraint future code must obey does not live in an ADR body.** Put it in
  a spec requirement when testable, or a `notes/` file when design insight, and
  cite the ADR as provenance (MS-11-004).
- **A spec or note must not resolve its meaning by pointing into an ADR body.**
  Cite the ADR for *why*; state the rule where the reader already is. MS-11-007
  forbids citing a numbered detail, and
  `test/metadata/test_no_adr_detail_citations.py` fails one under `specs/` or
  `notes/`.

What stays in the body: the reasoning, the rejected options, and how the code
looked then, written to read as of its time, with removed symbols annotated in
the ADR-0063 style rather than deleted. What does not: project tracking and
drift-prone detail (counts, metrics, `file.py:line`). The editing mechanics are
the Edit Tiers below.

### An ADR records what stays invariant

An ADR must not state a decision already known to become obsolete. Write the
stable principle with room for a foreseeable change, and keep the current,
changeable policy in the specs and notes that cite the ADR. ADR-0134 states that
checks protecting implementers apply to the implementer-facing kinds; which kind
each check covers today is in SR-05-004/005, SR-11-003/004 and MS-12-006,
because the story gate is expected to widen (#4528).

### An aged code reference in an ADR body is not a defect, and there is no scrub

The corpus's existing stale code references are **not** a backlog: each is an
accurate account of the code as it then stood. No issue owns scrubbing them and
no advisory counts them, since a count would re-describe the same sentences as
debt and invite the scrub back. Enforcement is **forward-only**: the
`adr-added-reference-check` hook fails a backticked path or symbol that an ADR
edit *adds* and that resolves nowhere (MS-15-006); a reference already on the
base never fails, so no refactor can trip it. A record that annotates a removed
name opts out with `lint_suppress: [phantom_symbol_ref]` or `[phantom_path_ref]`
(MS-15-007). A merge-blocking check keyed on code changes is rejected; it would
reinstate the refactor obligation.

### Routine context routes through records by title and edge

Routine task context does not load record bodies (MS-11-008). `deepen-context`
Step 2 finds in-scope records by title in the generated sections of
`docs/adr/index.md`, then loads the requirements each generated with
`spec-dump --adr ADR-NNNN`, which walks the `adr:` edge backwards (SR-07-017).
A record with only a prose back-edge has no `adr:` edge, so `--adr` selects
nothing; `spec-dump` names it, and the agent reads the `specs/` and `notes/`
files that cite it. Converting such a citation to an `adr:` edge makes the
record reachable by the tool.

The skills that make a record their object of work keep full access to bodies;
the list and reasons are the exception table in `deepen-context` Step 2, and
each weighs what it reads by `.agents/skills/shared/weighing-decision-records.md`.
`test/metadata/test_routine_context_skips_adr_bodies.py` fails a skill off the
list that instructs reading a body. If the list grows until most work falls
under it, ADR-0127's revisit trigger has fired.

### Every live record is reachable from a spec or a note, or is record-only

A decision stated nowhere but a body is lost to routine context, so every live
record (not archived, superseded, deprecated or rejected) needs a **back-edge**:
an `adr:` edge on a requirement, or a citation in a `specs/` or `notes/` file.
A record without one is handled one of three ways:

- **A requirement already covers the decision** — add the record to its `adr:`
  field. This is the usual case, and the only edge tooling can walk.
- **Nothing covers it** — state the decision in full in a spec requirement or a
  `notes/` file, citing the record as provenance.
- **The record is legitimately record-only** — a one-time process choice
  (MS-11-006). Add it to `RECORD_ONLY_EXEMPTIONS` in
  `vultron/metadata/adr/back_edges.py`, a pinned exemption set with no terminal
  value (ARCH-18-005).

`uv run adr-back-edges` reports every live record with no back-edge and every
exemption no longer needed; `test/metadata/test_adr_back_edges.py` fails on
either.

---

## The Externally-Observable Behavior Test

Before writing a new `specs/` requirement for a behavior observed during
implementation, ask:

> **Would a participant running a different implementation of the Vultron
> protocol notice if this requirement were violated?**

| Answer | Route to | Examples |
|---|---|---|
| **Yes** — the behavior is externally-observable or protocol-visible | `specs/` | Message semantics, state-machine invariants, wire format constraints, compliance-visible output |
| **No** — the behavior is an internal implementation convention | `AGENTS.md` | File paths, naming conventions, agent guidance, demo step ordering, coding practices |

This operationalizes MS-05-004 (declarative requirements) and MS-12: a
requirement that fails the `protocol`, `foundation` and `architecture` tests is
`project` or `process`, and if only this codebase's conventions care about it,
it belongs in `AGENTS.md` rather than `specs/`. Commonly misrouted: file and
module paths, demo step ordering, agent instructions, and naming conventions a
tool already enforces. The `learn` skill's `signal: spec-gap` path applies this
test before promoting an observation to `specs/`.

---

## Choosing the ADR `status` Value

The ADR `status:` is the **primary confidence signal** that reaches coding
agents: routine context sees it as the `docs/adr/index.md` section a record is
listed under, and every skill that reads a body weighs the record by it. An
agent treats `status: accepted` as settled fact, so choose it deliberately.

**Value set** (MADR-aligned, extended with `accepted-provisional`; ADR-0043):

| Value | Meaning | Agent should |
|---|---|---|
| `proposed` | Decision drafted, not yet ratified. | Treat as a proposal; validate before building on it. |
| `accepted` | Ratified **and** validated by implementation or review. | Build on it; do not re-litigate. |
| `accepted-provisional` | Ratified as the current direction but **explicitly not yet validated** — expected to converge after N implementations. | Follow it, but treat its details as challengeable; refine the ADR if the pattern proves wrong. |
| `deprecated` | No longer the recommended approach; not yet replaced. | Do not build on it; check for a successor. |
| `superseded` (+ `superseded_by:` field) | Replaced by a named later ADR. | Follow the successor; newly-retired ADRs are moved to `docs/adr/archived/`. |
| `rejected` | Considered and declined. | Do not implement; the record exists to prevent re-proposal. |

**Decision tree — pick the status when writing or updating an ADR:**

```text
1. Was the decision considered and declined?
   YES → rejected.

2. Has a later ADR replaced this one?
   YES → status: superseded, plus a superseded_by: <successor filename> field.
         Add this ADR to the successor's supersedes: list (MS-14-011).
         Move newly-retired files to docs/adr/archived/ (see ADR-0043).
   ONLY ONE DECISION IN IT → keep the status; add partially_superseded_by:
         <successor filename> here and this ADR to the successor's
         partially_supersedes: list. Do not archive it.
   The loader fails a link recorded on only one of the two ADRs.

3. Is the approach no longer recommended but not yet replaced?
   YES → deprecated.

4. Is the decision still just a draft awaiting ratification?
   YES → proposed.

5. Is the decision ratified as the current direction?
   ├─ Has it been validated by real implementation or review?
   │    YES → accepted.
   └─ Is it explicitly unvalidated / "formed in sand" / expected to converge?
        YES → accepted-provisional.  Do NOT mark such ADRs `accepted`:
              the prose will contradict the status and mislead agents.
```

**The cardinal rule:** the `status:` value and the ADR prose must agree. If the
body says the design is provisional or expected to converge, the status is
`accepted-provisional` (or `proposed`), never `accepted`. A lint check enforces
this (MS-14), and the `decision-audit` skill hunts for the contradiction.

### ADR Lifecycle: Epochs and Edit Tiers

ADR-0120 ties `status` to how far a decision has been built on, with timers as a
backstop. Frontmatter carries `created` (immutable), `updated` (material edits
only) and `revision` (bumped per material edit) (MS-14-008). The timers run from
`updated`, in whole days:

| Epoch | Ends | `status` | Editing |
|---|---|---|---|
| 1 | first test-verified dependent, or day 14 | `proposed` | edit in place freely |
| 2 | day 28 | `accepted-provisional` | ask the human: edit in place or supersede |
| 3 | never | `accepted` | supersede (below) |

A **test-verified dependent** is a requirement that cites the ADR in `adr:` and
whose verification names a test file that exists (not one that passes). The PR
that creates the first one sets the ADR to `accepted-provisional` in the same
change (MS-14-010). Status only moves forward; a promotion ahead of the computed
epoch needs a `status_override:` the PR adds or changes (MS-14-012). Agents
implement against `proposed` ADRs; the mandatory human touch is the epoch-2 ask.

**Edit tiers.** Editorial fixes and append-only annotations are allowed in any
epoch and change neither `updated` nor `revision`. A clarification after epoch 1
is appended as a dated note. A material change (*would something built on the
old text now be wrong?*) bumps `updated` and `revision`. In epoch 3, a material
change to one detail with the chosen option intact is a dated Amendment quoting
the replaced text; a change of chosen option is a new ADR that supersedes the
old one. Never rewrite an accepted ADR under its own number.

**The clock never fails a merge-blocking check.** An ADR crossing a boundary
changes no commit, so a check reading today's date would turn `main` red with
no one to blame. A PR that materially edits or adds an ADR owns its status on
that date (MS-14-007); every other status behind its epoch is reported by the
hourly `adr-status-drift` workflow through one self-closing issue, and a human
flips it. The `adr-lifecycle-check` hook and the `ADR Lifecycle` PR workflow
enforce MS-14-007, -009, -010 and -012 against `HEAD` and the merge base.
`uv run adr-index --epochs` prints each live ADR's epoch, status and revision.

**`status_override:` is a human's reason, for that one ADR.** A tooling rollout
or an agent never writes a placeholder override: it hides the ADR from the drift
report, and nothing would ever prompt the promised review (#4521).

### A Provisional ADR Phrases an Unbuilt Contract in the Future Tense

`accepted-provisional` warns that the *decision* is unvalidated, but the prose
can still state an enforcement contract in the present tense of a shipped one,
and a reader takes "the validator raises `X`" as a fact about the code. ADR-0075
did this, a note copied it, and a bug was filed on the false premise (#2860).

- In a provisional or proposed ADR, phrase not-yet-built enforcement in the
  **future or conditional** tense ("will raise") until a regression test pins
  it.
- Before relying on such a present-tense claim, or a note that cites one, grep
  for the named validator or guard and confirm it truly raises.

The status must match the decision's confidence; the tense must match the
implementation's build state.

### ADR "What Is Removed" Lists Are Scoped to One Use, Not Global Existence

An ADR may list a component as removed from one flow while spec entries still
require it in another. Before deleting a node, grep the spec corpus for MUSTs
describing the *operation* it implements (#1777).

---

## Never State Unverifiable, Drift-Prone Facts in Long-Lived Docs

Long-lived documents — specs, notes files, AGENTS.md — **MUST NOT state counts
that will drift independently of their authoritative source** (MS-16-001), and
more generally **MUST NOT state any fact that no automated check could falsify
and that drifts independently of its source** (MS-16-002). The test is "could a
test fail on this sentence?", not "is this a number?".

A sibling requirement tempted to copy an enumeration's size — "the five
universal types (DEMOMA-16-001)" — drifts silently when the source changes, and
the linter checks only that the ID resolves. The count adds no normative force.
A doc table that mirrors a code, spec or config inventory rots unevenly: the
columns a test could check stay roughly right while the rest go confidently
wrong. Triage such a table per `notes/documentation-sweeps.md` § "Mirrored
tables rot in the column no test can hold".

**Cross-reference without the count:**

| Instead of | Write |
|---|---|
| "the five universal types (DEMOMA-16-001)" | "the universal types (DEMOMA-16-001)" |
| "these four scenarios cover all types" | "these scenarios cover all types" |
| "the full 9-scenario suite" | "the full scenario suite" |

Counts belong only in the authoritative source itself (DEMOMA-16-001 listing its
own members). In notes and AGENTS.md, point at the list instead of counting it.

### The scenario-count rule is machine-enforced, and this file is exempt

For the demo scenario set, DEMOCI-11-008 forbids a declared scenario-table
consumer from restating the count; `restated_counts()` in
`vultron/metadata/demo_scenarios/prose_counts.py` enforces it over
`SCENARIO_TABLE_CONSUMERS`, wired into `uv run demo-scenarios --check` and the
`demo-scenarios-sync` hook. A restatement inside a `## Change history` section
is exempt, because it records a past state.

**This file is deliberately not a declared consumer.** The "Instead of" column
above must keep its restated counts — they are the counter-examples the guidance
is made of — and a check cannot tell a counter-example from the thing it warns
against. Adding `notes/specs-vs-adrs.md` to `SCENARIO_TABLE_CONSUMERS` would
report this section's own table and pressure someone into deleting the guidance.
The exemption is recorded in `EXEMPT_CONSUMERS` in the same module.

### ADR bodies are out of scope, and stay that way

MS-16 names specs, notes, AGENTS.md and mirrored `docs/` tables, not ADR bodies,
and ADR-0127 decided it should not. A body is read as history, so a dated
measurement in one stays correct as of its date; extending MS-16 there would
re-describe accurate prose as debt and invite the scrub ADR-0127 rejects. A body
owes only the forward-only reference check (MS-15-006).
