# Notes Index

`notes/` informs **work not yet done** (NF-08-001). It is not a history of the
project: when the work a note informs lands, the note is archived or its lasting
content moves to `docs/` or a `guidance` note. Read
`.agents/skills/shared/notes-writing-guide.md` before adding to any note.

Every note declares one `kind` in its frontmatter:

- `guidance`: a lasting rule or recurring procedure. Trimmed, not retired.
- `plan`: a design for work the code does not do yet. It lists the open issues it
  serves under `tracks:` and is archived when they close.
- `generated`: written by a tool. Change the generator, never the file.

Archived notes and sections live in `plan/history/YYMM/note/`, written by
`uv run append-history note` with source ID `NOTES-<file-stem>--<section-slug>`.

## How to use this index

Each entry gives the note's `kind`, a one-line summary, and a **Load when** line.
Read the **Load when** lines and pull only the notes that match your task; most
tasks need one to three. The frontmatter `description` of each note is the longer
summary; `uv run notes-tracks` lists plan notes whose tracked issues have all
closed.

Update this index in the same change that adds, archives, or re-scopes a note
(PD-03-004).

---

## Plan notes (temporary)

These describe unbuilt work. Each one ends when the issues it tracks close.

- **`call-out-simulation-plan.md`** · `plan`
  Personality bundles, a config surface for backends, and fuzzed multi-actor runs.
  **Load when**: designing a backend bundle, a backend config surface, or a fuzz demo.
- **`case-actor-cluster.md`** · `plan`
  A Raft-replicated CaseActor cluster for high-availability CASE_MANAGER writes.
  **Load when**: working on CASE_MANAGER availability or multi-node ledger writes.
- **`case-ledger-genesis-hardening.md`** · `plan`
  Closing the targeted-DoS gap of a computable genesis hash: nonce or manager key.
  **Load when**: changing how the per-case genesis hash is computed or verified.
- **`coordination-agents.md`** · `plan`
  Unbuilt capability-shape work: typed ports, latency budget, composites, Sentinel.
  **Load when**: designing a capability or call-out point, or routing a question to
  a capability, an ask, or a call-in monitor.
- **`cvd-recipe-injects.md`** · `plan`
  CERT Guide to CVD recipes classified as demo injects, by implementability tier.
  **Load when**: designing a failure-path demo or checking whether a recipe is tracked.
- **`demo-future-ideas.md`** · `plan`
  The planned-scenario register (DEMOCI-11-010) and unspecified scenario ideas.
  **Load when**: adding or retiring a planned demo scenario, or designing a new one.
- **`demo-interactive-ui.md`** · `plan`
  The React dashboard that watches live case ledgers over a prototype SSE stream.
  **Load when**: working on `ui/`, the ledger stream endpoint, or presentation demos.
