# AGENTS.md — Vultron Demo UI (`ui/`)

> Scope: this file governs the **`ui/` React/TypeScript visualization demo
> only**. The repo-root [`AGENTS.md`](../AGENTS.md) governs the Python backend;
> its rules (uv, pytest, behavior trees, AS2 factories) do **not** apply here.

## 1. What this project is

A swimlane-timeline demo of the Vultron Coordinated Vulnerability Disclosure
(CVD) protocol. Each participant (Finder, Vendor(s), Case Actor) gets a
horizontal **lane**; time flows left→right; protocol events are **nodes** in the
lanes. The goal is communication and teaching, not production fidelity. Stack:
**React 19 + TypeScript + Vite**, SVG timeline, no backend — all client-side.

### The two modes

`main.tsx` → `DemoSelector.tsx` toggles two independent App roots that do **not**
share an engine — know which one you are editing:

| Mode | File | What it is |
|---|---|---|
| **Multi-Vendor** (`'multi'`, default) | `App-multivendor.tsx` | A client-side simulation; RM/EM/VFD/PXA defer to the protocol artifact (§9). Labelled **illustrative** in the UI (ADR-0104). |
| **Log Replay** (`'logreplay'`) | `App-logreplay.tsx` | Replays real case-ledger JSONL, validated against the artifact. |

### How to run it

```bash
cd ui
npm install    # if ui/node_modules is absent or package.json changed
npm run dev    # Vite dev server; prints a localhost URL
npm run build  # tsc + vite build
npm run lint   # eslint
```

Nothing Python is needed at runtime: the demo imports the committed
`src/data/protocol_states.json` directly.

## 2. Visual grammar: decision / consequence nodes

Every protocol action produces **one decision node** (darker) in the acting
actor's lane and **zero or more consequence nodes** (paler) in every other
affected lane, placed at the **same X** and linked by a dashed `causedBy` arrow
(a consequence's `causedBy` = the decision node's `id`). Same-X plus the arrow
are what make one event read as one coordinated moment; a missing `causedBy`
draws no arrow and breaks the story. Colors live in `constants.ts` (per-role
palettes; vendors cycle via `getVendorColor` / `getVendorNodeColors`).

## 3. The CVD state model

Every node is a question, an answer, or an update to a participant's
RM/EM/VFD/PXA state. The four machines:

- **RM** (Report Management, **per-participant**):
  `START → RECEIVED → VALID → ACCEPTED | DEFERRED | INVALID → CLOSED`
- **VFD** (Vendor Fix Development, **per-participant**): `vfd → Vfd → VFd → VFD`
  (each capital is a milestone: aware → fix-ready → fix-deployed).
- **EM** (Embargo Management, **case-level**): `NONE → PROPOSED → ACTIVE → REVISE → EXITED`.
- **PXA** (Public / eXploit / Attacks, **case-level**).

**Scope:** RM and VFD are stored per participant
(`ParticipantState.rmState` / `.vfdState`); EM and PXA are single case-level
values on `DemoState`. Do not model EM or PXA per-participant.

## 4. Key data types (`src/types.ts`)

- `TimelineEvent` — a node: `type: 'decision' | 'consequence'`, `lane`, `x`, `causedBy?`, `consequences[]`.
- `DemoState` — the demo: `participants` map, case-level `emState` / `pxaState`, `timelineEvents[]`, `eventLog[]`.
- `ParticipantState` — per participant: `role`, `rmState`, `vfdState`, `laneIndex`, consent/publication/closure flags.

## 5. Log Replay pipeline (`src/utils/`)

`caseLedgerParser.ts` → `caseLedgerMapper.ts` → `App-logreplay.tsx`.

- **`caseLedgerParser.ts`** — `parseCaseLedger()` yields one `CaseLedgerEntry`
  per line; `normalizeLedger()` **dedups by `entryHash` and sorts by `logIndex`**
  (NOT `receivedAt` — entries can share a wall-clock second). `actorUrlToLaneId()`
  maps actor URLs to lanes (`case-actor` first, then `finder`, `coordinator`, `vendor-N`).
