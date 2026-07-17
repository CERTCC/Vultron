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
| **Log Replay** (`'logreplay'`) | `App-logreplay.tsx` | Real case-ledger JSONL, validated against `protocol_states.json` (§5–6). |

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

### How to run it (READ THIS FIRST if you're new to the session)

```bash
cd ui
npm run dev        # Vite dev server, prints a localhost URL (usually http://localhost:5173)
```

- **No `npm install` needed normally** — `ui/node_modules` is present in the
  working tree. Only reinstall if `package.json` deps changed (recent bumps:
  React 19, Vite 8, TS 6) or Vite errors on a missing module.
- **No backend, no Python** — everything is client-side. The demo imports the
  committed `data/json/protocol_states.json` directly (via `server.fs.allow`;
  §9). `npm run dev` never needs the exporter or a server.
- **Switching modes:** the mode toggle is at the top of the page
  ([`DemoSelector.tsx`](src/DemoSelector.tsx)). It's plain in-memory React state
  (`useState`, default `'multi'`) — **not** persisted to URL or localStorage, so
  a page refresh returns to Multi-vendor. To make a mode the startup default,
  change the `useState` initial value.
- **IMPORTANT — the agent CANNOT run any of this in-container.** There is no
  `node`/`npm`/`python` on PATH here (only `jq` + `node_modules/.bin` shims that
  still need a node runtime). So `npm run dev/build/lint` and the Python exporter
  **must be run by the user** in their real environment — hand them exact
  commands, don't attempt them. Agent-side verification = careful diff review +
  the build/lint gate the user runs. (See "Tooling constraint" at the bottom.)

### Where each mode stands (testing status, as of this note)

- **Single-vendor / Multi-vendor** — the proven, stable demos. Not under active
  change; treat as reference behavior.
- **Multi-vendor (Validated)** — protocol-deferral fork, **Steps 1–5 DONE**
  (§9). Last change: the CaseActor revision-response fix (§9). Build + lint were
  green and the fix was confirmed by manual walkthrough. Status: *initial work
  complete, manual testing underway* — embargo negotiation/revision paths are
  the highest-risk area to keep exercising.
- **Log Replay** — **rebuilt from scratch (2026-06)** on the new case-ledger
  format (§5–6), then extended for **multi-vendor + invite events (2026-07)** so
  it replays 3-party cases (finder + N vendors), not just two-actor. Build + lint
  are green and all three sample buttons (two-actor, synthetic-violation, fvv)
  have been exercised in the browser. Playback, collapsible lanes, hover tooltips
  (with violation explanations), and the red ⚠️ violation flagging all work.
  Remaining validation happens by careful diff review + the user's build/lint
  gate (no node in-container).

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

## 5. Log Replay pipeline (`src/utils/`) — RESTARTED, grounded in the protocol

> **2026-06 restart.** The log generator was refactored and the replay demo was
> rebuilt from scratch on the **new case-ledger format**, grounded in the protocol
> source of truth (`protocol.ts` → `protocol_states.json`, §9). The OLD pipeline
> (`jsonlParser.ts` + `logEventMapper.ts`) has been **deleted** (git history
> preserves it) — nothing imported it. The "known bugs" / "data contract
> gaps" that used to fill §5–6 described the OLD format and are obsolete (see git
> history).

**Why the old pipeline was scrapped (not just patched) — two reasons:**
1. **The log format changed underneath it.** The generator's new vocabulary is
   the case-ledger verbs listed below; the old parser expected `submit_report` /
   `engage_case` / `add_participant_status`, which the new logs no longer emit —
   so it literally couldn't read them.
2. **Its design was structurally broken.** The old `buildTimelineFromLogs`
   guessed decision/consequence clusters by bucketing entries into 1-second
   windows (`Math.floor(receivedAt/1000)`); it only knew how to cluster two
   hardcoded verbs, dropped everything else through an early-return that never
   advanced the X column (→ overlapping nodes), emitted no `causedBy` (→ no
   arrows, §2), and never deduped. These came from *inferring* structure the log
   didn't carry — unfixable by patching. The new pipeline gets ordering, dedup,
   and causality from the format + a linear shadow-state walk instead of guessing.

