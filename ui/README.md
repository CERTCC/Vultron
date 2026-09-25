# Vultron UI Demo

Interactive visualization of the Vultron Coordinated Vulnerability Disclosure
(CVD) protocol. Each participant (Finder, Vendor(s), Case Actor) gets a
horizontal **swimlane**; time flows left→right; protocol events appear as
**nodes** in the lanes. The goal is communication and teaching — making the
abstract CVD state machines legible.

> For the detailed architecture and working norms of this subproject, see
> [CLAUDE.md](CLAUDE.md). This README is the quick-start overview.

## Prerequisites

- Node.js (with npm)

## Getting Started

1. **Install dependencies:**
   ```bash
   npm install
   ```

2. **Run the development server:**
   ```bash
   npm run dev
   ```

3. **View the demo:**
   Open your browser to the URL shown in the terminal (usually `http://localhost:5173`).

## Demo Modes

The application has **two independent modes**, toggled from the selector bar at
the top of the page ([DemoSelector.tsx](src/DemoSelector.tsx)). They do **not**
share an engine — each is a separate implementation.

### Multi-Vendor (illustrative)

- **File:** [App-multivendor.tsx](src/App-multivendor.tsx)
- A **client-side simulation** that re-implements the CVD workflow in
  TypeScript. It illustrates how multiple vendors independently participate in
  one vulnerability case; it is **not** driven by a running Vultron system.
  Accordingly it is labelled **Illustrative** in the UI.
- **Participants:** Finder, one or more Vendors (added dynamically via invite),
  Case Actor.
- **Highlights:**
  - Independent per-vendor RM/VFD progression, shared case-level EM/PXA state.
  - Dynamic vendor invitations mid-case.
  - Case-ownership transfer between vendors.
  - State transitions defer to the committed protocol artifact (see
    [Source of truth](#source-of-truth)) rather than hardcoding the rules.

### Log Replay

- **File:** [App-logreplay.tsx](src/App-logreplay.tsx)
- **Visualization only.** Reads real **case-ledger JSONL** files produced by the
  container-based Vultron demos and replays them on the same swimlane interface,
  validating each derived transition against the protocol artifact and flagging
  any violations.
- Load a bundled sample from the buttons in the UI, or upload your own
  `*-case-ledger.jsonl` files. Bundled samples live in
  [src/sample-logs/](src/sample-logs/) (in-tree, so a fresh clone runs without
  the container demo).

See [LOG_REPLAY_README.md](LOG_REPLAY_README.md) for the Log Replay pipeline in
depth, and [MULTI_FOLDER_UPLOAD.md](MULTI_FOLDER_UPLOAD.md) for uploading
multi-actor log folders.

> **Note:** switching modes resets in-memory state; the toggle is not persisted,
> so a page refresh returns to Multi-Vendor.

## Available Commands

- `npm run dev` — start the development server with hot reload
- `npm run build` — type-check and build for production (`tsc -b && vite build`)
- `npm run preview` — preview the production build locally
- `npm run lint` — run ESLint

## Understanding the Visualization

### Node Types

- **Decision nodes (darker):** an action taken by the actor in whose lane the
  node sits.
- **Consequence nodes (lighter):** automatic effects of that decision in other
  participants' lanes, drawn at the **same X coordinate** and linked by a dashed
  `causedBy` arrow — so one protocol event reads as one coordinated moment
  across lanes.

### Participant Lanes

Each participant has a horizontal lane showing their actions, the consequences
that land in their context, and their current state across the relevant state
machines. Lanes are born from events (submitting a report creates the Vendor and
Case Actor lanes; inviting a vendor adds a lane).

### State Machines

1. **RM (Report Management)** — per-participant:
   `START → RECEIVED → VALID → ACCEPTED | DEFERRED | INVALID → CLOSED`
2. **VFD (Vendor Fix Development)** — per-participant:
   `vfd → Vfd → VFd → VFD` (each capital is a milestone: vendor aware → fix
   ready → fix deployed).
3. **EM (Embargo Management)** — case-level (shared):
   `NONE → PROPOSED → ACTIVE → REVISE → EXITED`.
4. **PXA (Public / eXploit / Attacks)** — case-level (shared). Exploit publication
   implies public awareness.

> RM and VFD are stored per participant; EM and PXA are single case-level values.

## Tech Stack

- React 19 + TypeScript
- Vite (build tool)
- [@xyflow/react](https://reactflow.dev/) — interactive node-based visualization

## Architecture

### Key Files

- [src/main.tsx](src/main.tsx) — entry point
- [src/DemoSelector.tsx](src/DemoSelector.tsx) — mode toggle
- [src/App-multivendor.tsx](src/App-multivendor.tsx) — Multi-Vendor illustrative simulation
- [src/App-logreplay.tsx](src/App-logreplay.tsx) — Log Replay visualization
- [src/actions/](src/actions/) — Multi-Vendor action handlers (pure functions)
- [src/state/](src/state/) — state management + action filters
- [src/utils/](src/utils/) — case-ledger parser/mapper for Log Replay
- [src/protocol.ts](src/protocol.ts) — typed wrapper over the protocol artifact

<a id="source-of-truth"></a>
### Source of truth

Both modes defer the protocol's states and transitions to a committed artifact,
`data/json/protocol_states.json` at the **repository root** (not under `ui/`),
generated from the authoritative Python state machines by
`uv run export-demo-states`
([vultron/metadata/demo_scenarios/export_states.py](../vultron/metadata/demo_scenarios/export_states.py)).
The Multi-Vendor demo computes its transitions from it; Log Replay validates real
logs against it. A CI drift test keeps the artifact in sync with the protocol.
The demo imports the JSON directly, so `npm run dev` never needs Python.

## Reference

- [ui/CLAUDE.md](CLAUDE.md) — full subproject architecture and conventions
- [State machine definitions](../vultron/core/states/)