- **`caseLedgerMapper.ts`** — `buildTimelineFromCaseLedger()` pre-scans to fix
  lane order, then walks entries in `logIndex` order holding a **shadow protocol
  state**. The log records **state SNAPSHOTS, not transitions**, so the mapper
  diffs each snapshot against the previous to recover the trigger and validates
  it against `../protocol`: legal → advance; illegal → flag `violation: true`.
  Emits the §2 decision/consequence + `causedBy` + same-X grammar.
- **`App-logreplay.tsx`** — loads committed samples via `?raw` or manual upload;
  violation nodes render red + ⚠️; nodes are hover-tooltipped; lanes collapsible.

### Durable rules the mapper encodes

- A participant's **first** snapshot is a *seed*, never a transition.
- Case-level **EM/PXA are forward-only**: a participant-local snapshot may
  advance them but must never regress the verb-driven state.
- `close_case` is the closer's **self-declaratory `Leave`** (CM-23-012,
  ADR-0084): it advances that actor's RM to `CLOSED` from **any** rung and is
  **not** validated against the RM machine — do not flag a leaver closing from
  `RECEIVED`.

## 6. How the protocol validates the log

The mapper treats the artifact (via `protocol.ts`) as the authority; every step
is checked with `isLegalTransition`. Node annotations: **violation** (red ⚠️,
illegal from the shadow state) and **inferred** (amber ℹ️, a multi-step snapshot
diff whose path was guessed). A clean single legal step gets none.

## 7. Tooling and log locations

- `node_modules/.bin` tools (eslint, tsc, vite) run via `npm run *`; `jq` reads `*.jsonl`.
- **Two log locations — do not confuse them:**
  - **`ui/src/sample-logs/`** — COMMITTED ledgers the "Load …" buttons import via
    `?raw`. In-tree, so a fresh clone builds. One dir per scenario, plus
    `synthetic/` (hand-authored violation fixtures).
  - **`devlogs/`** (repo root) — GITIGNORED runtime output from the container
    demo. Not tracked; a fresh clone has none. Point manual uploads here.

## 8. Working norms

- Identify which of the two modes a request targets before editing.
- Preserve the decision / consequence + `causedBy` + same-X grammar (§2).
- Keep RM/VFD per-participant and EM/PXA case-level (§3).
- When replay "looks wrong," decide whether it is a mapper bug (§5) or a
  missing-field-in-the-logs problem before changing code.

## 9. Deferring to the protocol artifact

The demo does **not** hardcode the protocol's states and transitions. It reads a
committed JSON artifact, `src/data/protocol_states.json`, generated from the
authoritative Python state machines by `uv run export-demo-states`
([`export_states.py`](../vultron/metadata/demo_scenarios/export_states.py)); a
drift test keeps it in sync. `src/protocol.ts` is the only file that reads it,
exposing helpers (`nextState`, `requireNextState`, `isLegalTransition`,
`machineStates`) that handlers and filters go through. The artifact also carries
`embargo_viability`, a cross-machine rule the per-machine tables cannot express.

**Boundary.** Defer to the artifact for what the protocol models
**declaratively** (the state machines and `embargo_viability`). Rules it models
**procedurally** — the CASE_MANAGER role, or "the case is done" as a fold over
participants' RM states — stay as explicit, documented demo overlays; do not
export a scraped copy.

## File layout

- `App-multivendor.tsx` / `App-logreplay.tsx` — the two modes, imported only by
  `DemoSelector.tsx`.
- `src/actions/*.ts` + `src/state/actionFilters.ts` — Multi-Vendor handlers and
  filters (imported only by `App-multivendor.tsx`).
- `src/utils/caseLedger*.ts` — the Log Replay parser and mapper.
- **Shared (a change here affects both modes):** `protocol.ts`,
  `participantHelpers.ts`, `stateUpdaters.ts`, `constants.ts`, `types.ts`,
  `components/`.