**The core conceptual shift (old → new):** the old mapper *transcribed* whatever
the log said. The new mapper **reconstructs transitions from snapshots and
validates each against the protocol** — the log records STATE SNAPSHOTS (not
transitions), so the mapper diffs each snapshot vs. the previous shadow to
recover the trigger, then asks `../protocol` if that trigger is legal (legal →
advance; illegal → flag `violation:true` + keep going). The same
`protocol_states.json` that *drives* the Validated interactive demo now *judges*
the real logs — it's the §9 deferral idea applied to replay.

**New pipeline:** `caseLedgerParser.ts` → `caseLedgerMapper.ts` → `App-logreplay.tsx`.

- **`caseLedgerParser.ts`** — `parseCaseLedger(content)` → one `CaseLedgerEntry`
  per line; `normalizeLedger(entries)` dedups by `entryHash` and sorts by `logIndex`
  (NOT `receivedAt` — several entries share a wall-clock second). `actorUrlToLaneId(url)`
  maps actor URLs to lanes: `case-actor`→`caseactor` tested FIRST (the Case Actor's
  URL is itself a `//vendor:` URL), then `//finder:`→`finder`, then `//vendorN:`→
  `vendor-N` (regex; bare `//vendor:`→`vendor-1`). **Multi-vendor:** `LaneId` is
  `'finder' | 'vendor-${number}' | 'caseactor' | 'unknown'`, so N vendors are supported.
- **`caseLedgerMapper.ts`** — `buildTimelineFromCaseLedger(entries)` first
  **pre-scans the whole ledger** (`buildLaneIndex`) to discover the full participant
  roster and assign stable lane indices (finder=0, vendors in ascending numeric
  order, caseactor always last), then pre-creates every lane. Because replay sees
  every entry up front, indices are fixed immediately — **no mid-stream lane reflow**
  like the interactive multi-vendor demo needs on invite. It then walks entries once
  in `logIndex` order maintaining a **shadow protocol state** (per-participant RM/VFD
  keyed by lane id, case-level EM/PXA). For each entry it derives the protocol
  trigger(s) and **validates each against `../protocol`**: legal → advance via
  `nextState`; illegal → flag the node `violation:true` (+ a human-readable
  `violationReason`), log a `PROTOCOL VIOLATION` line, and force the shadow to the
  log's snapshot so replay continues (the protocol is the *validating function*; see
  §6). Emits the standard decision/consequence + `causedBy` + same-X grammar (§2).
- **`App-logreplay.tsx`** — three "Load …" buttons import committed ledgers via `?raw`
  (repo-root files served through `server.fs.allow`, the same trick `protocol.ts`
  uses for `protocol_states.json`): **Load Sample Case** (`devlogs/two-actor/`),
  **Load Violation Sample** (`devlogs/synthetic/`, hand-authored illegal transitions),
  and **Load FVV Case** (`devlogs/fvv/`, finder + 2 vendors). Manual `.jsonl` upload
  still works. Violation nodes render with a red outline + ⚠️; hovering any node shows
  a tooltip (label + detail bullets, plus the `violationReason` for flagged nodes).
  Node/arrow colors resolve per participant via `nodeColorsFor()` (any `vendor-N` →
  `getVendorNodeColors`); a single `context-stroke` arrowhead marker inherits the
  line color so arrows work for any vendor without a per-color marker. Lanes are
  collapsible (vertical only — nodes keep full width + label).

### The case-ledger format (current)

Each line is a `CaseLedgerEntry`: `{ logIndex, eventType, payloadSnapshot (an AS2
activity), entryHash, prevLogHash, receivedAt, … }`. Eight `eventType` verbs:
`offer_case_manager_role`, `validate_report`, `add_note_to_case`,
`add_participant_status_to_participant`, `remove_embargo_event_from_case`,
`close_case`, and (multi-vendor) `invite_actor_to_case` +
`accept_invite_actor_to_case`. The log records **state SNAPSHOTS, not transitions** — the mapper
recovers the trigger by diffing each participant's snapshot against the previous one
(RM/VFD via `object.rmState`/`vfdState`; EM/PXA via `caseStatus` /
`caseStatuses[0]` structured fields). A status `name` like `"ACCEPTED VFD ACTIVE
Pxa"` is a cross-check only — trust structured fields (the offer's CaseStatus
`name="NONE pxa"` lies; its `emState` is ACTIVE).

