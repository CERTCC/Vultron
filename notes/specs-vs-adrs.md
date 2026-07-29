---
title: Specs vs. ADRs — Delineation Guidelines
status: active
related_specs:
  - specs/meta-specifications.yaml
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

## Where the Authoritative Rules Live

| Artifact | Location |
|---|---|
| Normative requirements (MS-11-001 – MS-11-006) | `specs/meta-specifications.yaml` |
| Human-facing guidance ("when to write an ADR") | `docs/adr/index.md` |
| This decision table and heuristic | `notes/specs-vs-adrs.md` (this file) |
| Agent-facing shorthand | `AGENTS.md` "Change Protocol" section |
