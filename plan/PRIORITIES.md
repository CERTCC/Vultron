# Priorities

## Important note about priority numbers

Priority numbers are ascending, so lower numbers are higher priority.
The scale is not linear, it's just intended to provide a rough ordering and
allow for space between to add new priorities in the future if needed. The
priority numbers themselves do not have any inherent meaning beyond their
relative order. Completed priorities should be archived via `uv run append-history priority`
(writes to `plan/history/YYMM/priority/`) and then removed from this file to keep
`plan/PRIORITIES.md` focused on pending and in-progress work.

## Priority 475: Participant Case Replica Safety

Enforce safety rules for seeding and maintaining local case replicas in
participant nodes, preventing unauthorized or out-of-order state
propagation, as specified in `specs/participant-case-replica.yaml`.

- [#440](https://github.com/CERTCC/Vultron/issues/440) — PCR: Implement
  participant case replica safety rules (PCR-03, PCR-05, PCR-06)

## Priority 476 — Epic #446: Bug Fixes and Demo Polish

Fix issues affecting demo execution and correctness.

- [#412](https://github.com/CERTCC/Vultron/issues/412) — mislabeled demo
  (docker-compose multi-vendor label mismatch)
- [#437](https://github.com/CERTCC/Vultron/issues/437) — Enforce spec vs.
  ADR delineation guidelines (MS-11)
- [#449](https://github.com/CERTCC/Vultron/issues/449) — Actor inbox
  endpoints return HTTP 404 during demo delivery
- [#450](https://github.com/CERTCC/Vultron/issues/450) — Outbound activities
  missing required `to:` field (OX-08-001 violation)
- [#451](https://github.com/CERTCC/Vultron/issues/451) — Invalid PEC state
  machine transition: `accept` trigger in NO_EMBARGO state
- [#452](https://github.com/CERTCC/Vultron/issues/452) — Demo times out
  waiting for case to propagate to finder DataLayer
- [#453](https://github.com/CERTCC/Vultron/issues/453) — Outbox processing
  aborts after too many `to:` field errors
- [#454](https://github.com/CERTCC/Vultron/issues/454) — Coordinator actor
  unexpectedly persists the authoritative case

## Priority 500: Re-implement "fuzzer" nodes from the original simulator

As we originally built out the `py_trees` implementation, we replaced
certain fuzzer nodes from the simulator (`vultron/bt`) with deterministic nodes
that simply
return success. While this initially allowed us to focus on the core
behavior tree logic, it also means that we are not able to demonstrate the
full range of behaviors that the Vultron Protocol is designed to support.
Re-implementing these nodes with more realistic behavior will be important for showcasing the
capabilities of the system and for moving towards a production-ready implementation.
The "fuzzer" implementation in the simulator worked well enough, so there is
not much need to change the overall design, but we will need to reimplement
it in the new codebase using `py_trees` as the foundation. The underlying
`vultron/bt/base/fuzzer.py` module (and all the other `fuzzer.py` modules in
`vultron/bt/`) can be used as a structural reference for the new implementation.

- [#427](https://github.com/CERTCC/Vultron/issues/427) — FUZZ-00:
  Re-implement fuzzer nodes from original simulator

## Priority 1000: Agentic AI readiness

We are going to want to allow for the possibility of agentic AI integration
into the vultron coordination process in the future. How this will happen is
still an open question. One possibility we can imagine coordination agents
that behave as ActivityPub Actors and participate in cases as CaseParticipants alongside
humans.

A more likely scenario is that we want to support agentic AI agents
interacting with cases as well on the
backend (i.e., not as ActivityPub Actors, but as API or command
line clients.) We may have local agents that interact directly with
the behavior trees or other internal system components via MCP. This would
be an adapter that parallels the API and CLI adapters in the hexagonal
architecture. These agents would not be ActivityPub Actors and would not
directly participate in cases, but would instead be more like assistants to human participants
who are directing them to perform specific tasks.

`AR-09-001` through `AR-09-004` and similar tasks will fall here.

- [#426](https://github.com/CERTCC/Vultron/issues/426) — AGENTIC-00:
  Agentic AI integration design and implementation

We will need to design the system in a way that allows for either of these
possibilities to be implemented in the future without requiring major refactoring.

## Priority 2000: Upgrade former "fuzzer" nodes to full implementations

See `notes/bt-fuzzer-nodes.md` for details on a set of fuzzer nodes that
were implemented as placeholders in the original simulator, but that
represent external touchpoints for the real process. Some of these nodes can
be fully automated, others will require outside judgment, human input, or
manual work. They might rely on external tools or services that we will need
to integrate with. Implementing these nodes will be important for moving
from a prototype to a production-ready system, but they also represent a
number of decisions and implementation work that is not core to being able
to demonstrate the core behavior tree and coordination logic.

- [#441](https://github.com/CERTCC/Vultron/issues/441) — Upgrade
  external-decision fuzzer nodes to full implementations

## Priority 3000: Miscellaneous tasks

- [#442](https://github.com/CERTCC/Vultron/issues/442) — Clean up orphaned
  BT-2.2/BT-2.3 placeholder references in PRIORITIES.md

## Priority 95000: Documentation Enhancements — Crosswalks and Framework Integration

Low-priority documentation work to expand coverage of related frameworks
and scoring systems. These will be addressed as part of a broader
documentation refresh, after higher-priority code and architecture work is
complete.

- [#5](https://github.com/CERTCC/Vultron/issues/5) — Integrate FIRST services frameworks
- [#6](https://github.com/CERTCC/Vultron/issues/6) — Add CVSSv4 crosswalk

## Priority 97000: MkDocs Replacement

Migrate documentation build tooling from MkDocs 1.x to Zensical (MkDocs 2.0
compatibility). MkDocs 2.0 is a ground-up rewrite that is incompatible with
the current plugin ecosystem and configuration format.

- [#294](https://github.com/CERTCC/Vultron/issues/294) — Plan migration to Zensical for MkDocs 2.0 compatibility

## Priority 99999 — Epic #447: Remaining Requirements and Documentation Updates

The project is currently in prototype development mode, therefore requirements
that are marked as `PROD_ONLY` are temporarily a lower priority than other
requirements. See `specs/prototype-shortcuts.yaml` for the prototype-stage
deferral policy.

- [#422](https://github.com/CERTCC/Vultron/issues/422) — USE-CASE-01:
  CloseCaseUseCase wire-type construction
- [#423](https://github.com/CERTCC/Vultron/issues/423) — USE-CASE-02:
  UseCase Protocol generic enforcement
- [#424](https://github.com/CERTCC/Vultron/issues/424) — EP-02/EP-03:
  EmbargoPolicy API + compatibility evaluation (PROD_ONLY)
- [#425](https://github.com/CERTCC/Vultron/issues/425) — AR-04/05/06:
  Job tracking, pagination, bulk ops (PROD_ONLY)
- [#426](https://github.com/CERTCC/Vultron/issues/426) — AGENTIC-00:
  Agentic AI integration (see also Priority 1000)
- [#427](https://github.com/CERTCC/Vultron/issues/427) — FUZZ-00:
  Fuzzer node re-implementation (see also Priority 500)
