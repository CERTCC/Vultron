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
| Cross-referencing | Spec description SHOULD cite the ADR; ADR "More Information" SHOULD list spec IDs | Bidirectional links preserve traceability in both directions |

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

## Cross-Referencing Pattern

When creating both an ADR and spec entries, wire them together:

**In the spec description field:**

```yaml
description: >
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
