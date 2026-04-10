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
| `architecture-ports-and-adapters.md` | Hexagonal architecture (Ports and Adapters) spec: layer model (inbound/outbound), adapter categories (driving/driven/connector/wire), file layout proposal, code patterns, architectural rules (Rules 1–8), dispatch/emit terminology, core model richness principle, adapter category discipline, review checklist |
| `architecture-review.md` | Adherence review against `architecture-ports-and-adapters.md`: identified violations (V-01 to V-24), remediation plan (R-01 to R-11), TECHDEBT-13 items, and what is already clean |
| `bt-fuzzer-nodes.md` | Behavior tree external touchpoints based on BT simulator fuzzing, commentary on automation potential                                                               |
| `bt-integration.md` | Behavior tree design decisions, py_trees patterns, simulation-to-prototype strategy                                                                                          |
| `case-log-authority.md` | Assertion recording model for report/proto-case/case flows: implicit participant assertions, CaseActor-authored `CaseLogEntry`, local audit log vs replicated canonical chain, and rejection handling |
| `case-state-model.md` | VFD/PXA case state hypercube, potential actions, measuring CVD quality, case object docs vs implementation, participant-specific vs participant-agnostic state distinction; CaseStatus/ParticipantStatus append-only history; CaseEvent model for trusted timestamps (SC-PRE-1); actor-to-participant index design (SC-PRE-2); report-as-proto-case redefined (caterpillar = RM.RECEIVED/INVALID stage; butterfly = RM.VALID/ACCEPTED/DEFERRED; FINDER-PART-1 superseded by ADR-0015); pre-case event backfill design; multi-vendor case state action rule considerations |
| `codebase-structure.md` | Module reorganization candidates, enum refactoring, splitting `vultron_types.py` into individual modules (TECHDEBT-14), `CVDRoles` StrEnum design decision, API layer architecture, code documentation strategy, demo script lifecycle logging (`demo_step`/`demo_check`), technical debt items (TECHDEBT-11–14), `docker/README.md` out of date, inline code blocks in `docs/` needing module path updates |
| `demo-future-ideas.md` | Extended multi-actor demo scenarios: Two-Actor (Finder + Vendor), Three-Actor (Finder + Vendor + Coordinator), and MultiParty (ownership transfer + expanded participants) |
| `diataxis-framework.md` | Diátaxis documentation framework: Tutorials, How‑to, Reference, Explanation, Compass, and implementation workflow                                                            |
| `documentation-strategy.md` | Docs chronology and trust levels, process models, formal protocol, behavior simulator reference, Do Work behaviors, ISO crosswalks                                           |
| `domain-model-separation.md` | Wire/Domain/Persistence layer separation; current coupling in `VulnerabilityCase`; per-actor DataLayer isolation options (including MongoDB production path); `FooActivity` vs `FooEvent` naming convention; discriminated domain event hierarchy design; outbound event design questions; DRY core models (`vultron_types` + `events`); post-P75-2 architecture findings; wire-layer mutation helpers that belong in core; vocabulary-registry and DataLayer coupling; architectural direction and recommended next steps |
| `do-work-behaviors.md` | Scope of "do work" BT behaviors: out-of-scope, not-implementable, partially-implementable items; reporting behavior notes; embargo policy prior art; future VulnerabilityDisclosurePolicy wrapper concept |
| `docker-build.md` | Project-specific Docker build observations, dependency layer caching, image content scoping, general build performance checklist                                             |
| `encryption.md` | Encryption implementation notes: public-key discovery, decryption placement, outgoing strategies, key rotation, and implementation guidance |
| `federation_ideas.md` | Federation design: AS2 as vocabulary (not full ActivityPub), actor/inbox/outbox model, case object model, ownership, relay pattern, journal vs. delivery log, mirror consistency, instance trust, peering handshake, delivery architecture, connector plugins, open questions |
| `state-machine-findings.md` | RM/EM/CS transition findings, ADR-0013 follow-up opportunities (OPP-06/07/09), and `transitions` integration guidance for Pydantic-backed state |
| `multi-actor-architecture.md` | Pre-D5-2 architectural review: CA-2 follow-up confirmation, current architecture state, per-actor isolation model, outbound delivery pipeline, CaseActor design, assumptions and gaps for isolated actor/container scenarios, recommended D5-2 prerequisites |
| `sync-log-replication.md` | Log-centric architecture overview, hash-chain design rationale, log position in activity context, implementation phases (SYNC-1–4), system invariants, and open questions for the replicated case event log |
| `protocol-event-cascades.md` | Cascading automation design principle: primary events vs cascading consequences, identified gaps in BT automation and activity addressing (invitation acceptance, note broadcast, embargo announce, case propagation), relationship to demo correctness |
| `triggerable-behaviors.md` | Design notes for PRIORITY 30 triggerable behaviors: trigger scope, endpoint schema, candidate behaviors (RM/EM), relationship to actor independence; resolved design decisions on `RedactedVulnerabilityCase`, per-participant embargo acceptance, and `reject-report` note requirement |
| `use-case-behavior-trees.md` | Relationship between use cases, domain logic, and behavior trees; proposed module layout; conceptual layering (Driver → Dispatcher → Use Case → BT → Domain Model); protocol activity-to-use-case mapping; standardized `UseCase` protocol proposal; SEMANTICS_HANDLERS migration to core |
| `vocabulary-registry.md` | Vocabulary registry design (VOCAB-REG-1): `__init_subclass__` auto-registration, flat dict structure, `VocabNamespace` enum as metadata, `Literal` type_ heuristic for concrete/abstract detection, dynamic discovery as startup guarantee, migration path (VOCAB-REG-1.1 / 1.2) |

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