---

## 6. How the protocol validates the log — and the format's quirks

The mapper treats `protocol_states.json` (via `protocol.ts`) as the authority:
every RM/VFD/EM/PXA step derived from a log entry is checked with
`isLegalTransition`; the shortest legal trigger path between two snapshot states is
found by a small BFS (`triggerPath`). This is the §9 deferral idea applied to
replay rather than to the interactive demo.

Quirks of the current sample the mapper handles explicitly (carry forward):

1. **Mid-stream start.** The two-actor sample begins with EM already **ACTIVE** at
   `logIndex 0` (no submit/propose/accept-embargo events). The mapper **seeds** the
   shadow from the first snapshot it sees rather than from `initialState()`. A
   participant's first snapshot is a *seed*, never a transition (you can't validate
   what has no source).
2. **`validate_report` carries no status snapshot.** The vendor is pre-seeded
   `RM=RECEIVED` at case-creation (the receipt seed) so `validate` is a legal
   RECEIVED→VALID step — seeding it at ACCEPTED would falsely flag a violation.
3. **One entry can pack several advances.** `logIndex 4` shows the vendor at
   `"ACCEPTED VFd"` — both RM `accept` (VALID→ACCEPTED) and VFD `fix_is_ready`
   (Vfd→VFd). The mapper applies both shadow advances but emits **one** node,
   labeled by the primary (RM > VFD > PXA > EM), with all changes in the bullets.
4. **Stale embedded case status.** `logIndex 8` (a finder status) still carries
   `caseStatus.emState=ACTIVE` *after* the embargo terminated at `logIndex 7`.
   Case-level EM/PXA are applied **forward-only** — a participant-local snapshot may
   advance PXA but must never regress the verb-driven EM; a regress is logged and
   ignored.
5. **Notes lack `inReplyTo` linkage.** Both sample notes have `inReplyTo:null`, so
   question-vs-answer is a heuristic (first unanswered note = question; the next
   note by a *different* actor while one is pending = its answer).
6. **`actor` ≠ subject.** On `offer_case_manager_role` / `close_case` the recorded
   `actor` is the Case Actor while `object.attributedTo` is the vendor. The mapper
   puts the decision node in the **actor/recorder** lane (caseactor) but reads
   "whose machine" from `object.attributedTo`.
7. **Verb order isn't fixed (multi-vendor).** In `devlogs/fvv/`, `validate_report`
   is at `logIndex 0` — *before* the offer at `logIndex 1` (two-actor had the offer
   first). So the vendor may already be advanced (RM=VALID) by the time `handleOffer`
   runs. The receipt seeds in `handleOffer` are therefore guarded on
   `shadow.rm[id] === undefined` (NOT on `seededRm`), so an already-advanced state is
   never regressed. Don't reorder those seeds back to unconditional writes.
8. **Invites: the `accept` creates the lane, not the `invite`.** `invite_actor_to_case`
   has an **empty `payloadSnapshot`** in the sample (no attribution), so it only logs;
   `accept_invite_actor_to_case` carries `actor`=joining vendor and creates the lane +
   seeds its report-receipt state + emits an "Accept Invite" node (`handleAcceptInvite`).

Still genuinely **absent** from the format (would further improve replay; raise with
the log developer): an explicit `causedBy`/correlationId (the mapper infers
causality from the entry itself, which suffices for now), and a `loggedBy`
perspective field. **Per-folder copies are NOT always byte-identical:** `two-actor/`'s
three copies are (one shared ledger), but `fvv/`'s four copies (finder, vendor,
vendor2, case-actor) differ per perspective while carrying the same 19 `logIndex`
entries. The "Load …" buttons load a single canonical copy (the case-actor/coordinator
view) rather than relying on `entryHash` dedup across differing copies.

