---
title: Interactive Demo UI — Scenarios and Architecture
status: active
kind: plan
tracks:
  - "#676"
  - "#3640"
  - "#3642"
  - "#3643"
description: >
  Design for the Vultron interactive demo UI: a React/ReactFlow dashboard for
  stakeholder presentations that watches the real system's case ledgers live
  over a prototype-only SSE stream, operator-side with no case identity, with
  branch-point choices driven through the real trigger endpoints. Records the
  feature/demo-ui prior art and the remaining Tasks under epic #676.
related_notes:
  - notes/demo-future-ideas.md
  - notes/demo-scenario-registry.md
  - notes/case-ledger-authority.md
  - notes/configuration.md
related_specs:
  - specs/multi-actor-demo.yaml
  - specs/triggerable-behaviors.yaml
  - specs/demo-report.yaml
relevant_packages:
  - vultron/demo/scenario
  - vultron/adapters/driving/fastapi/routers
  - vultron/adapters/driving/fastapi/ledger_stream.py
---

# Interactive Demo UI — Scenarios and Architecture

Decision record: ADR-0104.

This is presentation tooling, not protocol work. It generates no `specs/`
requirements; everything below is design guidance.

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

1. **Vehicle: the React/ReactFlow app on `feature/demo-ui`.** The lighter
   alternatives (a self-contained HTML live page reusing
   `vultron/demo/report.py`, or presenting the static report after the
   fact) were considered and rejected: the prior art already exists and is
   the more compelling presentation artifact.
2. **Backbone: the real system, live.** The headline mode is the branch's
   *Log Replay* mode grown into a live view of a running scenario. What the
   audience sees is what the containers actually did.
3. **The TypeScript simulation is frozen.** The branch's client-side
   *Multi-Vendor* mode re-implements protocol rules in TypeScript. It stays
   as an offline, explicitly *illustrative* mode, but receives no new
   protocol logic — a second protocol implementation drifts silently, and an
   audience watching it is not watching Vultron.
4. **The dashboard is operator-side, with no case identity.** It reads each
   actor's prototype-only ledger stream; it is never a case
   participant, never appears in a roster, and never changes the case being
   demonstrated. It is the watching half of a **Sentinel** (a call-in
   pattern, ADR-0097 — not a capability shape); it becomes a full Sentinel
   once branch-point choices call trigger endpoints. The rejected
   alternative — an Observer participant receiving `Announce(CaseLedgerEntry)`
   — would alter every scenario's roster and see only what it is sent.
5. **Transport: server-sent events of case ledger entries, polled
   server-side.** One direction of flow only (choices go out as ordinary
   trigger POSTs), so SSE rather than a WebSocket. The stream is justified
   on its own observability merits (`curl -N` tailing during debugging and
   CI), independent of the UI.