- **`encryption.md`** · `plan`
  Exploratory options for message encryption on ActivityPub public-key infrastructure.
  **Load when**: designing encryption in the inbox or outbox pipeline (#1156).
- **`message-occasion-table.md`** · `plan`
  Remaining occasion-table design: derived "Sent by"/"Send to", "When…" grammar.
  **Load when**: extending the message occasion table or its generated fragments.
- **`ownership-transfer-close-paths.md`** · `plan`
  Closing a transfer Offer without an answer: owner withdrawal and answer deadlines.
  **Load when**: implementing transfer withdrawal or deadline expiry (CM-21).
- **`protocol-asks.md`** · `plan`
  The ask primitive: ask and terminate, conversation-state routing, ask registers.
  **Load when**: building a gate that needs another actor's answer, or an ask/reply
  exchange, ask expiry, or processing-fault notification.
- **`selective-disclosure.md`** · `plan`
  Referencing objects without inlining them, and explicit redaction of withheld fields.
  **Load when**: scoping privacy, redaction, or by-reference payload features.
- **`user-story-catalog.md`** · `plan`
  Personas, story identity, generated coverage, and working the protocol story gap.
  **Load when**: writing or citing a user story, or mapping a spec's `stories:` field.

---

## Guidance notes

### Architecture and layer boundaries

- **`architecture-hexagonal.md`** · `guidance`
  The core / wire / adapter layer model, its rules, and the review checklist.
  **Load when**: orienting to layer boundaries or reviewing a layering violation.
- **`architecture-adapters.md`** · `guidance`
  Driven-port activity construction, stub rules, store scope, uniform HTTP delivery.
  **Load when**: implementing an adapter or auditing the adapter/core boundary.
- **`wire-core-boundary.md`** · `guidance`
  Import direction, union-safe validators, `extra="forbid"`, and unknown inbound keys.
  **Load when**: touching core↔wire imports or validators, or deciding what happens to
  an unknown inbound key (MV-11).
- **`core-wire-rendering-port.md`** · `guidance`
  Why core needs wire-shaped JSON and the `WireRenderPort` seam that supplies it.
  **Load when**: touching `by_alias` or `alias_generator`, or building payload
  snapshots.
- **`domain-validation.md`** · `guidance`
  Loose-to-strict object boundaries, fail-fast helpers, and masked-invalid-state traps.
  **Load when**: writing error handling in a use case, BT node, or domain helper.
- **`lifecycle-staged-types.md`** · `guidance`
  When a lifecycle milestone earns its own type, and how to narrow to it (ADR-0033).
  **Load when**: deciding between a staged type and a predicate for a milestone.
- **`predicates-rule-layer.md`** · `guidance`
  What belongs in `vultron/core/predicates/`, its imports, and one-path invariants.
  **Load when**: placing a domain rule, or auditing a rule enforced on one path only.
- **`datalayer-design.md`** · `guidance`
  The DataLayer port contract, store scope, write/read shapes, and snapshots.
  **Load when**: working on a DataLayer adapter or deciding which store a write uses.
- **`actor-knowledge-model.md`** · `guidance`
  No cross-actor store access, the inline-object shortcut, and the actor-discovery seam.
  **Load when**: an actor needs data another actor holds, or reviewing AKM work.
- **`configuration.md`** · `guidance`
  YAML-backed Pydantic config: layering, key-presence checks, cache-safe tests.
  **Load when**: changing `vultron/config/` or a test that sets configuration.
- **`codebase-structure.md`** · `guidance`
  Module layout rules, module splits, and small recurring coding pitfalls.
  **Load when**: adding, moving, or splitting a module.
- **`structured-logging.md`** · `guidance`
  Log-call shape, correlation fields, the narrative template, and demotion rules.
  **Load when**: writing or reviewing any log call or log level.

### Wire format and messages

- **`activitystreams-semantics.md`** · `guidance`
  Activities as state-change statements, Accept/Reject object rules, rehydration.
  **Load when**: writing any inbound or outbound message handler.
- **`activitystreams-state-update.md`** · `guidance`
  Case state update paths, outbound naming and addressing, parsing traps.
  **Load when**: tracing a case-state divergence or an AS2 state-update path.
- **`activity-factories.md`** · `guidance`
  Design rules for the outbound activity factory layer.
  **Load when**: adding or changing an outbound activity factory.
- **`vocabulary-registry.md`** · `guidance`
  Auto-registration, the generated JSON-LD context, and disjoint registry keys.
  **Load when**: adding a vocabulary class or debugging a type-resolution failure.
- **`wire-artifact-immutability.md`** · `guidance`
  Received and emitted wire bodies are sealed evidence; delivery is a dumb relay.
  **Load when**: touching the inbox freeze point, a delivery port, or a sealed body.
- **`stub-objects.md`** · `guidance`
  The VulnerabilityCase stub, the only stub type the protocol permits.
  **Load when**: deciding whether an outbound object may be sent as a stub.
- **`message-type-reference.md`** · `guidance`
  Formal message shorthands versus AS2 wire forms, and the reference-page gates.
  **Load when**: claiming a shorthand maps to a wire form, or editing
  `docs/reference/messages/`.

### Behavior trees and use cases

- **`bt-integration.md`** · `guidance`
  Binding design decisions for BT-backed use cases, the lock, and received stages.
  **Load when**: building a BT-backed use case or deciding where a tree write belongs.
- **`bt-pitfalls.md`** · `guidance`
  Blackboard keys, failure reasons, idempotency, and refusal-arm rules.
  **Load when**: a tree returns an unexpected status, or writing a new node pattern.
- **`bt-canonical-reference.md`** · `guidance`
  Using the canonical CVD protocol tree: subtree map, legend, anti-patterns.
  **Load when**: locating where a new behavior fits in the canonical tree.
- **`bt-composability.md`** · `guidance`
  Define a subtree once and reuse it; BT idioms over procedural code.
  **Load when**: designing a subtree or refactoring near-duplicate nodes.
- **`bt-design-patterns.md`** · `guidance`
  Idiomatic BT construction patterns from Colledanchise and Ögren.
  **Load when**: writing new nodes or subtrees, or reviewing them for idiom.
- **`use-case-behavior-trees.md`** · `guidance`
  Domain logic lives in the tree, never in a use case's `execute()`.
  **Load when**: deciding whether logic goes in a use case or its tree.
- **`use-case-protocol.md`** · `guidance`
  Use-case results, handler dispositions, request paths, and the trigger contract.
  **Load when**: writing a use case or a trigger verb, or mapping a verdict to
  `InboxOutcome`.
- **`triggerable-behaviors.md`** · `guidance`
  Classifying trigger-tree nodes, capturing omitted side effects, placeholder seams.
  **Load when**: designing or changing a trigger behavior.
- **`triggers-test-coverage.md`** · `guidance`
  Test coverage and PR scope for trigger use cases.
  **Load when**: adding a trigger use case or scoping a PR across trigger modules.
- **`protocol-event-cascades.md`** · `guidance`
  Only primary events are triggered; every consequence is a subtree.
  **Load when**: deciding which downstream effects a handler must cause.
- **`event-driven-control-flow.md`** · `guidance`
  Gate on cause, not order; external decisions ask and terminate.
  **Load when**: a demo or use case seems to need a manual intermediate step.
- **`call-out-configuration.md`** · `guidance`
  Selecting call-out backends: the three modes, bundles, and gate defaults.
  **Load when**: wiring call-out backends in a tree builder, demo, or test.
- **`do-work-behaviors.md`** · `guidance`
  Which "do work" behaviors Vultron models and which it only records.
  **Load when**: scoping a new do-work behavior or its policy injection.
- **`peer-broadcast-failure-semantics.md`** · `guidance`
  Peer fan-out failure surfaces as FAILURE, with one narrow exception (BT-14-001).
  **Load when**: changing a broadcast path or its error behavior.

### Case model, ledger, and replication

- **`case-state-model.md`** · `guidance`
  Where the CS rules live, per-participant versus per-case dimensions, VF/D writes.
  **Load when**: working with case state machines or participant status transitions.
- **`status-dimension-objects.md`** · `guidance`
  The per-machine dimension objects on CaseStatus and ParticipantStatus (ADR-0036).
  **Load when**: changing a dimension object or SDO requirements.
- **`case-communication-model.md`** · `guidance`
  All participant messages route through the CASE_MANAGER; resolvers and relays.
  **Load when**: a participant sends a case-scoped message, or auditing addressing.
- **`case-joining.md`** · `guidance`
  Stub Invite, inert participant, full-case Invite, removal and reinstatement.
  **Load when**: touching invitations, participant creation, or recipient selection.
- **`case-proposal.md`** · `guidance`
  Who may answer a CaseProposal, admission invariants, native case initialization.
  **Load when**: changing the CaseProposal flow or the case-actor container.
- **`case-bootstrap-trust.md`** · `guidance`
  Establishing trust in a case and its CASE_MANAGER at a non-owner site.
  **Load when**: changing case bootstrap, trust anchors, or early-message queueing.
- **`case-ledger-authority.md`** · `guidance`
  Assertions versus admitted entries, what is ledgered, timestamps, genesis hash.
  **Load when**: adding a ledger entry kind or deciding whether a change is ledgered.
- **`case-ledger-parsing.md`** · `guidance`
  Reading case-ledger JSONL: every nesting layer, tolerant rows, per-case partition.
  **Load when**: writing any consumer of case-ledger JSONL.
- **`sync-ledger-replication.md`** · `guidance`
  Replicating the ledger: hash-chain sync, commit and replica invariants, buffers.
  **Load when**: changing ledger fan-out, replica ingest, or SYNC requirements.
- **`participant-case-replica.md`** · `guidance`
  One inbox per actor, the CASE_MANAGER as sole replica writer, late joiners.
  **Load when**: changing replica handling or PCR requirements.
- **`participant-role-management.md`** · `guidance`
  The CaseParticipant role API, participant lookup, and the RM terminal guard.
  **Load when**: changing participant roles or RM mutation on a participant.
- **`received-status-authorization.md`** · `guidance`
  How a CASE_MANAGER turns an inbound status claim into case state: two gates.
  **Load when**: changing received-side status handling or its gates.
- **`ownership-transfer.md`** · `guidance`
  Transfer Offer and Accept route through the CASE_MANAGER and the ledger (ADR-0053).
  **Load when**: changing ownership-transfer routing or its demo.

### Embargo

- **`embargo-lifecycle.md`** · `guidance`
  The embargo register, EmbargoLifecycle steps, guards, expiry, and the relay.
  **Load when**: any embargo state change, or reading EM state.
- **`embargo-default-semantics.md`** · `guidance`
  The creation-time default embargo: actor versus protocol default, once per case.
  **Load when**: changing default embargo initialization (EP-04).
- **`participant-embargo-consent.md`** · `guidance`
  Per-embargo consent rows: which writes move them and what is derived.
  **Load when**: writing any consent change, or reading signatory or lapsed state.

### Inbox, outbox, and delivery

- **`inbox-orchestration.md`** · `guidance`
  The core BT-backed inbox module, its adapter seam, and verdict mapping.
  **Load when**: changing `process_payload` or adding an inbound entry point.
- **`inbox-pipeline.md`** · `guidance`
  The dispatcher exception boundary and the `InboxPipeline` test seam.
  **Load when**: changing where unroutable errors are caught or re-queues bounded.
- **`outbox.md`** · `guidance`
  Outbox addressing enforcement, `handle_outbox_item`, and required test coverage.
  **Load when**: changing outbox delivery or adding an outbound activity type.
- **`outbox-delivery-reliability.md`** · `guidance`
  Per-pass caps, per-recipient lanes, finite retry budgets, and dead-lettering.
  **Load when**: changing delivery retries, locks, or dead-letter handling (OX-13).

### Demos and CI

- **`demo-scenario-authoring.md`** · `guidance`
  Writing a demo without faking the protocol: puppeteer via triggers, shared helpers.
  **Load when**: writing or reviewing a demo scenario or scenario helper.
- **`demo-scenario-registry.md`** · `guidance`
  The self-registering scenario registry, derived paths, generate-versus-check.
  **Load when**: adding a scenario or editing a scenario table or its generator.
- **`demo-scenario-tree.md`** · `plan`
  The scenario tree made explicit: path declarations, names, tree index, prefix check.
  **Load when**: declaring a scenario's path, renaming a scenario, or building the
  tree index.
- **`demo-ci-invariants.md`** · `guidance`
  The demo CI case-ledger invariant harness and its expected semantic types.
  **Load when**: changing the demo CI workflow or a scenario's expected events.
- **`demo-ci-diagnostics.md`** · `guidance`
  Runbook for a red Demo Integration run: log layers, invariant map, local repro.
  **Load when**: triaging a red Demo Integration or Invariant Harness job.
- **`demo-ci-scenario-coverage.md`** · `guidance`
  Which scenarios exercise which events, and the minimum PR validation set.
  **Load when**: choosing which scenarios run on PRs.
- **`ci-workflow-authoring.md`** · `guidance`
  GitHub Actions YAML traps, mandatory `notify-failure`, reading a red job.
  **Load when**: editing a `.github/workflows/` file or reading a CI failure.
- **`docker-build.md`** · `guidance`
  Which `.dockerignore` applies, runtime-stage paths, and slow-build triage.
  **Load when**: changing `docker/` files or the compose setup.

### Testing and developer tooling

- **`testing-pitfalls.md`** · `guidance`
  Pytest pitfalls here: killed runs, timeouts, markers, isolation, assertion traps.
  **Load when**: writing or debugging tests, or designing a ratchet baseline.
- **`flaky-tests.md`** · `guidance`
  Catalog of known flaky tests mapped to open issues, plus flakiness triage rules.
  **Load when**: triaging a test failure that may be pre-existing.
- **`architecture-ratchet-corpus.md`** · `guidance`
  The shared corpus behind `test/architecture/` ratchets, and baseline rules.
  **Load when**: adding or changing an architecture ratchet test.
- **`devcontainer-tooling.md`** · `guidance`
  `uv run`, cleared `PYTHONPATH`, bare `ruff`, hanging hooks, pushing to origin.
  **Load when**: a tool fails to start, `git push` fails, or editing a skill file.
- **`lint-tooling.md`** · `guidance`
  Ruff policy: bare-invocation gates, annotated `ignore` entries, `RUF100` baselines.
  **Load when**: changing ruff config, adding a `noqa` or ignore, or breaking an
  import cycle.
- **`git-workflow-pitfalls.md`** · `guidance`
  False rebase errors, catch-up merges, ADR number races, AC checks, red CI.
  **Load when**: syncing or merging a branch, claiming an issue, or opening a PR.
- **`parallel-development.md`** · `guidance`
  Multi-agent coordination: claiming, bundles, recovery, worktrees, Project #24.
  **Load when**: changing how work is claimed, bundled, or sized, or using
  Project #24 or worktree slots.

### Agent workflow and project history

- **`agentic-workflow.md`** · `guidance`
  The learnings queue, large fork migrations, affected sets, spec/code conflicts.
  **Load when**: writing a learning file, dispatching a large refactor, or finding a
  spec/code mismatch.
- **`agents-md-structure.md`** · `guidance`
  Where new agent guidance goes (root, per-directory AGENTS.md, notes) and budgets.
  **Load when**: adding a pitfall or rule to any AGENTS.md file.
- **`history-management.md`** · `guidance`
  Writing and reading `plan/history/` through `append-history` and `show-history`.
  **Load when**: archiving work, a learning, or a notes section, or reading history.

### Specs and decision records

- **`spec-authoring-rules.md`** · `guidance`
  Spec YAML mechanics: kinds and the MS-12 tree, enums, coverage guards, debt.
  **Load when**: writing or relabeling a spec item, or a spec-lint or coverage guard
  fails.
- **`specs-vs-adrs.md`** · `guidance`
  Spec, ADR, or both; ADRs as historical records (ADR-0127); ADR status rules.
  **Load when**: deciding where a decision goes, setting ADR status, or editing an ADR.
- **`behavioral-conformance-specs.md`** · `guidance`
  Authoring items in the behavioral conformance spec layer (RMB, EMB, CSB).
  **Load when**: editing `specs/rm-behavior.yaml`, `em-behavior.yaml`, or
  `cs-behavior.yaml`.
- **`rfc-spec-authoring.md`** · `guidance`
  Protocol Specification structure: page map, fragments, `full.md`, citations,
  normative text rendered from the YAML (callouts, Requirements Catalog).
  **Load when**: adding, moving, or splitting a section, annex, or open question in
  the specification, or writing a normative statement in it.
- **`rfc-review-rubric.md`** · `guidance`
  Ordered mechanical and judgment checks for reviewing the Protocol Specification.
  **Load when**: reviewing or revising a page or fragment under
  `docs/reference/vultron-spec/`.

### Documentation

- **`documentation-strategy.md`** · `guidance`
  Trust in doc generations, which behavior view to edit, MkDocs withholding rules.
  **Load when**: docs disagree with code, editing behavior docs, or changing
  `mkdocs.yml` or a docs gate.
- **`documentation-sweeps.md`** · `guidance`
  Moving a docs claim is not verifying it; share content by include fragment.
  **Load when**: moving, extracting, or republishing `docs/` content, or syncing a
  mirrored table.
- **`diataxis-framework.md`** · `guidance`
  The Diátaxis compass for classifying a page, and the docs authoring tooling.
  **Load when**: writing a `docs/` page or deciding which quadrant it belongs to.
- **`site-information-architecture.md`** · `guidance`
  Stakeholder types versus CVD roles, page levels, routing and landing pages.
  **Load when**: changing `docs/` structure, nav, page frontmatter, or landing pages.

---

## Generated notes

- **`site-coverage-matrix.md`** · `generated`
  Count of reader-facing pages per stakeholder type and level (DF-11-008).
  **Load when**: deciding which audience or depth the docs underserve. Regenerate
  with `uv run docs-site --write`.