---

## 7. Environment / tooling constraints (important)

- **`node` and `python3` are NOT available** in this dev environment. Do not try
  to run JSONL through node/python scripts.
- **`jq`** is available (`/usr/bin/jq`) — use it to inspect `*.jsonl` logs.
- `node_modules/.bin` tools (eslint, tsc, vite) work via `npm run *`.
- `devlogs/` holds the committed sample ledgers each Log Replay button loads:
  - `two-actor/{finder,vendor,case-actor}/` — the happy-path sample; all three
    copies byte-identical (one shared ledger).
  - `synthetic/violations-case-ledger.jsonl` — hand-authored fixture with two
    deliberate illegal transitions (see `synthetic/README.md`).
  - `fvv/{finder,vendor,vendor2,case-actor}/` — finder + 2 vendors; the four
    copies DIFFER per perspective but carry the same 19 entries (see §6). Traced
    clean (no violations) despite being unverified when added.
  Each button imports the **case-actor** copy via `?raw`.

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

**The 5-step plan (Steps 1–5 done):**
1. ✅ Make the artifact importable (vite + tsconfig).
2. ✅ `protocol.ts` — typed wrapper over the JSON.
3. ✅ `protocolActions.ts` — action-ID → machine-trigger bridge.
4. ✅ Refactored **all** forked handlers (`actions/validated/*.ts`) to compute
   destination states via `requireNextState(...)` instead of hardcoding
   `{ rmState: 'VALID' }` etc. Node/consequence/event-log code left untouched.
   **Every** machine-state write now derives from `protocol_states.json` — RM
   (validate/accept/defer/invalidate/close), VFD (fix_is_ready/fix_is_deployed),
   EM (propose/accept/reject/terminate across vendor+finder+caseActor), and PXA
   (public_becomes_aware/exploit_made_public/attacks_are_observed). The only
   remaining machine-state *literals* are the report-receipt composite seeds (see
   gotchas). Verified: each call's source state is filter-guaranteed; EM calls
   read the unmutated `state.emState`. Output is behaviorally identical to the
   pre-refactor demo (see "no behavioral bug" note) except where it removed an
   illegal transition (publish-while-PROPOSED, below).
5. ✅ Refactored the **forked** filters
   ([`state/validated/actionFilters.ts`](src/state/validated/actionFilters.ts))
   so RM/EM/VFD/PXA gating comes from `isLegalTransition(...)`; non-machine
   rules (embargo-before-participation / late-joiner consent, `isPublic`
   early-termination, pending-note reply gating, invite availability, `phase`
   routing, EM label selection) stay as an explicit overlay. See "Step 5" below.

**Step 4 — what the refactor did and did NOT change (read before Step 5):**
- **No behavioral bug was fixed by the RM/VFD pass.** Every RM/VFD trigger has a
  single destination regardless of source (e.g. `accept` → ACCEPTED from both
  VALID and DEFERRED), so the old hardcoded literals were already correct for all
  reachable sources. The value of the refactor is (a) **source-of-truth deferral**
  — destinations now follow `protocol_states.json` automatically — and (b) a
  **guard**: `requireNextState` throws loudly if a filter/handler ever drift into
  an illegal source. Don't describe it as a correctness fix.
- **EM `propose`/`reject` DO have source-dependent destinations**, so there the
  derivation is genuinely load-bearing (propose: NONE→PROPOSED vs ACTIVE→REVISE;
  reject: PROPOSED→NONE vs REVISE→ACTIVE).
- **One real correctness change: publish-while-PROPOSED.** When a vuln becomes
  public while EM is merely `PROPOSED`, the protocol treats it as an implicit
  **`reject`** (PROPOSED→NONE), NOT `terminate` — `terminate`/EXITED is reserved
  for embargoes that had actually become ACTIVE (verified against
  [`em.py`](../vultron/core/states/em.py) and `transitions.md:291-293`; the JSON
  represents this correctly). The old demo reached the right end-state (NONE) but
  via an invented `terminate`-from-PROPOSED that the machine forbids. Now both
  `handleVendorNotifyPublished` and `handleTriggerExploit` route ACTIVE/REVISE →
  `terminate` and PROPOSED → `reject`, both via `requireNextState`.
