---
title: Specs vs. ADRs — Delineation Guidelines
status: active
related_specs:
  - specs/meta-specifications.yaml
related_notes:
  - notes/bt-pitfalls.md
  - notes/spec-authoring-rules.md
---

# Specs vs. ADRs — Delineation Guidelines

Implementation guidance for deciding when to write a spec entry, an ADR, or
both. Formalizes the decision tree captured in `specs/meta-specifications.yaml`
MS-11-001 through MS-11-006.

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

---

## Decision-Tree Heuristic

Use this self-check before committing a change:

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

---

## The Externally-Observable Behavior Test

Before writing a new `specs/` requirement for any behavior observed during
implementation, apply this gate:

> **Would a participant running a different implementation of the Vultron
> protocol notice if this requirement were violated?**

| Answer | Route to | Examples |
|---|---|---|
| **Yes** — the behavior is externally-observable or protocol-visible | `specs/` | Message semantics, state-machine invariants, wire format constraints, compliance-visible output |
| **No** — the behavior is an internal implementation convention | `AGENTS.md` | File paths, naming conventions, agent guidance, demo step ordering, coding practices |

This gate operationalizes two existing rules:

- **MS-05-004**: Requirements must be declarative — describing *what* the
  system must do, not *how* it is implemented internally.
- **MS-12** (four-tier taxonomy): A requirement that cannot pass the
  `protocol` or `architecture` tier tests is `project` or `process` kind.
  If it also fails the externally-visible test — i.e., only this codebase
  cares about it — it belongs in `AGENTS.md` rather than `specs/` entirely.

### Common Misrouted Requirements

These patterns commonly appear in `specs/` but belong in `AGENTS.md`:

- **File/module paths**: "Factory functions MUST live in
  `vultron/wire/as2/factories/`" — only this codebase has this layout.
- **Demo step ordering**: "Step 3 MUST follow step 2 in the demo script" —
  a different implementation would have no demo, let alone this step order.
- **Agent instructions**: "The agent MUST confirm the selected bug with the
  user before fixing it" — describes agent workflow, not protocol compliance.
- **Naming conventions**: "Test files MUST be named `test_*.py`" — already
  enforced by pytest discovery config; not protocol-relevant.
- **Ambiguous `project`/`process` kind requirements**: If a requirement would
  be kind `project` (MS-12-002) *and* only an internal convention, it belongs
  in `AGENTS.md`. The `specs/` corpus should capture what an independent
  conformance checker would verify; internal conventions belong in agent guidance.

### How This Relates to the `learn` Skill

The `learn` skill's `signal: spec-gap` path must apply this test before
promoting an observation to `specs/`. If the behavior is not externally
observable, the correct destination is `AGENTS.md` (recurring pitfall) or
`notes/` (design decision), not a new MUST requirement in `specs/`. See also
the anti-pattern list in `specs/AGENTS.md`.

---

## Worked Examples

### ADR only

- **ADR-0006 Use CalVer for Project Versioning** — this is a binary,
  one-time choice ("we use CalVer, not SemVer"). There is no recurring
  per-change requirement for agents to check, so no spec entry is needed.
- **ADR-0014 Pin GitHub Actions to Full Commit SHAs** — once the policy is
  set, there is a CI enforcement mechanism; agents do not need a spec entry
  to implement it per-change.

### Spec only

- `MS-04-001` "Requirement IDs MUST follow `PREFIX-NN-NNN` format" — this
  is an uncontested formatting rule. No alternatives were evaluated; it is
  simply the chosen convention. A spec entry captures the rule for agents
  without requiring ADR justification.
- `CS-08-002` "Optional string fields MUST reject empty strings" — a
  practical validation rule with no meaningful opposing design.

### Both ADR and spec

- **ADR-0009 Hexagonal Architecture** generated multiple
  `architecture.yaml` ARCH-01 through ARCH-12 requirements. The ADR records
  why hexagonal was chosen over a layered or transaction-script architecture;
  the spec entries define the per-change layer-separation rules that agents
  must enforce.
