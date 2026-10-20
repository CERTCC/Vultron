---
title: Interactive Demo UI — Scenarios and Architecture
status: active
kind: plan
tracks:
  - "#676"
  - "#3642"
  - "#3643"
  - "#3901"
  - "#4723"
  - "#4726"
  - "#4730"
  - "#4733"
  - "#4759"
description: >
  Design for the Vultron interactive demo UI: a React dashboard for stakeholder
  presentations that shows only what the real system did. Live, it watches each
  actor's case ledger over a prototype-only SSE stream; offline, it replays a
  recorded scenario tree regenerated deterministically from the real scenario
  code. The presenter walks the tree's authored choices in both modes. Records
  the interface contract between ui/ and the Python code, the 2026-10-15 gap
  analysis of the merged UI, and the Task sequence under epic #676.
related_notes:
  - notes/demo-future-ideas.md
  - notes/demo-scenario-registry.md
  - notes/demo-scenario-tree.md
  - notes/demo-scenario-authoring.md
  - notes/case-ledger-authority.md
  - notes/configuration.md
related_specs:
  - specs/multi-actor-demo.yaml
  - specs/triggerable-behaviors.yaml
  - specs/demo-report.yaml
  - specs/demo-ci.yaml
  - specs/semantic-extraction.yaml
  - specs/case-ledger-processing.yaml
relevant_packages:
  - ui
  - vultron/demo/scenario
  - vultron/metadata/demo_scenarios
  - vultron/semantic_registry
  - vultron/adapters/driving/fastapi/routers
  - vultron/adapters/driving/fastapi/ledger_stream.py
---

# Interactive Demo UI — Scenarios and Architecture