- **Finder now starts at RM.ACCEPTED, not RECEIVED** (in the fork only). Per the
  formal protocol (states.md start-state table: Finder/Reporter starts at
  `(A, N, pxa)`; "The Secret Lives of Finders"), a Finder's
  START→RECEIVED→VALID→ACCEPTED traversal happens *privately* before they contact
  anyone — that private prioritization IS the Finder→Reporter transition. So the
  only observable RM lifecycle for the Finder is ACCEPTED ⇄ DEFERRED → CLOSED.
  `handleSubmitReport` now seeds `ACCEPTED`, which also makes the later `close`
  legal (close is NOT permitted from RECEIVED — that was the bug this fixed).
  `handleFinderCloseCase` is therefore now a clean `requireNextState('rm', …,
  'close')` like the vendor handlers, not an exception.
- **`handleTriggerExploit` / vendor publish are composites of legal steps.**
  Exploit publication auto-implies public awareness (pxa→PXa, not the bare
  `exploit_made_public` pxa→pXa), modeled as `exploit_made_public` THEN
  `public_becomes_aware` — each computed from the artifact, composing to the
  demo's exact original mapping. `handleTriggerAttacks` is a single
  `attacks_are_observed` step (attacks do NOT imply public awareness — no forced P).

**Step 5 — what the filter refactor did and did NOT change:**
- **Behavior-identical, by construction.** Every machine-state literal swapped to
  `isLegalTransition(...)` was equivalent to the literal for all reachable states
  (verified case-by-case against `protocol_states.json`). The gating logic is now
  *derived from the artifact* rather than hardcoded, matching what Step 4 did for
  handlers. The one intentional behavior change is the DECLINED removal (below),
  which is also a no-op because DECLINED was never written.
- **Pattern used:** `isLegalTransition(machine, currentState, trigger) && <overlay>`.
  Where the demo deliberately surfaces a transition in only *some* machine-legal
  source states (a happy-path narrowing — e.g. CaseActor proposes a revision only
  from ACTIVE, not via REVISE re-propose; vendor `defer` only from VALID, not from
  ACCEPTED), the narrowing stays an explicit `=== STATE` overlay layered on the
  legality check and is commented as such.
- **PXA legality IS the publicity check.** `!pxaState.includes('X')` ≡
  `isLegalTransition('pxa', s, 'exploit_made_public')`, `!includes('A')` ≡
  `attacks_are_observed`, and `!includes('P')` ≡ `public_becomes_aware` — verified
  from the artifact's source lists. The external/publish filters now read legality
  directly instead of substring-testing the PXA string.
- **Stayed as overlay (no machine slot — correct to leave literal):** late-joiner
  embargo consent (`em.accept` is NOT legal from ACTIVE — accepting an existing
  ACTIVE embargo is per-participant consent, not a case-level transition), the
  RM→VFD coupling `canProgressVFD = rmState === 'ACCEPTED'`, `isPublic`
  early-termination, pending-note reply gating, invite availability, `phase`
  routing, and EM accept/reject label selection between negotiation phases.

**CaseActor revision-response overlay bug (found while exercising Step 5; FIXED).**
Symptom: after the CaseActor *accepted* an embargo revision, its
"Accept/Reject Embargo Revision" buttons kept reappearing. Root cause was a
**pre-existing overlay gap, not the filter refactor** — the EM machine
([`em.py`](../vultron/core/states/em.py) / `protocol_states.json`) is a single
**case-level** state with no per-participant acceptance or consensus, so
"who has responded to this proposal" is unavoidably demo overlay for *every*
role. That overlay tracks each participant's response in `embargoAccepted` and
resets it on each new proposal — but the **CaseActor was never wired in**:
its filter lacked the `!embargoAccepted` guard the Finder/Vendor filters have,
its accept-revision handler never set the flag, and the propose-revision
handlers never reset it. *Reject* self-healed (it fires `REVISE → ACTIVE`, so
the button vanished via `emState`); *accept* did not, because a CaseActor accept
leaves EM in `REVISE` pending real consensus. Fix = complete the overlay
uniformly: add `!caseActor.embargoAccepted` to the filter
([actionFilters.ts](src/state/validated/actionFilters.ts) caseactor REVISE block),
set it in `handleCaseActorAcceptRevision`, and reset it in
`handleFinderProposeRevision` / `handleVendorProposeRevision`. The flag is
**UI-only** — deliberately kept OUT of `allParticipantsAccepted` (finder + active
vendors only), preserving "CaseActor facilitates, doesn't vote." The EM
transition itself still comes from the artifact via `requireNextState('em', …)`.
The frozen original carries the same latent gap; left untouched per fork isolation.

