# Archived Notes

This directory holds notes files that have been archived from `notes/` because
they are either fully superseded, describe completed implementation tasks, or
are session-log artefacts rather than durable design insights.

**Do not load these files as routine context.** They are kept for historical
reference only. Any open items were rescued to `plan/IMPLEMENTATION_PLAN.md`
before archiving.

---

## Archived Files

| File | Archived   | Reason | Rescued items |
|------|------------|--------|---------------|
| `architecture-review.md` | 2026-04-10 | All V-01–V-24 violations fully resolved; "What Is Already Clean" section migrated to `notes/architecture-ports-and-adapters.md` (Compliance Reference appendix) | None — compliance reference preserved in active notes |
| `codebase-structure-history.md` | 2026-04-10 | Completed/superseded sections stripped from `notes/codebase-structure.md`: API layer architecture (VCR Batch B), use-case module structure (REORG-1), vocabulary examples (P60-1), TECHDEBT-12 (resolved), outbox delivery (OX-1.0–1.4), `app.py` root logger fix (BUGFIX-1.1), trigger services package (VCR Batch D) | None — all tasks completed |
| `datalayer-refactor.md` | 2026-04-10 | TECHDEBT-32 task log; 32a and 32b completed; only 32c remained open | **TECHDEBT-32c** rescued to `plan/IMPLEMENTATION_PLAN.md` (PRIORITY-350 section): remove `from vultron.adapters.driven.datalayer_tinydb import get_datalayer` from `vultron/wire/as2/rehydration.py` |
| `multi-actor-architecture.md` | 2026-04-10 | Pre-D5-2 planning document; D5-2 is fully implemented and complete | None — all tasks completed |
| `spec-review-0327.md` | 2026-04-10 | Session log from a 2026-03-27 spec review; not a durable design insight; action items belonged in `plan/` or `specs/` | None — session artefact only |
| `state-machine-findings.md` | 2026-04-10 | Header explicitly states "Refactoring complete — all P and OPP items addressed"; all ADR-0013 follow-up opportunities resolved | None — all tasks completed |
| `two-actor-feedback.md` | 2026-04-10 | Bug-tracking log from the two-actor demo; all bugs resolved except two demo improvement items | **D5-7-DEMONOTECLEAN-1** and **D5-7-DEMOREPLCHECK-1** rescued to `plan/IMPLEMENTATION_PLAN.md` (already present) |
| `datalayer-sqlite-design.md` | 2026-04-17 | Pre-implementation design doc for PRIORITY-325 (TinyDB → SQLite migration); migration is complete | None — all tasks completed |
| `protocol-event-cascade-gaps.md` | 2026-04-17 | "Identified Gaps" (D5-6-AUTOENG, D5-6-NOTECAST, D5-6-EMBARGORCP, D5-6-CASEPROP) and "Anti-Pattern" sections extracted from `notes/protocol-event-cascades.md`; all gaps resolved (PRIORITY-310, PRIORITY-320, PRIORITY-330) | None — all tasks completed |
| `wire-trans-design.md` | 2026-04-17 | "Current Status" and "Recommended Next Steps" sections extracted from `notes/domain-model-separation.md`; WIRE-TRANS-01–05 fully complete (PRIORITY-340) | None — all tasks completed |
| `priority-30-design.md` | 2026-04-17 | "Open Design Questions" and "Candidate Behaviors for PRIORITY 30" sections extracted from `notes/triggerable-behaviors.md`; all 10 trigger endpoints implemented (PRIORITY-30) | None — all tasks completed |

---

## How this directory is maintained

- Files are moved here using `git mv` so history is preserved.
- When archiving, open items MUST be rescued to `plan/IMPLEMENTATION_PLAN.md`
  before the file is moved.
- This README MUST be updated whenever a file is moved here.
- See `specs/project-documentation.md` for the full maintenance policy.