6. **The UI Tasks wait for the branch to land** (#3640).

---

## Prior Art — `origin/feature/demo-ui`

About 16k lines:

- **`ui/`** — React 19 + TypeScript + Vite + `@xyflow/react` (ReactFlow).
  `DemoSelector.tsx` toggles two modes:
  - **Multi-Vendor** (`App-multivendor.tsx`, `ui/src/actions/*.ts`) —
    client-side CYOA simulation; Finder, up to two extra vendors, Case
    Actor; decision and consequence nodes in per-participant swimlanes;
    external-event buttons for exploit publication and attacks.
  - **Log Replay** (`App-logreplay.tsx`, `ui/src/utils/caseLedgerParser.ts`,
    `caseLedgerMapper.ts`) — loads case-ledger JSONL by file upload or from
    bundled samples (`ui/src/sample-logs/`) and renders it with the same
    swimlane components (`ActorPanel`, `AnimatedNode`, `Swimlanes`).
- **`vultron/scripts/export_states.py`** → `data/json/protocol_states.json`
  (deterministic export of the RM/EM/VFD/PXA machines from their
  `create_*_machine()` factories) plus `test/test_demo_states_export.py`
  as a drift test, so the UI does not hard-code which transitions exist.
- **No network code**: no `fetch`, `EventSource`, or `WebSocket`. Live mode
  is the missing piece.
- **Housekeeping before landing**: file-mode flips on several `.sh`
  scripts, a deleted `docs/reference/codebase/.codebase-scan.txt`, and
  stale `ui/LOG_REPLAY_README.md` content (old `case-log.jsonl` file names
  and event types). Several files are very large (`caseLedgerMapper.ts`,
  `vendorActions.ts`).

---

## Architecture

### Data path

```text
actor container (finder, vendor, coordinator, …; may host several actors)
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

## Three-Scenario Presentation Set

All presentation scenarios share one UI; only the number of actor lanes
differs. They map onto registered demo scenarios (`vultron-demo` sub-commands,
ADR-0098). The UI takes its lanes and streams from the scenario's ledger
targets (see *One stream per actor* above), not from a fixed container
layout.

| Presentation | Narrative | Closest registered scenario |
|---|---|---|
| A — Two-Actor | Researcher reports a bug directly to a single vendor | `fv` |
| B — Coordinator | Reporter routes through a neutral coordinator for a widely-used library | `fcv` |
| C — Multi-Vendor | Shared component used by several vendors; the vendor set expands | `fvv`, `fvcv-*`, `fcvcv` |

---

## Choose-Your-Own-Adventure (CYOA) Model

The human viewer "plays" one or more actors, making real protocol decisions
at key branch points. The human is explicitly assigned a role at each
decision: **"As the Vendor, choose one of the following..."** Choices POST to
the same trigger endpoints the Python demo scripts use
(`POST /actors/{id}/trigger/{behavior}`, `POST /actors/{id}/demo/{behavior}`);
the UI then animates from the ledger entries that result. It never invents
state client-side in the live mode.

### Branch points (in priority order)

1. **Report validation** — As the Vendor: validate / invalidate-hold /
   invalidate-close. *First to build, on scenario A.*
2. **Embargo negotiation** — As the Finder or Vendor: accept the proposed
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

### Scripted baseline

The Python demo scripts remain **automated puppeteers** that take the
happy-path branch at every decision. A presenter can run a script while the
audience watches the UI animate — this is the first live milestone, before
any branch point is interactive.

---

## Layout and Actor Scorecards

```text
┌─────────────────────────────────────────────────────────┐
│  VULTRON DEMO   [Scenario A ▼]   [Reset]   [Run Auto]   │
│  CERT/CC — Research Prototype                           │
├─────────────────────────────────────────────────────────┤
│   [Finder]  ──msgs──>  [Vendor]  ──msgs──>  [Case Actor]│
│   scorecard            scorecard            scorecard   │
├─────────────────────────────────────────────────────────┤
│  Message Timeline (newest at top, history grows down)   │
└─────────────────────────────────────────────────────────┘
```

- **Top**: actor network graph with animated message edges; each actor
  node carries a scorecard.
- **Bottom**: vertical swimlane timeline, newest at top — sender → receiver,
  activity type, human-readable description.
- **Landing page**: scenario selector with CERT/CC branding and a
  "Research Prototype — Not for Production Use" disclaimer.
- **Scorecard**: LED-style RM / EM / CS indicators (raw labels such as
  `RM.V` on hover, not primary), a plain-language narrative label
  ("Embargo active", "Waiting for vendor response"), and role badges
  (REPORTER, VENDOR, COORDINATOR, CASE_MANAGER).

---

## Task Sequence (epic #676)

1. **Land `feature/demo-ui` on `main`** (#3640). Blocks 2 and 3.
2. **Live mode** (#3642) — compose service with reverse proxy; Log Replay
   subscribes to each actor's stream; scenario selector, branding,
   disclaimer.
3. **Branch-point choices via real triggers** (#3643) — report validation
   on scenario A first. Blocked by 2.

---

## Open Questions / Future Work

- **CI for `ui/`**: whether `ui/` gets a lint/build job is a maintainer
  decision (agents do not touch CI); raised in #3640.
- **Duplicated display logic**: `caseLedgerMapper.ts` holds its own event
  phrasing, parallel to the `SEMANTIC_REGISTRY` phrases `report.py` renders
  (DRPT-03-005 forbids that duplication *within* the report tool). Consider
  exporting the registry phrases to JSON the way `export_states.py` exports
  the state machines.
- **CYOA script format**: branching logic may benefit from a declarative
  format (e.g., a YAML scenario tree) rather than hard-coded React state.
- **State machine visualization**: LED-style indicators need a visual design
  pass; the SVG state diagrams in the Vultron docs are a candidate base.
- **Container startup**: whether "Start Demo" spins up containers or assumes
  they are already running.
- **Accessibility**: the graph must be usable by viewers who cannot read
  color-coded state indicators.
- **Later branches**: once the happy-path UI exists, failure-mode scenarios
  (embargo collapse, vendor decline, reporter going silent) are a matter of
  wiring new CYOA options.
