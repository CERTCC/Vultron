---
status: accepted
date: 2026-09-24
deciders: Allen D. Householder
consulted: Greg Strom
informed: CERT/CC Vultron protocol team
stakeholder_type: [project-contributor]
---

# The Interactive Demo UI Is a React/ReactFlow Operator-Side Ledger Watcher, Fed by a Prototype-Only SSE Stream

## Context and Problem Statement

Vultron's demos are Python scripts whose evidence is scrolling logs and, after the fact, a static HTML timeline (`vultron/demo/report.py`).
That convinces developers but not the funders and practitioners who decide whether to invest in or adopt the protocol.
The 2026-05-15 design session (#533) called for a ReactFlow choose-your-own-adventure UI fed by per-actor WebSocket streams, and #665 proposed a server-sent-events stream of case ledger entries as its transport.

Since then, `origin/feature/demo-ui` has accumulated a working React 19 + TypeScript + Vite + ReactFlow app under `ui/` with two modes.
One is a client-side simulation that re-implements protocol rules in TypeScript.
The other replays case-ledger JSONL files the container demos write, but only after the fact.
Neither talks to a running Vultron server.

The questions this record settles are: what vehicle the stakeholder demo uses, what it treats as the source of truth, where it sits relative to the protocol, and how it learns about changes.

## Decision Drivers

- The audience is non-technical, so the artifact must be a polished, browser-based story rather than developer tooling.
- What the audience sees should be what Vultron actually did, not a parallel model of it.
- Demonstrating a case must not change that case.
- The project stack has no JavaScript toolchain, and adding one needs explicit approval.
- A live ledger feed has observability value (debugging, CI) even without a UI.

## Considered Options

- Vehicle: the React/ReactFlow app on `feature/demo-ui`; a self-contained HTML live page reusing the report tool's timeline model; the existing static report presented after the fact; no UI for now.
- Source of truth: the real system's case ledgers, live; the branch's TypeScript simulation; both on equal footing.
- Transport: server-sent events; a WebSocket per actor container, as the 2026-05-15 session proposed.
- Identity: operator-side tooling with no case identity; an Observer participant receiving `Announce(CaseLedgerEntry)`.
- Change notification for the stream: server-side polling of the DataLayer; an in-process per-case notification queue fed by the ledger write paths.

## Decision Outcome

Chosen options: **the React/ReactFlow app**, **the real system live**, **operator-side**, and **SSE with server-side polling**, because together they give a non-technical audience a polished browser story that shows what Vultron actually did, without changing the case being shown.
The React/ReactFlow app is chosen because it is the most polished artifact for this audience and already exists.
The real ledgers are the source of truth because a parallel model can diverge from the protocol unnoticed.
The dashboard is operator-side because demonstrating a case must not change it.
The stream is SSE because data flows one way only, and it is polled because polling needs no hook in the ledger write paths while still giving observability value without a UI.

1. The stakeholder demo is the React/ReactFlow app from `feature/demo-ui`, living in `ui/`.
   This admits Node/npm, Vite, and React as a project-sanctioned toolchain **scoped to `ui/`**; no Python code depends on it.
2. The headline mode is the branch's Log Replay mode grown into a live view of a running scenario.
   The TypeScript simulation remains as an offline mode labelled illustrative, and is frozen: it receives no new protocol logic.
3. The dashboard is operator-side, with no case identity.
   It reads each actor's ledger stream and is never a participant.
   In ADR-0097's terms it is the watching half of a Sentinel (a call-in pattern), and it becomes a full Sentinel when branch-point choices call real trigger endpoints on the actor the presenter plays.
4. Each actor exposes `GET /api/v2/actors/{actor_id}/demo/cases/{case_id}/log/stream`, a `text/event-stream` of that actor's case ledger entries.
   A container may host several actors (a self-hosted case-actor, for example), so the dashboard opens one stream per actor, not per container.
   It is mounted only in `RunMode.PROTOTYPE`, beside the existing ledger read endpoints (TRIG-09).
   It replays from `?since=` or `Last-Event-ID`, learns of new entries by polling the DataLayer, stops cleanly when the client disconnects, and emits a terminal `close` event when the server shuts down.
   It is justified on its own observability merits and does not depend on the UI.
5. The browser reaches the containers through a reverse proxy in the UI's compose service rather than through CORS on the Vultron server.

Implementation guidance and the Task sequence live in `notes/demo-interactive-ui.md`.

### Consequences

- Good, because the audience watches Vultron's own ledgers, so the demo cannot quietly diverge from the protocol.
- Good, because the dashboard never alters the case it demonstrates and can show every actor's replica side by side.
- Good, because polling needs no hook in the commit or replica-receipt paths and no app-scoped pub/sub state that could leak between test apps.
- Good, because the stream is useful on its own (`curl -N` tailing) and can ship before the UI.
- Bad, because the repository gains a second language toolchain with its own dependencies and upkeep.
- Bad, because the frozen TypeScript simulation is still a second protocol copy for as long as it is kept.
- Bad, because the operator-side dashboard sees more than any participant would; this is acceptable only because the stream is prototype-only.
- Bad, because polling costs a bounded, repeated read load per open stream.

## Validation

- The stream endpoint is absent (404) outside `RunMode.PROTOTYPE`, which is verified by test.
- An integration test covers connect → replay existing entries → commit a new entry → receive it → disconnect.
- Live mode is validated by running a registered scenario while the UI renders it from the streams alone, with no file upload.
- Review rejects new protocol logic in the TypeScript simulation.

## Pros and Cons of the Options

### No UI for now

- Good, because it adds no toolchain and no upkeep.
- Bad, because the stakeholder audience keeps getting scrolling logs, which is the problem this record exists to solve.

### Self-contained HTML live page

- Good, because it needs no JavaScript toolchain and reuses the report tool's timeline model.
- Bad, because it discards substantial, more polished prior art already built for this audience.

### Static report presented after the fact

- Good, because it already exists.
- Bad, because nothing is live, so it does not tell the story as it happens.

### TypeScript simulation as the headline

- Good, because it runs with no containers and is already interactive.
- Bad, because it is a parallel implementation of the protocol, and the audience is not watching Vultron run.

### Simulation and live system on equal footing

- Good, because the demo works with or without containers.
- Bad, because the two modes must be kept in step, and the protocol logic in the simulation grows as a second implementation.

### WebSocket transport

- Good, because it could also carry the presenter's choices back to the server.
- Bad, because data flows one way only (choices already go out as ordinary trigger POSTs), so it adds a handshake and a bidirectional protocol for no gain over browser-native SSE.

### Observer participant

- Good, because it sees exactly what the protocol allows a participant to see.
- Bad, because it appears in every case roster, must be invited into each scenario, and sees only what it is sent.

### In-process notification queue

- Good, because it pushes instantly without repeated reads.
- Bad, because every ledger write path needs a hook, and app-scoped queues risk leaking state across `create_app()` instances.

## More Information

- Planning session: #2847 (group G19), members #533 and #665; epic #676.
- Prior art: `origin/feature/demo-ui` (tip `4398ed7be`, 2026-09-08).
- Related: ADR-0097 (Sentinel as a call-in pattern), ADR-0098 (demo scenario registry).
