# Project Report — Reference

## Report Structure

```markdown
# Vultron Project — <Period> Work Sponsor Report

## Executive Summary

2–4 sentences covering:
- Overall productivity characterization
- The 2–4 major themes of the period
- Any notable caveats (work in progress, issues discovered post-period)

---

## <Theme 1 Heading>

...

## <Theme 2 Heading>

...

[4–7 theme sections total]

---

*Report covers: <start> through <end> |
Repository: [CERTCC/Vultron](https://github.com/CERTCC/Vultron)*
```

---

## Tone Guidelines

**Audience**: work sponsors who are not familiar with the internal
codebase. They care about:

- What the system can do **now** that it couldn't before
- What is working more reliably or efficiently
- What is still in progress or has caveats
- General health of the project (test coverage, dependency hygiene)

**Do**:

- Lead with capabilities and user-visible outcomes
- Use plain language; briefly explain any necessary technical term
- Note when something is "in progress" or "partially complete"
- Be accurate about caveats — do not oversell

**Don't**:

- Reference internal module names, class names, or file paths
- Use unexplained acronyms (BT, EM, RM, AS2, etc.) without a brief gloss
- Claim something is fully functional if issues were found post-close
- Include every commit; focus on the 5–10 most significant changes
- Use internal shorthand for numbered work items without describing what they are
  (e.g., "Production Collapse 3", "FUZZ-08e", "ADR-0042" all need a plain-language
  gloss or should be replaced with a description of the actual change)

---

## Jargon Glossary and Rewrite Guide

When any of the following terms appear in a draft without an inline explanation,
either add the gloss shown or rewrite using the plain-language alternative.

| Term | First-use gloss or plain-language rewrite |
|---|---|
| BT / behavior tree | "behavior tree — a decision-automation technique borrowed from game AI and robotics" |
| PEC | "PEC (per-participant embargo-consent state machine)" — or just "embargo-consent state machine" |
| EM / embargo management | "embargo management — tracking the active embargo agreement" |
| RM / report management | "report management — the state machine governing a vulnerability report's lifecycle" |
| CS / case status | "case status — the aggregate fix/deploy/disclosure state of the case" |
| VFD state flags | "VFD fix-state flags (Vendor fix-ready / Fix-deployed / Disclosed)" — or describe the specific transition in plain terms |
| f→F / d→D transitions | describe the meaning: "marking a fix as developed" / "marking a fix as deployed" |
| ADR / ADR-NNNN | "architectural decision record (ADR-NNNN)" on first use; subsequent mentions can use the abbreviation |
| call-out seam / call-out point | "injectable call-out point — a hook where a custom backend can be plugged in" |
| DataLayer | "the internal data layer — which separates wire-format messages from domain objects" |
| wire vocab / wire format | "wire-format messages (ActivityStreams 2.0, a standard social-web protocol)" |
| blackboard | "shared blackboard — the in-memory store behavior tree nodes read from and write to" |
| ledger | explain on first use: "case ledger — the append-only log of all events for a case" |
| FUZZ-08x | do not use; describe what changed (e.g., "the exploit-strategy evaluation fuzzer nodes were converted to call-out point abstractions") |
| Production Collapse N | do not use; describe what changed (e.g., "the notification loop was collapsed from a stub into a full call-out abstraction") |
| ASGIEmitter | "the in-process delivery shim (ASGIEmitter)" — or just describe what it did |
| CaseActor | "the CaseActor service — a dedicated container that owns the canonical case record" |
| DEMOMA-NN | do not use alone; describe the scenario by its actors and workflow |
| ECA format | "ECA (Event–Condition–Action) spec format" |
| ratchet test | "architecture ratchet test — an automated check that prevents a design boundary from eroding" |

### Bad/good rewrite examples

❌ "PEC state machine transitions from NO_EMBARGO were fixed."
✅ "The embargo-consent state machine was corrected: participants can now accept or decline an embargo offer even when they are not currently party to one."

❌ "Production Collapses 1, 3, and 4 were completed."
✅ "Three fuzzer subsystems — the exploit-strategy evaluator, the suggest-actor notification loop, and the publication leaf — were converted from simplified simulation placeholders to full call-out abstractions ready for production backend wiring."

❌ "VFD role guards were added for f→F and d→D."
✅ "Role guards now ensure that only a vendor actor can mark a fix as developed, and only a deployer actor can mark it as deployed — previously these checks were absent."

❌ "FUZZ-08e retriever call-out points were implemented."
✅ "The actor-retrieval step in the multi-actor suggestion workflow was refactored to expose an injectable call-out point for custom retrieval backends."

---

## Theme Grouping Heuristics

Group changes by **what improved for users or developers**, not by
internal code location. Common groupings for Vultron:

| Theme label | What belongs here |
|---|---|
| Protocol automation | Behavior Tree automation, reduced manual steps |
| Multi-actor scenarios | Demo reliability, new scenarios, integration tests |
| API / architecture | New ports, facades, cleaned boundaries |
| Specification infrastructure | Spec format, lint, CI, machine-readability |
| Developer tooling / agents | Skills, history management, agentic workflow |
| Configuration | Config format, YAML migration, settings |
| Bug fixes | Reliability fixes, error handling |
| Documentation | Docs site, versioning, reference fixes |
| Dependencies | Automated dependency bumps (keep brief) |

---

## PR Link Format

Always link significant PRs inline:

```markdown
See [PR #NNN](https://github.com/CERTCC/Vultron/pull/NNN).
```

For dependency bumps, a single aggregate sentence is sufficient:

> 20+ automated dependency bumps were merged cleanly during the period,
> including updates to `pydantic`, `fastapi`, `uvicorn`, and `mypy`.

---

## Output Path and Filename

Reports live in `plan/history/<YYMM>/report/` where `YYMM` is derived from
the **end date** of the period (capped at today for open-ended periods):

```text
plan/history/<YYMM>/report/project-report-<YYYYMMDD>-<YYYYMMDD>.md
```

Examples:

├── implementation/         # Completed implementation tasks
├── priority/               # Completed priority groups
├── idea/                   # Ingested ideas
└── learning/               # Bug fixes, lessons learned, code reviews

`idea/` entries rarely need individual mention unless they drove major work.
