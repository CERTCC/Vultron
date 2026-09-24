---
title: Interactive Demo UI — Scenarios and Architecture
status: active
description: >
  Design for the Vultron interactive demo UI: a React/ReactFlow dashboard for
  stakeholder presentations that watches the real system's case ledgers live
  over a prototype-only SSE stream, operator-side with no case identity, with
  branch-point choices driven through the real trigger endpoints. Records the
  feature/demo-ui prior art and the Task sequence under epic #676.
related_notes:
  - notes/demo-future-ideas.md
  - notes/fv-demo.md
  - notes/demo-scenario-registry.md
  - notes/case-ledger-authority.md
related_specs:
  - specs/multi-actor-demo.yaml
  - specs/triggerable-behaviors.yaml
  - specs/demo-report.yaml
relevant_packages:
  - vultron/demo/scenario
  - vultron/adapters/driving/fastapi/routers
---

# Interactive Demo UI — Scenarios and Architecture

**Sources**: 2026-05-15 design session (#533); 2026-09-24 planning session for
planning group G19 (#2847), which settled the vehicle, the data path, and the
Task sequence. Decision record: ADR-0104.

This is presentation tooling, not protocol work. It generates no `specs/`
requirements (G19 AC-3); everything below is design guidance.

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

## Decisions (2026-09-24)

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
   actor container's prototype-only ledger stream; it is never a case
   participant, never appears in a roster, and never changes the case being
   demonstrated. It is the watching half of a **Sentinel** (a call-in
   pattern, ADR-0097 — not a capability shape); it becomes a full Sentinel
   once branch-point choices call trigger endpoints. The rejected
   alternative — an Observer participant receiving `Announce(CaseLedgerEntry)`
   — would alter every scenario's roster and see only what it is sent.
5. **Transport: server-sent events of case ledger entries, polled
   server-side.** One direction of flow only (choices go out as ordinary
   trigger POSTs), so SSE rather than the WebSocket the 2026-05-15 session
   proposed. The stream is justified on its own observability merits
   (`curl -N` tailing during debugging and CI), independent of the UI.
6. **Delivery is blocked on the branch landing.** The branch is not ready to
   land; landing it is Greg Strom's work, tracked as its own Task that
   blocks the UI Tasks. The SSE endpoint does not wait for it.

---

## Prior Art — `origin/feature/demo-ui`

As of 2026-09-08 (tip `4398ed7be`, forked from `main` at `ff4b39cbc`,
2026-09-03), about 16k lines, authored by Greg Strom:

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
  and event types). Several files are very large (`caseLedgerMapper.ts`
  1709 lines, `vendorActions.ts` 1642 lines).

---

## Architecture

### Data path

```text
actor container (finder, vendor, coordinator, case-actor, …)
  └─ GET /actors/{id}/demo/cases/{case_id}/log/stream   (SSE, prototype-only)
        ▲  one stream per container — each shows that actor's replica
        │
  ui compose service: serves built ui/ and reverse-proxies /<service>/…
        ▲
  browser (EventSource per actor)  ──POST trigger──▶  actor the presenter plays
```

- **Reverse proxy, not CORS.** Actor containers publish ephemeral host ports
  and the server has no CORS middleware. The UI's compose service serves
  the built app and proxies each actor under one origin, so the Vultron
  server needs no change.
- **Per-replica view.** Because the dashboard reads every container, it can
  show replica convergence side by side — the same per-actor presence view
  `vultron/demo/report.py` builds after the fact (DRPT-02-005).

### Live case log stream

Extends the existing prototype-only ledger read endpoints in
`vultron/adapters/driving/fastapi/routers/demo_triggers.py`
(`GET /actors/{actor_id}/demo/cases/{case_id}/log` and `…/log/{index}`,
TRIG-09).

- **Path**: `GET /actors/{actor_id}/demo/cases/{case_id}/log/stream`, beside
  the existing ledger endpoints — not the `/actors/{actor_id:path}/cases/…`
  path first proposed in #665. It resolves the case id with the same
  `_resolve_case_id` helper as its siblings.
- **Mounted only in `RunMode.PROTOTYPE`** (TRIG-09-002/003); returns 404
  otherwise because the route is absent.
- **Response**: `text/event-stream`. Each event's `id:` is the entry's
  `log_index` and its `data:` is the entry serialized exactly as the list
  endpoint serializes it (wire form, by alias, `exclude_none`).
- **Replay**: `?since=<log_index>` (or the browser's `Last-Event-ID` on
  reconnect) skips entries at or below that index; absent means replay from
  the beginning.
- **Notification: server-side polling.** The handler re-reads the case's
  ledger entries on a short interval (~250 ms) and emits those above the last
  index sent. Chosen over an in-process queue because it needs no hook in
  the commit path, catches entries however they arrived (local commit or
  replicated in), and needs no app-scoped pub/sub state that could leak
  between test apps. The bounded read load is acceptable for a
  prototype-only endpoint.
- **Termination**: stops cleanly when the client disconnects; emits a
  terminal `event: close` when the server shuts down (and, if cheaply
  detectable, when the case closes).
- **Not a replication channel.** Like its siblings, it is demo tooling;
  participants replicate through the ActivityStreams inbox (SYNC-07).

---

## Three-Scenario Presentation Set

All presentation scenarios share one UI; only the number of actor lanes
differs. They map onto registered demo scenarios (`vultron-demo` sub-commands,
ADR-0098); the Case Actor runs in its own container in every scenario.

| Presentation | Narrative | Closest registered scenario |
|---|---|---|
| A — Two-Actor | Researcher reports a bug directly to a single vendor | `fv` |
| B — Coordinator | Reporter routes through a neutral coordinator for a widely-used library | `fcv` |
| C — Multi-Vendor | Shared component used by several vendors; the vendor set expands | `fvv`, `fvcv-*`, `fcvcv` |

The pre-rebuild `three_actor_demo.py` and `multi_vendor_demo.py` scripts the
2026-05-15 session planned to remove are already gone.

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

1. **Land `feature/demo-ui` on `main`** (#3640) — Greg Strom. Blocks 3
   and 4.
2. **Live case log SSE endpoint** (#3641) — independent; can start now.
3. **Live mode** (#3642) — compose service with reverse proxy; Log Replay
   subscribes to each container's stream; scenario selector, branding,
   disclaimer. Blocked by 1 and 2.
4. **Branch-point choices via real triggers** (#3643) — report validation
   on scenario A first. Blocked by 3.

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