- **ADR-0016 SQLModel/SQLite DataLayer** generated DataLayer spec entries
  covering type-safe writes, auto-rehydration, and port isolation. The ADR
  records why SQLModel was preferred over TinyDB or raw SQLite; the spec
  entries give agents enforceable rules.

---

## Choosing the ADR `status` Value

The ADR `status:` frontmatter field is the **primary confidence signal** that
reaches coding agents: `deepen-context` weights how much to trust an ADR by its
status. A wrong or careless status value is a landmine — an agent will treat a
`status: accepted` ADR as settled fact even when the decision was never
validated. Choose the value deliberately, not by habit.

**Value set** (MADR-aligned, extended with `accepted-provisional`):

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
         Move newly-retired files to docs/adr/archived/ (see ADR-0043).

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
body says the design is provisional, "formed in sand", or "expected to
converge", the status is `accepted-provisional` (or `proposed`), never
`accepted`. A lint check enforces this (see `specs/meta-specifications.yaml`
MS-14). The `decision-audit` skill hunts for exactly this contradiction.

> **Why a status value and not a separate `confidence` field?** We already have
> a status field that agents read; a parallel confidence field would be one
> more thing to keep in sync and one more source of drift. Expanding the status
> vocabulary keeps a single source of truth. See ADR-0043.

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

## Cross-Referencing Pattern

When creating both an ADR and spec entries, wire them together:

**In the spec `rationale` field** (MS-11-004 — use the per-requirement `rationale`, not the spec-group `description`):

```yaml
rationale: >
  Rules for DataLayer writes derived from ADR-0016
  (docs/adr/0016-sqlmodel-sqlite-datalayer.md).
```

**In the ADR "More Information" section:**

```markdown
## More Information

Generated spec requirements: `datalayer.yaml` DL-01 through DL-03.
```

---

## Never State Ephemeral Counts in Long-Lived Docs

Long-lived documents — specs, notes files, AGENTS.md — **MUST NOT state
counts that will drift independently of their authoritative source** (MS-16-001).

### The problem

When a spec requirement like DEMOMA-16-001 defines an enumeration ("the five
universal event types"), sibling requirements and cross-file citations are
tempted to copy the count: "the five universal types (DEMOMA-16-001)". The
linter validates that `DEMOMA-16-001` resolves; it has no opinion about the
prose next to it. When DEMOMA-16-001 is updated (e.g., a sixth type is added),
every copied count drifts silently — a reader who encounters a stale count first
gets a false picture of the system. The count adds no normative force.

The same applies to any long-lived doc: writing "there are 4 unimplemented
nodes" or "15 xfails" is a snapshot virtually guaranteed to be wrong when read
later.

### The fix

**When cross-referencing another spec**, omit the count and cite the source by
ID:

| Instead of | Write |
|---|---|
| "the five universal types (DEMOMA-16-001)" | "the universal types (DEMOMA-16-001)" |
| "these four scenarios cover all types" | "these scenarios cover all types" |
| "the full 9-scenario suite" | "the full scenario suite" |

**Counts are only appropriate in the authoritative source itself** — the spec
entry that *defines* the enumeration (e.g., DEMOMA-16-001 listing its own
members is the authority for that count; siblings that cross-reference it are
not).

**In notes and AGENTS.md**, avoid counting items that can change: replace
"there are 4 unimplemented nodes" with "the unimplemented nodes are listed in
[...]"; replace "15 xfails" with "known-flaky tests are tracked in
`notes/flaky-tests.md`".

---

## Where the Authoritative Rules Live

| Artifact | Location |
|---|---|
| Normative requirements (MS-11-001 – MS-11-006) | `specs/meta-specifications.yaml` |
| Human-facing guidance ("when to write an ADR") | `docs/adr/index.md` |
| This decision table and heuristic | `notes/specs-vs-adrs.md` (this file) |
| Agent-facing shorthand | `AGENTS.md` "Change Protocol" section |

## ADR "What Is Removed" Lists Are Scoped to One Use, Not Global Existence

Grep the spec corpus for MUSTs describing the *operation* a node implements
before deleting it. An ADR may list a component as removed from one specific
initialization flow while spec entries still require it in another.

Source: ISSUE-1777; see also `notes/bt-pitfalls.md`
