# CLAUDE.md — Vultron Demo UI (`ui/`)

> Scope: this file governs the **`ui/` React/TypeScript visualization demo
> only**. The repo-root [`AGENTS.md`](../AGENTS.md) governs the Python backend
> (FastAPI, behavior trees, ActivityStreams wire layer) and does **not** cover
> this subproject. When working anywhere under `ui/`, read this first.

---

## 1. What this project is

A **visually polished swimlane-timeline demo** of the Vultron Coordinated
Vulnerability Disclosure (CVD) protocol. Each participant (Finder, Vendor(s),
Case Actor) gets a horizontal **lane**; time flows left→right; protocol events
appear as **nodes** in the lanes. The goal is communication/teaching, not
production fidelity — it makes the abstract CVD state machines legible.

Stack: **React 18 + TypeScript + Vite**, SVG-rendered timeline. No backend
calls — everything runs client-side. Dev server: `npm run dev` (Vite).
Build: `npm run build` (tsc + vite). Lint: `npm run lint` (eslint).

### Entry point and the four demo modes

`main.tsx` → `DemoSelector.tsx` toggles between four independent App roots:

| Mode | File | Source of truth |
|------|------|-----------------|
| **Single-vendor** (`'single'`) | `App.tsx` | Scripted / hardcoded actions |
| **Multi-vendor** (`'multi'`, default) | `App-multivendor.tsx` | Scripted via `actions/` handlers |
| **Multi-vendor (Validated)** (`'multi-validated'`) | `App-multivendor-validated.tsx` | Same as multi-vendor, but RM/EM/VFD/PXA defer to `protocol_states.json` (§9). **In-progress overhaul** — a frozen fork of multi-vendor. |
| **Log Replay** (`'logreplay'`) | `App-logreplay.tsx` | Uploaded JSONL case logs |

These are **separate, parallel implementations** — they do **not** share one
engine. The multi-vendor demo is driven by handcrafted action handlers in
`src/actions/`; the log-replay demo is driven by parsing real `*.jsonl` logs
through `src/utils/`. Changes to one mode usually do **not** propagate to the
others. Know which mode you're touching.

> **Multi-vendor vs. Multi-vendor (Validated):** the Validated mode is a
> deliberate, isolated **fork** of the working multi-vendor demo so the proven
> demo keeps running untouched while the protocol-deferral overhaul proceeds
> (see §9 "Validated fork"). It duplicates the multi-vendor-exclusive logic into
> `actions/validated/` + `state/validated/actionFilters.ts`; the originals are
> frozen. The two trees **drift** — a fix to one does NOT propagate to the
> other. This is temporary: once Validated proves out it replaces the original
> and the duplicates are deleted.

> Note: `App.css` defines its own `LANE_HEIGHT = 295` and inline node sizes,
> separate from `constants.ts` (`LANE_HEIGHT = 400`, `NODE_HEIGHT = 100`).
> Constants are **not** centralized across all three apps — verify the file
> you're editing rather than assuming `constants.ts` applies.

---

## 2. The core visual grammar: Decision / Consequence nodes

This is the single most important concept in the demo. Every protocol action
produces:

- **One "decision" node** — darker color — in the lane of the **actor who took
  the action**. (e.g. Finder's "Submit Report", Vendor's "Engage Case".)
- **Zero or more "consequence" nodes** — paler color — in the lanes of **every
  other participant affected**, placed at the **same X coordinate** as the
  decision.