Decision records: ADR-0104 (the demo UI, amended 2026-10-15), ADR-0098 (scenarios
self-register, amended 2026-10-15 for the scenario tree), and ADR-0140 (a ledger
entry's semantic type is the registry label of its AS2 payload).
Vocabulary: the **Demo** section of `CONTEXT.md` (scenario tree, branch point,
choice, ending, scenario, recording).

This is presentation tooling, not protocol work. It generates no `specs/`
requirements of its own; everything below is design guidance.

---

## Purpose

The goal of the interactive demo UI is to make Vultron's CVD protocol
behavior legible and compelling to non-technical stakeholders — primarily
government funders and program managers, then industry practitioners
(vendors, coordinators, CNA staff). Watching Python logs scroll by
convinces developers; it does nothing for funders. The UI replaces logs
with a live, interactive visualization of protocol state and message
exchange that tells a story.

### Target audiences (in priority order)

1. **Government funders / program managers** — Does this work? Is it
   worth continued investment?
2. **Industry security teams** (vendors, coordinators, CNA staff) — Does
   this fit into real CVD workflows? Would I use it?
3. **Policy researchers / academics** — Is the protocol formally correct?
   (This group requires the most polish; they come after 1 and 2 have
   bought in.)

---

## Decisions

1. **Vehicle: the React app in `ui/`.** It landed from `feature/demo-ui` in
   PR #3754. The timeline is drawn as SVG; the UI does not use ReactFlow.
2. **The audience sees only what Vultron did.** Live mode reads the running
   system's ledgers. Offline mode replays **recordings**: the case ledgers each
   scenario writes, produced by running the real scenario code
   deterministically and drift-tested against a fresh run. Neither mode
   invents protocol state; the whole UI holds to this once the TypeScript
   simulation is deleted (#4732, decision 5).
3. **The scenarios form one scenario tree.** Its root is a Reporter who has
   found a vul and must choose whom to tell. Each branch point is a role
   facing a decision; each choice is a trigger that role calls. Who joins and
   how a decision goes are both branch points.
4. **A choose-your-own-adventure story, not an open-world simulation.** The
   presenter plays the roles, but only the tree's authored choices are
   offered, offline and live alike. An off-tree "sandbox" mode is future
   work.
5. **The TypeScript simulation is temporary.** The Multi-Vendor mode
   re-implements protocol rules in TypeScript and stays the default only
   until the recorded scenario tree covers its branch points; then it is
   deleted (#4732). It receives no new protocol logic meanwhile.
6. **The dashboard is operator-side, with no case identity.** It reads each
   actor's prototype-only ledger stream; it is never a case participant,
   never appears in a roster, and never changes the case being demonstrated.
   It is the watching half of a **Sentinel** (a call-in pattern, ADR-0097 —
   not a capability shape); it becomes a full Sentinel once branch-point
   choices call trigger endpoints.
7. **Transport: server-sent events of case ledger entries, polled
   server-side.** One direction of flow only (choices go out as ordinary
   trigger POSTs), so SSE rather than a WebSocket. The stream is justified
   on its own observability merits (`curl -N` tailing), independent of the
   UI.
8. **Quality bar: sized to the risk.** Test what could show the audience
   something Vultron did not do — ledger parsing and mapping, tree walking,
   and every generated artifact the UI reads. Rendering and layout are
   checked by eye.

---

## Interface Contract between `ui/` and Python

Every protocol fact the UI uses comes from Python as a generated, committed,
drift-tested artifact (ADR-0128's rule), never as a hand-kept TypeScript copy.
Nothing in `vultron/` imports `ui/`; the only dependency runs from the
exporters to the files they write.

| Seam | Producer | Consumer | Guard | Status |
|---|---|---|---|---|
| State machines (`ui/src/data/protocol_states.json`) | `uv run export-demo-states` | `ui/src/protocol.ts` | drift test in `test/metadata/demo_scenarios/` | built (EM read from the EM transition table since #4427) |
| Semantic registry table | registry exporter (#4725) | ledger parser and mapper | drift test | planned |
| Recordings | deterministic in-process scenario runner (#3901) | Log Replay, offline mode | byte-identical drift test; `CaseLedgerEntry` validation | planned |
| Scenario-tree index | branch-point table and `@scenario` path declarations (#4727; design in `demo-scenario-tree.md`) | offline mode, live branch points | drift test; isomorphic shared-prefix check | planned |
| Live ledger stream | `GET /api/v2/actors/{id}/demo/cases/{case_id}/log/stream` | live mode (#3642) | stream integration tests | server built (#3641); client planned |
| Branch-point choices | trigger endpoints (`/actors/{id}/trigger/{behavior}` and `/actors/{id}/demo/{behavior}`) | live mode (#3643) | — | planned |

Rules for the TypeScript side:

- A ledger entry's meaning is its `semanticType`, which equals the registry's
  semantic type for its AS2 payload (ADR-0140). The UI reads the exported
  registry table; it never keeps its own list of event names or phrasing.
- TypeScript types for anything the UI reads match the current Python models,
  and a Python test fails when a field the TypeScript side declares is gone.
- Loading a ledger validates its shape. An unrecognized semantic type is shown
  as such, never dropped silently.
- Lane identity comes from actor ids and roles in the ledger, never from
  container hostnames or display names.

---

## Architecture

### Data path

```text
actor container (reporter, vendor, coordinator, …; may host several actors)
  └─ GET /api/v2/actors/{id}/demo/cases/{case_id}/log/stream   (SSE, prototype-only)
        ▲  one stream per actor — each shows that actor's replica
        │
  ui compose service: serves built ui/ and reverse-proxies /<service>/…
        ▲
  browser (EventSource per actor)  ──POST trigger──▶  actor the presenter plays
```

- **Reverse proxy, not CORS.** Actor containers publish ephemeral host ports
  and the server has no CORS middleware. The UI's compose service serves
  the built app and proxies each actor under one origin, so the Vultron
  server needs no change.
- **One stream per actor, not per container.** A container can host several
  actors, each with its own store. The canonical case and ledger live in the
  dedicated `case-actor` container; each participant container holds its
  replica. Live mode picks its streams the way the report tool picks its
  ledgers — the `LedgerDumpTarget` list each scenario module builds
  (`vultron/demo/helpers/ledger_dump.py`) — so it never misses the case
  manager's authoritative ledger.
- **Per-replica view.** Because the dashboard reads every actor, it can
  show replica convergence side by side — the same per-actor presence view
  `vultron/demo/report.py` builds after the fact (DRPT-02-005).

### Live case log stream

The stream is built (#3641): `GET
/api/v2/actors/{actor_id}/demo/cases/{case_id}/log/stream`, prototype-only
(TRIG-09), in `vultron/adapters/driving/fastapi/routers/demo_triggers.py` and
`vultron/adapters/driving/fastapi/ledger_stream.py`. Each event's `id:` is the
entry's `log_index`, `?since=` or `Last-Event-ID` resumes, and the stream is
demo tooling, not a replication channel (SYNC-02-001).

---

## Choose-Your-Own-Adventure (CYOA) Model

The human viewer "plays" one or more actors, making real protocol decisions
at key branch points. The human is explicitly assigned a role at each
decision: **"As the Vendor, choose one of the following..."** Choices POST to
the same trigger endpoints the Python demo scripts use
(`POST /actors/{id}/trigger/{behavior}`, `POST /actors/{id}/demo/{behavior}`);
the UI then animates from the ledger entries that result. It never invents
state client-side.

### Branch points (in priority order)

1. **Report validation** — As the Vendor: validate / invalidate-hold /
   invalidate-close. *First to build, on the `rv` path.*
2. **Embargo negotiation** — As the Reporter or Vendor: accept the proposed
   embargo / reject / counter-propose different terms
3. **Publication** — As any participant: publish on the agreed date /
   announce early publication / request embargo extension
4. **Embargo collapse** — As participants: re-negotiate / agree to
   accelerate
5. **Case ownership transfer** — As the Vendor: retain ownership / offer to
   a Coordinator

The full set of branch points corresponds to the protocol decision nodes the
original Vultron simulator exposed via fuzzer BT nodes; any place a demo
script calls a trigger that advances protocol state is a candidate.

### Presentation paths

The earlier three-presentation set maps onto paths through the scenario tree.
All share one UI; only the number of actor lanes differs.

| Presentation | Narrative | Path today |
|---|---|---|
| A — Two-Actor | Reporter reports directly to a single vendor | `rv` |
| B — Coordinator | Reporter routes through a neutral coordinator | `rcv` |
| C — Multi-Vendor | A shared component's vendor set expands | `rvv`, `rvcv-*`, `rcvcv` |

### Scripted baseline

The Python demo scripts remain **automated puppeteers** that take the
happy-path branch at every decision. A presenter can run a script while the
audience watches the UI animate — this is the first live milestone, before
any branch point is interactive.

---

## Layout and Actor Scorecards

```text
┌─────────────────────────────────────────────────────────┐
│  VULTRON DEMO   [Branch: rv ▸]   [Reset]   [Run Auto]   │
│  CERT/CC — Research Prototype                           │
├─────────────────────────────────────────────────────────┤
│  [Reporter] ──msgs──> [Vendor] ──msgs──> [CASE_MANAGER] │
│   scorecard            scorecard            scorecard   │
├─────────────────────────────────────────────────────────┤
│  Message Timeline (newest at top, history grows down)   │
└─────────────────────────────────────────────────────────┘
```

- **Top**: actor network graph with animated message edges; each actor
  node carries a scorecard.
- **Bottom**: vertical swimlane timeline, newest at top — sender → receiver,
  activity type, human-readable description.
- **Landing page**: the scenario tree's root branch point (the Reporter
  choosing whom to tell), with CERT/CC branding and a
  "Research Prototype — Not for Production Use" disclaimer.
- **Scorecard**: LED-style RM / EM / CS indicators (raw labels such as
  `RM.V` on hover, not primary), a plain-language narrative label
  ("Embargo active", "Waiting for vendor response"), and role badges
  (REPORTER, VENDOR, COORDINATOR, CASE_MANAGER).

---

## Gap Analysis of the Merged UI (2026-10-15)

An audit of PR #3754 on `main` covered test coverage, internal architecture,
and the interface to Python. Findings and where each went:

| Gap | Where it went |
|---|---|
| The ledger had no contract: free-form event names, scattered literals, a closed TypeScript list that had drifted | ADR-0140; #4723, #4724, #4725 |
| The parser read removed fields (`vfdState`, `emConsentState`) and missed current semantic types, hidden by tolerant parsing | #4729 |
| The bundled sample ledgers predated the current `CaseLedgerEntry`, and nothing regenerated or checked them | #3901 |
| The simulation, the default mode, showed embargo acceptance as a unanimous vote, and activity names Vultron does not have | #4730, #4731, #4732 |
| No UI tests, no strict typing, CI path filters that missed changes on the other side of the seam | #4728, #4729 |
| The two app modes shared little and duplicated their layout and controls | removed with the simulation (#4732) |
| Dead code (`protocolActions.ts`, unused components, the ReactFlow dependency, scaffold assets) and stale paths | #4728 |
| CaseActor used for CASE_MANAGER (ADR-0088); Finder used for Reporter (ADR-0078) | #4728, #4736 |
| Sibling scenarios are full copies up to the point where they differ | #4726, #4733 |
| A ledger payload used a non-AS2 activity type (`Expire`) | #4723 |

What was already solid: the state-machine export is generated, committed,
drift-tested, and in sync; the layering is clean; the simulation freeze held.

---

## Task Sequence (epic #676)

Design Ideas and Concerns come first and are decided interactively; the Tasks
they block wait for them.

1. **Vocabulary.** Concern #4723 (AS2 shapes for ledger-only acts) →
   #4724 (the registry labels every ledger entry) → #4725 (export the registry
   table to `ui/`).
2. **Recordings and the tree.** Idea #4726 (scenario-tree design) → #4736
   (Finder → Reporter) → #4759 (path declarations) → #4727 (tree index and
   shared-prefix check, also after #3901, deterministic recordings); Idea #4733
   (scenarios as composition) after #4727, producing one Task per scenario
   family.
3. **UI correctness.** #4728 (tooling baseline) → #4729 (Log Replay reads the
   current ledger, golden tests over the recordings).
4. **Offline mode.** Idea #4730 (presentation design) → #4731 (offline
   choose-your-own-adventure mode) → #4732 (delete the simulation).
5. **Live mode.** #3642 (watch a running scenario) after #4729 → #3643
   (branch points through real triggers) after #4727 and #4730.

Independent follow-up: #4735 (log "no use case found" at WARNING).

---

## Open Questions / Future Work

- **Sandbox mode**: an off-tree mode offering every action the protocol
  allows. It would need either protocol rules in the client or a server
  endpoint listing the triggers a role may call; both need their own design.
- **State machine visualization**: LED-style indicators need a visual design
  pass; the SVG state diagrams in the Vultron docs are a candidate base.
- **Container startup**: whether "Start Demo" spins up containers or assumes
  they are already running.
- **Accessibility**: the timeline must be usable by viewers who cannot read
  color-coded state indicators.
- **Later branches**: failure-mode endings (embargo collapse, vendor decline,
  reporter going silent) become new branch points in the scenario tree.
