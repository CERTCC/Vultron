# Design Insights and Implementation Notes

This directory captures **durable design insights** for the Vultron project.
Unlike `plan/IMPLEMENTATION_NOTES.md` (which is ephemeral and may be wiped),
files here are committed to version control and MUST be kept up to date as the
implementation evolves.

A new guidance document, **diataxis-framework.md**, provides documentation
standards adapted from the Diátaxis model (Tutorials, How‑to, Reference,
Explanation) and an implementation workflow for authoring technical docs.

## Contents

| File | Topics                                                                                                                                                                       |
|------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `activitystreams-semantics.md` | Activity model, state-change notification semantics, response conventions, vocabulary examples, case update path and CaseActor authoritativeness                                                               |
| `bt-fuzzer-nodes.md` | Behavior tree external touchpoints based on BT simulator fuzzing, commentary on automation potential                                                               |
| `bt-integration.md` | Behavior tree design decisions, py_trees patterns, simulation-to-prototype strategy                                                                                          |
| `case-state-model.md` | VFD/PXA case state hypercube, potential actions, measuring CVD quality, case object docs vs implementation, participant-specific vs participant-agnostic state distinction   |
| `codebase-structure.md` | Module reorganization candidates, enum refactoring, API layer architecture, code documentation strategy, demo script lifecycle logging (`demo_step`/`demo_check`)                                    |
| `diataxis-framework.md` | Diátaxis documentation framework: Tutorials, How‑to, Reference, Explanation, Compass, and implementation workflow                                                            |
| `documentation-strategy.md` | Docs chronology and trust levels, process models, formal protocol, behavior simulator reference, Do Work behaviors, ISO crosswalks                                           |
| `domain-model-separation.md` | Wire/Domain/Persistence layer separation, current coupling in `VulnerabilityCase`, per-actor DataLayer isolation options, architectural direction and recommended next steps |
| `do-work-behaviors.md` | Scope of "do work" BT behaviors: out-of-scope, not-implementable, partially-implementable items; reporting behavior notes; embargo policy prior art                          |
| `docker-build.md` | Project-specific Docker build observations, dependency layer caching, image content scoping, general build performance checklist                                             |
| `encryption.md` | Encryption implementation notes: public-key discovery, decryption placement, outgoing strategies, key rotation, and implementation guidance |
| `triggerable-behaviors.md` | Design notes for PRIORITY 30 triggerable behaviors: trigger scope, endpoint schema, candidate behaviors (RM/EM), relationship to actor independence; resolved design decisions on `RedactedVulnerabilityCase`, per-participant embargo acceptance, and `reject-report` note requirement |

## Conventions

- Each file focuses on a specific topic area.
- Write insights as **durable guidance for future agents** (not status
  reports).
- When a lesson is learned during implementation, add it here (not just in
  `plan/IMPLEMENTATION_NOTES.md`).
- Cross-reference from `AGENTS.md` where relevant.

## Relationship to plan/IMPLEMENTATION_NOTES.md

`plan/IMPLEMENTATION_NOTES.md` is **ephemeral** — it is wiped periodically to
keep it focused on current work. **Do not reference it from `AGENTS.md`.**

When updating `AGENTS.md`:

- Pull durable technical guidance from `notes/` (this directory), not from
  `plan/IMPLEMENTATION_NOTES.md`.
- If `plan/IMPLEMENTATION_NOTES.md` contains insights worth preserving, move
  them here first, then reference `notes/` from `AGENTS.md`.