- **Dashed arrows** from the decision node to each consequence node,
  expressed in data via the `causedBy` field (consequence's `causedBy` =
  decision node's `id`).

Vertical alignment (same X) + the `causedBy` arrow are what make a single
protocol event read as one coordinated moment across lanes. **If `causedBy` is
missing, no arrow is drawn and the visual story breaks** (see `App-logreplay`
arrow logic — arrows are only emitted for events that have `causedBy`).

Colors live in `constants.ts`: per-role `decision`/`consequence`/`*Hover`
palettes, with a 5-color vendor palette that cycles via `getVendorColor` /
`getVendorNodeColors`.

---

## 3. The CVD state model (what nodes actually represent)

Fundamentally, every node is one of:

1. A **question** being asked (e.g. propose embargo, ask a note),
2. An **answer** to a question (accept/reject/revise, reply to a note), or
3. An **update to a participant's RM / EM / VFD / PXA state**.

The four state machines:

- **RM** (Report Management, **per-participant**):
  `START → RECEIVED → VALID → ACCEPTED | DEFERRED | INVALID → CLOSED`
- **VFD** (Vendor Fix Development, **per-participant**):
  `vfd → Vfd → VFd → VFD` (capitalization is meaningful — each capital letter
  is a milestone: aware → fix-ready → fix-deployed).
- **EM** (Embargo Management, **case-level / global**):
  `NONE → PROPOSED → ACTIVE → REVISE → EXITED`
- **PXA** (Public / eXploit / Attacks, **case-level / global**).

> **Critical scope distinction:** RM and VFD are stored **per participant**
> (`ParticipantState.rmState` / `.vfdState`). EM and PXA are **single
> case-level values** on `DemoState` (`emState`, `pxaState`). Do not model EM
> or PXA per-participant.

Milestones M1 (embargo active), M3 (notes exchanged), M4 (VFd), M5 (VFD),
M6 (public) are **derived/computed by the UI**, not stored in logs.

Lanes are **born from events**: submitting a report creates the Vendor +
Case Actor lanes; inviting a vendor creates a new vendor lane (and shifts the
Case Actor lane down — see `inviteActions.ts`, which re-maps existing events'
`lane` indices when a vendor is inserted).

---

## 4. Key data types (`src/types.ts`)

- `TimelineEvent` — `{ id, actor, participantId?, label, x, lane,
  type:'decision'|'consequence', consequences[], causedBy?, enablesNext?,
  timestamp? }`
- `DemoState` — `{ phase, participants:Map, emState, pxaState, timelineEvents[],
  eventLog[], nextXPosition, invitedVendors:Set, embargoProposerId? }`
- `ParticipantState` — `{ id, name, role, color, rmState, vfdState,
  embargoAccepted, embargoProposedToParticipant?, hasPublished, hasClosed,
  visible, laneIndex, hasRepliedToCurrentNote? }`

---

## 5. Log Replay pipeline (`src/utils/`)

`jsonlParser.ts` → `logEventMapper.ts` → `App-logreplay.tsx`.

- `parseJsonl` parses one `CaseLogEntry` per line.
- `extractActorType(url)` maps actor URLs to lane ids:
  `case-actor`→`caseactor`, `//vendor:`→`vendor-1`, `//finder:`→`finder`.
- `buildTimelineFromLogs` groups entries into 1-second buckets keyed
  `${eventType}:${roundedTime}`, then tries to split each group into a
  decision entry + consequence entries.

### Known bugs in the replay mapper (diagnosed, NOT yet fixed)

1. **Missing arrows / no consequences.** The real logs carry no causal link, so
   no `causedBy` is produced for most events → no arrows.
2. **X-overlap / bad vertical alignment.** `visualEventIndex` is only
   incremented in the decision/consequence path of `buildTimelineFromLogs`
   (~line 291). The `else` branch that handles plain status/embargo/verification
   events (~lines 224–239) `return`s early **without incrementing**, so those
   events pile up at the same X as the next grouped event. This is why
   "Engage Case" and "STATUS: Accepted VFD" rendered on top of each other.
3. **No dedup.** `mergeLogEntries` sorts by `receivedAt` but never dedups by
   `entryHash`, and in `devlogs/two-actor` the vendor and case-actor files are
   byte-identical — so duplicates flow through.

Do not "fix" these by faking data in the mapper. The deeper problem is the log
format (below); the mapper fixes only matter once the logs carry the needed
fields.

---

## 6. What the demo needs FROM the logs (the data contract) — and the gaps

The demo needs, per event: **(a)** whose event it is, **(b)** which event caused
it, **(c)** question-vs-answer, **(d)** the actor's RM/EM/VFD/PXA state.

Audit of `devlogs/two-actor/` against that contract:

**Present and reliable:** `actor`, per-participant `rmState`+`vfdState`,
embargo consent (`target.embargoConsentState` = SIGNATORY/NO_EMBARGO +
`acceptedEmbargoIds`), `logIndex` (monotonic ordering), `receivedAt`,
`entryHash`/`prevLogHash`.

**Present but unreliable:** case-level **EM/PXA** (`caseStatus.{emState,
pxaState}`) is stamped on only *some* status events and lives in 3+ different
locations (`object.caseStatus`, `target.participantStatuses[N].caseStatus`,
`engage_case`'s `caseStatuses[0]`). Needs to be on **every** entry in **one**
fixed place.

**The biggest gaps — raise these with the log developer:**

1. **No `causedBy` / correlationId.** Nothing links an originating action to the
   receipt entries it triggers. `prevLogHash` is sequential, not causal. This is
   the root cause of missing arrows + misalignment. **Top priority.**
2. **No explicit `actionType` verb.** ~29 distinct demo actions (validate,
   accept, defer, propose-embargo, accept-revision, fix-ready, publish, …) all
   collapse into a single `add_participant_status` / AS2 `Add`. Distinguishable
   only by diffing state against the previous entry; embargo *negotiation* verbs
   aren't recoverable at all.
3. **No `loggedBy` / perspective field.** Whose copy a log entry is is only
   implied by which folder the file is in — and the vendor and case-actor files
   are byte-identical, while the finder file is a truncated subset starting at
   `logIndex 2`. So genuine cross-perspective records don't exist in this sample.
4. **Notes (questions & answers) are absent.** The `notes` array is always `[]`
   and there is no `add_note` / `Note` event type in the vocabulary. The entire
   Q&A dimension — central to the demo — has **no schema slot yet**.
5. **No first-class participant-join event.** Lanes appearing is only inferable
   from new actors showing up.

Also: `actor` ≠ subject. For some entries the `actor` is the recorder/relay
while `object.attributedTo` is the real subject (e.g. `logIndex 9`:
actor=vendor, attributedTo=finder). Use `attributedTo` for "whose state",
not `actor`.

---

## 7. Environment / tooling constraints (important)

- **`node` and `python3` are NOT available** in this dev environment. Do not try
  to run JSONL through node/python scripts.
- **`jq`** is available (`/usr/bin/jq`) — use it to inspect `*.jsonl` logs.
- `node_modules/.bin` tools (eslint, tsc, vite) work via `npm run *`.
- `devlogs/two-actor/{finder,vendor,case-actor}/` hold the sample logs. They are
  **known to be incomplete/duplicated** (see §6) — treat them as a flawed
  fixture, not a reference format.

---

## 8. Working norms for this subproject

- Identify **which of the three App modes** a request targets before editing;
  they don't share an engine.
- Preserve the decision/consequence + `causedBy` + same-X grammar (§2) — it's
  the whole point of the visualization.
- Keep RM/VFD per-participant and EM/PXA case-level (§3).
- When the issue is "the replay looks wrong," first check whether it's a mapper
  bug (§5) or a missing-field-in-logs problem (§6) before changing code.
- The root `AGENTS.md` Python rules (uv, pytest, BTs, AS2 factories) do **not**
  apply here. This is a standalone Vite app.

---

## 9. Deferring to the protocol's source of truth (in progress)

**Goal:** stop hardcoding the protocol's states/transitions in the demo. The
authoritative definitions live in Python at
[`vultron/core/states/`](../vultron/core/states/) — `rm.py` (RM), `em.py` (EM),
`cs.py` (`CS_vfd` = the `vfd→Vfd→VFd→VFD` ladder, and `CS_pxa`). Each has a
clean `create_*_machine()` factory exposing states + transitions uniformly.

**Approach chosen (committed-JSON + CI drift check):** a Python exporter dumps
those four machines to a committed JSON artifact; the demo imports it. The JSON
is generated *occasionally* (only when the protocol changes), committed to git,
and the demo imports it like any source file — so `npm run dev` never needs
Python. A pytest drift detector fails CI if the committed JSON goes stale.

**Artifact location:** `data/json/protocol_states.json` at the **repo root**
(NOT under `ui/`), following the SSVC `data/json/` precedent (per the protocol
maintainer). Living outside `ui/` matters because `ui/` does not exist on
`main` — keeping the artifact + test in `vultron/`/`test/`/`data/` lets the
drift test run on `main` independently of the demo.

**Exporter side (done in an earlier session):**
- [`vultron/scripts/export_states.py`](../vultron/scripts/export_states.py) —
  the exporter (`build_payload()` is importable; `main()` writes the file).
- [`test/test_demo_states_export.py`](../test/test_demo_states_export.py) —
  drift detector + payload-shape guard.
- [`pyproject.toml`](../pyproject.toml) — registers `export-demo-states`
  entry point.
- `data/json/protocol_states.json` — **GENERATED and committed.** Re-run
  `uv run export-demo-states` (outside the container) and re-commit whenever the
  protocol's state machines change.

**JSON shape:** `{ _README, rm, em, vfd, pxa }`, each machine =
`{ initial, states[], transitions[{trigger,source,dest}] }`. The exporter is
deterministic (no timestamps, fixed machine order) so the drift test can do a
byte-exact compare.

**Optional, deferred:** add `data/json/**` to the `paths:` triggers in
`.github/workflows/python-app.yml` to also catch hand-edits of the artifact.

### `ui/`-side refactor — the Validated fork (IN PROGRESS)

The refactor happens **only inside an isolated fork** (the "Multi-vendor
(Validated)" mode, §1), so the proven multi-vendor demo never breaks while this
proceeds. Decision (with the maintainer): **moderate deferral depth** — handlers
compute destinations from the JSON; filters derive RM/EM/VFD legality from it;
non-machine rules (embargo gating, notes, invites, visuals) stay as an explicit
overlay. NOT a full generic engine.

**Foundation — DONE (verified: `npm run build` green):**
- [`vite.config.ts`](vite.config.ts) — `server.fs.allow: ['..', '.']` so the
  artifact at the repo root (`../../data/json/protocol_states.json` from
  `src/`) is importable. `resolveJsonModule: true` added to
  [`tsconfig.app.json`](tsconfig.app.json) (was absent; not default even under
  bundler resolution). **This is the chosen answer to the old "Vite fs" note** —
  we did NOT copy the JSON into `ui/`.
- [`src/protocol.ts`](src/protocol.ts) — the ONLY file that reads the JSON.
  Builds a `source→trigger→dest` index per machine; exposes `nextState`,
  `requireNextState` (throws on illegal — for handlers), `isLegalTransition` /
  `legalTriggers` (for filters), `initialState`, `machineStates`, `isValidState`.
- [`src/protocolActions.ts`](src/protocolActions.ts) — maps all 31 demo action
  IDs to `{kind:'transition'|'composite'|'demo'}`. Verified 1:1 against the
  `handleAction` switch; every `(machine,trigger)` pair exists in the JSON.
  Composites: `submit-report` (rm `receive` + vfd `vendor_becomes_aware`),
  `vendor-notify-published` (pxa `public_becomes_aware` + em `terminate`).
  `demo`-kind = notes/replies/invites/publication-ack (no machine slot).

**The 5-step plan (Steps 1–3 done, 4–5 next):**
1. ✅ Make the artifact importable (vite + tsconfig).
2. ✅ `protocol.ts` — typed wrapper over the JSON.
3. ✅ `protocolActions.ts` — action-ID → machine-trigger bridge.
4. ⬜ Refactor the **forked** handlers (`actions/validated/*.ts`) to compute
   destination states via `requireNextState(...)` instead of hardcoding
   `{ rmState: 'VALID' }` etc. Leave node/consequence/event-log code untouched.
   Plan: do `handleValidateReport` first, review the diff, then apply the
   pattern across the ~15 transition handlers.
5. ⬜ Refactor the **forked** filters (`state/validated/actionFilters.ts`) so
   RM/EM/VFD gating comes from `isLegalTransition(...)`; keep non-machine rules
   (embargo-before-participation, `isPublic` early-termination, pending-note
   reply gating, invite availability) as an explicit overlay.

**Gotchas discovered (carry forward):**
- **`DECLINED` RM pseudo-state** ([actionFilters.ts:237](src/state/actionFilters.ts#L237))
  is NOT a real RM state in the JSON — it's a demo invention for declined
  invites, and is in fact never *written* anywhere (only read). Keep it as a
  demo-only pseudo-state, outside the machine.
- **VFD `vfd→Vfd`** (and **RM `START→RECEIVED`**) have no standalone user
  action — the demo sets vendors straight to `Vfd`/`RECEIVED` at report receipt
  ([finderActions.ts:26](src/actions/finderActions.ts#L26),
  [inviteActions.ts:49](src/actions/inviteActions.ts#L49)). Those triggers are
  folded into the `submit-report` / invite composites.

### Validated fork — file layout & isolation (how to keep it safe)

The overhaul's entire blast radius is **multi-vendor-exclusive**: `actions/*.ts`
and `state/actionFilters.ts` are imported ONLY by `App-multivendor.tsx`
(`App.tsx` is self-contained; `App-logreplay.tsx` uses only
`participantHelpers`). So the fork duplicates exactly those:
- `App-multivendor-validated.tsx` (copy of `App-multivendor.tsx`; only its
  `actions/` + `actionFilters` imports were repointed to the forks).
- `src/actions/validated/{finder,vendor,caseActor,invite,external}Actions.ts`
  (relative imports bumped `../` → `../../`).
- `src/state/validated/actionFilters.ts` (imports `../participantHelpers`,
  `../../types`).

**Shared (NOT forked, treat as stable):** `participantHelpers.ts`,
`stateUpdaters.ts`, `constants.ts`, `types.ts`, `components/`. If Step 4/5 ever
needs to change one of these, fork it too rather than mutating the shared copy
(that would leak into the frozen original).

**Invariant to preserve:** `App-multivendor-validated.tsx` must import ONLY from
`*/validated/*`; the original `App-multivendor.tsx` must import ONLY the
non-forked originals. A quick check:
`grep -nE "from './(actions|state)/" src/App-multivendor-validated.tsx` should
show only `validated/` paths.

### Lint / build status (end of this session)
- `npm run build` (`tsc -b && vite build`): **GREEN.**
- `npm run lint`: **3 errors + 4 warnings, all pre-existing or copied** — left
  intentionally. The 3 errors are in the held-back log-replay pipeline
  (`utils/jsonlParser.ts` `no-explicit-any` ×2, `utils/logEventMapper.ts`
  `no-useless-assignment`) — frozen pending the log-generator rework (§5–6). The
  4 warnings are `react-hooks/exhaustive-deps` in App.tsx / both multivendor
  apps (the 4th is just the fork's copy of the original's warning). Do NOT
  "fix" the log-replay lint by guessing types for the unstable log format.
- Earlier in this session a full rebuild (triggered by the tsconfig edit)
  unmasked 6 TS `noUnusedLocals` errors + a batch of eslint errors in files
  unrelated to this work; the trivial ones (dead locals, `(v: any)` filter
  callbacks → inferred, `let`→`const`) were cleared. `handleLoadDemoLogs` in
  `App-logreplay.tsx` was found unused but **kept** (`void`-referenced, with a
  comment) — it's a parked feature awaiting the log-generator rework, not dead
  code.

### Branch / sync context
- Work lives on **`feature/demo-ui`**. As of this session it was synced with
  `main` (was 302 behind / 10 ahead → now level + ahead). `ui/` merged with
  **zero** conflicts; the only merge conflict was a gitignored generated scan
  file, resolved by keeping it deleted.
- A **local** git identity is set for this repo: `Greg Strom
  <gstrom@sei.cmu.edu>` (matches existing commit authorship).

### Tooling constraint update (IMPORTANT)
This container has **no `node`, `npm`, `python`, `python3`, `uv`, or `pip`** on
PATH — only `jq` and `node_modules/.bin/*` shims (which still need a node
runtime). Consequence: **the agent cannot run the exporter, pytest, or the Vite
build/dev/lint commands in-container.** Those must be run by the user in their
real environment — hand them the exact commands rather than attempting them
here. (Verification of Steps 4–5 will lean on the build/lint gate plus careful
before/after equivalence review of the diffs, then a manual walkthrough.)

> Vite filesystem note (RESOLVED): we chose `server.fs.allow` in
> [`vite.config.ts`](vite.config.ts) over copying the JSON into `ui/`. See §9
> "Foundation".