**Gotchas discovered (carry forward):**
- **`DECLINED` RM pseudo-state — REMOVED from the Validated fork (Step 5).** It is
  NOT a real RM state in the JSON; it was a demo invention for declined invites
  and was in fact never *written* anywhere (no decline action/handler exists —
  invited vendors enter directly at RM.RECEIVED), so its guards/filters were inert.
  The fork deleted the `rmState === 'DECLINED'` filter guard and the four
  `!== 'DECLINED'` consequence-filter clauses. A vendor "declining" a report is, at
  the protocol level, `invalidate` (→INVALID→CLOSED) or `defer` (→DEFERRED→CLOSED)
  — both already modeled. The **frozen original** still carries DECLINED
  ([actionFilters.ts:237](src/state/actionFilters.ts#L237)); leave it until the
  fork replaces the original.
- **VFD `vfd→Vfd`** (and **RM `START→RECEIVED`**) have no standalone user
  action — the demo sets vendors straight to `Vfd`/`RECEIVED` at report receipt
  ([finderActions.ts:26](src/actions/finderActions.ts#L26),
  [inviteActions.ts:49](src/actions/inviteActions.ts#L49)). Those triggers are
  folded into the `submit-report` / invite composites.
- **Report-receipt composite seeds remain literals (intentional, post-Step-4).**
  After Step 4, the ONLY hardcoded machine-state writes left in
  `actions/validated/*.ts` are the receipt seeds: vendor-1 / invited vendors set
  straight to `{ rmState:'RECEIVED', vfdState:'Vfd' }`
  ([validated/finderActions.ts:34](src/actions/validated/finderActions.ts#L34),
  [validated/inviteActions.ts:48](src/actions/validated/inviteActions.ts#L48)),
  and the Finder seeded to `rmState:'ACCEPTED'`
  ([validated/finderActions.ts:33](src/actions/validated/finderActions.ts#L33)).
  These are composite *seeds*, not single transitions — the Finder's ACCEPTED in
  particular collapses a private START→RECEIVED→VALID→ACCEPTED traversal that has
  no single `requireNextState` trigger — so they stay literal by design. Don't
  "finish the job" by forcing them through `requireNextState`.

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

### Lint / build status
- **MUST be re-verified by the user** after the replay restart — the container has
  no node/npm (see below), so `npm run build` / `npm run lint` were NOT run here.
- The 3 pre-existing lint errors lived in the OLD replay pipeline
  (`utils/jsonlParser.ts` `no-explicit-any` ×2, `utils/logEventMapper.ts`
  `no-useless-assignment`). Those files have now been **deleted** (git history
  preserves them), which should clear those 3 errors. The new `caseLedgerParser.ts` /
  `caseLedgerMapper.ts` avoid `any` and dead assignments by design.
- Replay-restart files to expect green: `utils/caseLedgerParser.ts`,
  `utils/caseLedgerMapper.ts`, `App-logreplay.tsx`, `types.ts` (one additive
  optional `violation?` field). The old parked `handleLoadDemoLogs` was REMOVED and
  replaced by `handleLoadSample` (wired to a real button), so the `void`-reference
  hack is gone.
- The 4 `react-hooks/exhaustive-deps` warnings in App.tsx / both multivendor apps
  are unrelated and untouched.

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
