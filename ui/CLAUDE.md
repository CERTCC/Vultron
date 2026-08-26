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

### Entry point and the two demo modes

`main.tsx` → `DemoSelector.tsx` toggles between two independent App roots:

| Mode | File | Source of truth |
|------|------|-----------------|
| **Multi-vendor** (`'multi'`, default) | `App-multivendor.tsx` | Scripted via `actions/` handlers; RM/EM/VFD/PXA defer to `protocol_states.json` (§9). |
| **Log Replay** (`'logreplay'`) | `App-logreplay.tsx` | Real case-ledger JSONL, validated against `protocol_states.json` (§5–6). |

These are **separate, parallel implementations** — they do **not** share one
engine. The multi-vendor demo is driven by handcrafted action handlers in
`src/actions/`; the log-replay demo is driven by parsing real `*.jsonl` logs
through `src/utils/`. Changes to one mode usually do **not** propagate to the
other. Know which mode you're touching.

> **History (2026-07):** three earlier modes were removed. The **Single-vendor**
> (`App.tsx`) and original scripted **Multi-vendor** demos were deleted as no
> longer useful, along with their exclusive handler/filter code. The
> **Multi-vendor (Validated)** fork — an isolated rewrite that deferred RM/EM/VFD/PXA
> to `protocol_states.json` (§9) — was then **promoted to be THE multi-vendor demo**:
> `App-multivendor-validated.tsx` → `App-multivendor.tsx`, and its `actions/validated/*`
> + `state/validated/actionFilters.ts` moved up to `actions/*` + `state/actionFilters.ts`.
> So today's `App-multivendor.tsx` is the protocol-deferring implementation; the
> old hardcoded one is gone (git history preserves it). No more fork, no `validated/`
> subdirs.

> Note: `App.css` defines its own `LANE_HEIGHT = 295` and inline node sizes,
> separate from `constants.ts` (`LANE_HEIGHT = 400`, `NODE_HEIGHT = 100`).
> Constants are **not** centralized across the apps — verify the file
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

- **Multi-vendor** — the protocol-deferring demo (formerly the "Validated" fork,
  promoted 2026-07 after the old hardcoded multi-vendor + single-vendor demos were
  deleted). Steps 1–5 of the deferral work are DONE (§9), including the CaseActor
  revision-response fix. Build + lint green. Embargo negotiation/revision paths are
  the highest-risk area to keep exercising.
- **Log Replay** — **rebuilt from scratch (2026-06)** on the new case-ledger
  format (§5–6), then extended for **multi-vendor + invite events (2026-07)** so
  it replays finder + N-vendor cases (two-actor, fvv). Build + lint green; the
  three sample buttons (two-actor, synthetic-violation, fvv) work, along with
  playback, collapsible lanes, hover tooltips (with violation explanations), and
  red ⚠️ violation flagging. **⏳ NOT yet handled: the new coordinator/handoff
  container scenarios (fcv, fvcv-*, fccv-*) — 5 new event verbs + coordinator/
  actor5 lanes + case-ownership handoff. This is the current open work — see §5
  "⏳ IN PROGRESS".** Validation stays: diff review + user's build/lint gate.

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
  from **`ui/src/sample-logs/`** (in-tree, so a fresh clone builds; see §7):
  **Load Sample Case** (`sample-logs/two-actor/`), **Load Violation Sample**
  (`sample-logs/synthetic/`, hand-authored illegal transitions), and **Load FVV
  Case** (`sample-logs/fvv/`, finder + 2 vendors). Manual `.jsonl` upload
  still works. Violation nodes render with a red outline + ⚠️; hovering any node shows
  a tooltip (label + detail bullets, plus the `violationReason` for flagged nodes).
  Node/arrow colors resolve per participant via `nodeColorsFor()` (any `vendor-N` →
  `getVendorNodeColors`); a single `context-stroke` arrowhead marker inherits the
  line color so arrows work for any vendor without a per-color marker. Lanes are
  collapsible (vertical only — nodes keep full width + label).

### The case-ledger format (current)

Each line is a `CaseLedgerEntry`: `{ logIndex, eventType, payloadSnapshot (an AS2
activity), entryHash, prevLogHash, receivedAt, … }`. The log records **state
SNAPSHOTS, not transitions** — the mapper recovers the trigger by diffing each
participant's snapshot against the previous one (RM/VFD via `object.rmState`/
`vfdState`; EM/PXA via `caseStatus` / `caseStatuses[0]`, or — for
`add_case_status_to_case` — `object.emState`/`pxaState` directly). A status `name`
like `"ACCEPTED VFD ACTIVE Pxa"` is a cross-check only — trust structured fields
(the bootstrap's CaseStatus `name="NONE pxa"` lies; its `emState` is ACTIVE).

> **⚠️ 2026-08 VOCABULARY SHIFT (done — mapper updated).** A merge from `main`
> changed the case-LIFECYCLE verbs (the per-participant/note/embargo/invite verbs
> are unchanged). The mapper + parser were updated to the new vocabulary; the
> committed fixtures were regenerated. Old→new mapping:
> - `offer_case_manager_role` → **`create_case`** (same roster + CaseStatus shape;
>   `handleCreateCase` handles both).
> - `submit_report` → **`add_report_to_case`** (`actor` = recorder/owner, finder =
>   `object.attributedTo`; `handleReport` handles both, node in the finder lane).
> - case-level EM/PXA now also arrives as first-class **`add_case_status_to_case`**
>   (`handleCaseStatus`; EM/PXA directly on `object`).
> - **`case_fully_closed`**, **`engage_case`**, **`add_case_participant`**,
>   **`accept_actor_recommendation`** — log-only (no machine change).
> - **`reject_invite_actor_to_case`** — invitee declines (`handleRejectInvite`;
>   "Declined Invite" node in the rejecter's lane).
>
> **Owner identification changed:** `create_case`'s `object.attributedTo` is the
> case-actor RECORDER, not the owner. `handleCreateCase` now derives the owner as
> the single roster host that is neither `finder` nor `caseactor` (fv → vendor-1,
> fcv → coordinator).
>
> **Case-actor sub-actor now carries an RM lifecycle.** The new ledger attributes
> the owner's case-management RM (RECEIVED→VALID→ACCEPTED) to the case-actor
> sub-actor URL (→ `caseactor` lane). Since the owner's own participant lane
> already carries that, `handleParticipantStatus` **ignores RM/VFD on the
> `caseactor` lane** to keep it `N/A` per §9 (case-level EM/PXA still apply).
>
> **Parser:** `actor6:` host → `vendor-3` (the fcvcv "vendor-deployer", mirroring
> `actor5`→`vendor-2`). `offer_case_manager_role`/`submit_report` are retained in
> the union for replaying older uploaded logs, but current fixtures no longer emit
> them.

### ✅ MOSTLY DONE (superseded 2026-08): coordinator scenarios + vocabulary shift

> **Status update (2026-08).** The GAP 1/2/3 work below (2026-07) was largely
> completed: the coordinator scenarios (fcv, fvcv-*, fccv-*) render, `coordinator`/
> `actor5` lanes exist, and the ADR-0026 suggest-actor overlay is in. Then a merge
> from `main` changed the case-ledger VOCABULARY (see the "⚠️ 2026-08 VOCABULARY
> SHIFT" box under §5) and added two scenarios (`fcv-reject`, `fcvcv`). The mapper
> + parser were updated and all 9 fixtures regenerated. The GAP notes below are
> retained as historical context; the handoff work (GAP 3) is still deferred.

**How to (re)generate the logs** (Docker, on the user's real machine — not in
this container): the exec bit on the script is not reliably preserved on OneDrive,
so invoke via `bash`:
`bash ./integration_tests/demo/run_multi_actor_integration_test.sh <s>` for `<s>`
in `fv fvv fcv fcv-reject fvcv-extension fvcv-handoff fccv-extension fccv-handoff
fcvcv` (the current 9; `devlogs/` accumulates old+new UUIDs across runs, so refresh
fixtures from the NEWEST case-actor copy per scenario). If `EOFError: marshal data
too short` appears, clear `__pycache__`/`*.pyc` (OneDrive-corrupted host `.pyc`
leaking via the bind-mount) and retry.

Allen standardized the container demos on an **F/V/C scenario-shape notation**
(F=Finder, V=Vendor, C=Coordinator) with `-extension` vs `-handoff` variants
(extension = original report receiver KEEPS case ownership and just recommends/
invites others; handoff = original receiver TRANSFERS ownership to another actor).
Each scenario is a container demo that writes JSONL to the gitignored
`devlogs/<scenario>/`.

**Ground-truth survey (2026-08 regeneration — 9 scenarios; entry counts + actor
hosts):** `actor5` = 2nd vendor host (→ `vendor-2`), `actor6` = vendor-deployer
host (→ `vendor-3`). The `case-actor` recorder is co-hosted on the owner's host.
| scenario | entries | actor hosts |
|---|---|---|
| `fv` | 22 | finder, vendor |
| `fvv` | 32 | finder, vendor, actor5 |
| `fcv` | 30 | finder, vendor, coordinator |
| `fcv-reject` | 22 | finder, vendor, coordinator |
| `fvcv-extension` | 44 | finder, vendor, coordinator, actor5 |
| `fvcv-handoff` | 42 | finder, vendor, coordinator, actor5 |
| `fccv-extension` | 42 | finder, vendor, coordinator, actor5 |
| `fccv-handoff` | 41 | finder, vendor, coordinator, actor5 |
| `fcvcv` | 57 | finder, vendor, coordinator, actor5, actor6 |

**New scenarios (2026-08):** `fcv-reject` (fcv path where the invited vendor
declines — `reject_invite_actor_to_case`) and `fcvcv` (five actors: finder,
coordinator, vendor, 2nd coordinator, 2nd vendor/deployer). Both are wired to
"Load …" buttons with a caveat badge and need visual verification.

**GAP 1 — unhandled event verbs.** The mapper's `handleEntry` switch handles 8
verbs; the new scenarios emit **5 more that currently hit the `default` branch and
render NO node (silently dropped):**
- `submit_report` — explicit report submission (old two-actor folded this into the
  offer seed; now first-class, `object.type = VulnerabilityReport`). Actor = finder.
- `accept_case_manager_role` — an actor accepts the CM/coordinator role (pairs with
  the existing `offer_case_manager_role`).
- `offer_actor_to_case`, `offer_case_participant`, `accept_offer_case_participant` —
  the **extension** flow's participant-onboarding handshake (distinct from the
  `invite_actor_to_case`/`accept_invite_actor_to_case` pair the fvv path uses).
Decide per verb whether it's a visible node, a seed/no-op, or folds into an existing
handler — mirror how `invite`/`accept_invite` were added.

**GAP 2 — unrecognized actor lanes.** `actorUrlToLaneId`
([caseLedgerParser.ts](src/utils/caseLedgerParser.ts)) knows only `finder`,
`vendor-N`, `caseactor`. The new hosts **`//coordinator:`** and **`//actor5:`** fall
through to `unknown` → dropped. Need lane ids + `makeParticipant` cases +
`LANE_INDEX`/`buildLaneIndex` ordering + colors for a coordinator (and to map
`actor5` — confirm whether it's "vendor-2" or a distinct role; in fvv it's the 2nd
vendor, in the C-scenarios it appears alongside a coordinator, so its role may be
scenario-dependent — VERIFY from each log's `actorParticipantIndex`/roles before coding).

**GAP 3 — case-ownership HANDOFF (hardest).** The `-handoff` scenarios transfer the
case-manager role BETWEEN actors mid-case (protocol events
`offer_case_ownership_transfer` / `accept_case_ownership_transfer` /
`reject_case_ownership_transfer` exist in the source; confirm exactly how they
surface in the handoff logs — the top-level `eventType` set above didn't obviously
include them, so they may be carried differently). The mapper currently assumes ONE
fixed `caseactor` lane for the whole case. Handoff breaks that assumption and likely
touches the lane model itself, plus the `rmState==='N/A'` "who is the coordinator"
marker used by `buildInviteAction` (§9). Scope this carefully against the real
handoff logs before coding — it's more than a new event handler.

**Suggested approach for the next session:** (1) re-read the actual logs in
`devlogs/{fcv,fvcv-*,fccv-*}/case-actor/*.jsonl` (ground truth — invariant tests
assert only a subset of verbs, don't rely on them); (2) extend the parser
(`LedgerEventType`, `LaneId`, `actorUrlToLaneId`) for coordinator/actor5 + the 5 new
verbs; (3) add mapper handlers; (4) tackle handoff's lane model last; (5) add
`sample-logs/` copies + "Load …" buttons for the scenarios that render cleanly, as
we did for fvv. Validation stays: hand-trace against the artifact + user runs
build/lint (no node in-container).

**Decisions taken (2026-07 session, confirmed with the user):**
- **actor5 → `vendor-2`.** The `actor5:` host is Vendor2's container (scenario
  source seeds it as `vendor2` and runs it through the vendor fix lifecycle), so it
  reuses the existing vendor-N machinery (`getVendorColor`, `vendorNumber`, the
  vendor-N `makeParticipant` branch) as `vendor-2` — no bespoke lane.
- **`coordinator` is its own lane, distinct from the `caseactor` recorder.** Lane
  identity is keyed on the HOST, never on CVD role. The `case-actor-…` recorder
  sub-actor keeps the always-bottom `caseactor` lane even when co-hosted with the
  coordinator (fcv/fccv). The `coordinator:` host's real participant (which can be
  CASE_OWNER and run `validate_report`) is the `coordinator` lane.
- **Role labels are STATIC this pass**, set once from each lane's first `cvdRole`
  snapshot. Making a role LABEL migrate between lanes is the deferred handoff work
  (below) — it's the only place CASE_OWNER actually moves (vendor→coordinator).
- **Suggest-actor trio → one "Actor Recommended" overlay node** in the coordinator
  lane (documented as mirroring ADR-0026 `_phase_coordinator_suggests_vendor2`); the
  other two verbs of the handshake become event-log lines. The actual join still
  renders via the existing `accept_invite` node.
- **Handoff (fvcv/fccv-handoff) DEFERRED.** No ledger verb / no state machine —
  ownership transfer is behavior-tree only (`ownership_transfer_tree.py`,
  TRIG-11-001/002, delivered actor→actor via inbox/outbox) and surfaces in the
  ledger ONLY as a `cvdRole` change (CASE_OWNER vendor→coordinator) + the case
  object's `attributedTo` flip. This is squarely a demo overlay (procedural rule,
  §9 boundary). Those scenarios will replay but not depict the transfer until built.

**Upstream quirks to raise with Allen (not UI bugs):**
1. In `fvcv-handoff` and `fccv-extension`, actor5's `ParticipantStatus.cvdRole` reads
   `["COORDINATOR"]` even though the scenario seeds it as `vendor2` and drives it
   through the vendor fix lifecycle. The UI is insulated (label derives from lane
   identity, defaulting to "Vendor 2", not from that field), but it looks like a
   scenario seed bug.
2. Invite entries are inconsistently populated: a DIRECT `invite_actor_to_case` gets
   a full payload (inviter/invitee/case), but the final invite of an ADR-0026
   suggest-actor join is emitted EMPTY (`{}`). So in the -extension scenarios the
   directly-invited coordinator shows an "Invite Sent" node while the recommended
   vendor does not (only Actor Recommended → Accept). See §6 quirk #8. Populating both
   would make the onboarding paths symmetric.

### ⚠️ Multi-Vendor demo — possible gaps surfaced by the coordinator JSONLs (2026-07, NOT yet acted on)

While extending Log Replay for the coordinator scenarios, three things surfaced that
the protocol-driven **Multi-Vendor** demo (`App-multivendor.tsx` + `actions/*` +
`state/actionFilters.ts`) may not model. All three are **procedural/role** concerns
(overlay territory per the §9 declarative-vs-procedural boundary, NOT artifact-deferral
gaps), so they're recorded for later, not fixed here. None is confirmed — they need a
read of `App-multivendor.tsx`/`actions/` to verify:
1. **A real Coordinator participant that can be CASE_OWNER and validate the report.**
   In `fcv`/`fccv-extension` the *coordinator* (a distinct participant, not the
   virtual caseactor) is the CASE_OWNER/receiver and runs `validate_report` — not the
   vendor. The Multi-Vendor roster is finder/vendor(s)/caseactor, where "caseactor" is
   the *virtual* coordinator; it likely has no notion of a real coordinator
   participant holding CASE_OWNER + an RM lifecycle.
2. **Case-ownership handoff** — CASE_OWNER migrating vendor→coordinator mid-case
   (see deferred handoff above). The demo almost certainly assumes a fixed owner.
3. **The suggest-actor handshake** (coordinator recommends → CaseActor forwards →
   owner approves → invite) — a multi-step onboarding distinct from the demo's direct
   invite path.

---

## 6. How the protocol validates the log — and the format's quirks

The mapper treats `protocol_states.json` (via `protocol.ts`) as the authority:
every RM/VFD/EM/PXA step derived from a log entry is checked with
`isLegalTransition`; the shortest legal trigger path between two snapshot states is
found by a small BFS (`triggerPath`). This is the §9 deferral idea applied to
replay rather than to the interactive demo.

**Three node annotations the mapper produces:**
- **Violation (red ⚠️, `violation`/`violationReason`)** — a derived trigger illegal
  from the shadow state. Per-participant RM/VFD: `triggerPath` returns null. Case-level
  EM/PXA (`applyCaseLevelForward`): reachable in *neither* direction (a mere backward
  reach = stale snapshot, ignored — see quirk 4). Forces the shadow to the log's value
  and keeps going.
- **Inferred step (amber ℹ️, `inferred`/`inferredNote`)** — a *tripwire*, not an error.
  Since the log records snapshots not transitions, a diff spanning >1 legal step means
  intermediate states weren't logged and the mapper GUESSED the path — which could mask
  an illegal 1-step jump bridgeable by a longer legal detour. Today's generator never
  emits multi-hop diffs (validate has its own `validate_report` verb; only ACCEPTED/CLOSED
  appear as RM status snapshots; VFD milestones logged singly), so this is **dormant** —
  it exists to surface the inference if generator granularity ever coarsens. Violation
  supersedes inferred on the same node. Exercised by
  `devlogs/synthetic/inferred-multistep-case-ledger.jsonl`.
- (no annotation) — a clean, single-step legal transition.

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
8. **Invites: two payload shapes (UPDATED 2026-08).** `invite_actor_to_case` appears
   in two forms. (a) EMPTY `payloadSnapshot` (`{}`, no attribution) — the older
   two-actor/fvv logs, a leading placeholder before each populated invite in the
   coordinator scenarios, AND the final invite of an ADR-0026 recommend-path join
   (see below). These are log-only; the join is shown by the accept. (b) POPULATED —
   the coordinator scenarios' direct invites: `actor` = the case-actor recorder,
   `object` = the invitee (id/name), `target` = the case with `target.attributedTo` =
   the **real inviter** (case owner/manager). `handleInvite` renders an "Invite Sent"
   node in the INVITER's lane (from `target.attributedTo`, NOT `actor`). Either way
   `accept_invite_actor_to_case` carries `actor` = the joining actor and emits the
   "Accept Invite" node that seeds its report-receipt state (`handleAcceptInvite`).
   **Structural quirk (flag for Allen):** a directly-invited actor gets a populated
   invite, but an actor onboarded via the suggest-actor handshake
   (`offer_actor_to_case`) gets an EMPTY invite — so in the -extension scenarios the
   recommended vendor's onboarding renders as Actor Recommended → Accept (no "Invite
   Sent" node), while the directly-invited coordinator renders Invite Sent → Accept.
   No info is lost (the recommend node names the invitee), but populating both invites
   upstream would make the two paths symmetric.

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
- `node_modules/.bin` tools (eslint, tsc, vite) work via `npm run *`.
- **Two different log locations — don't confuse them:**
  - **`ui/src/sample-logs/`** — the COMMITTED sample ledgers the Log Replay
    "Load …" buttons import via `?raw`. In-tree (tracked in git), so a fresh clone
    builds without needing the container demo. Contains one dir per scenario —
    `fv/` (happy path; formerly `two-actor/`), `fvv/`, `fcv/`, `fcv-reject/`,
    `fvcv-extension/`, `fvcv-handoff/`, `fccv-extension/`, `fccv-handoff/`,
    `fcvcv/`, plus `synthetic/` (hand-authored violation + inferred-multistep
    fixtures + README). Each button imports the **case-actor** copy. Filenames are
    per-run UUIDs, so regenerating means updating the `?raw` import paths in
    `App-logreplay.tsx`.
  - **`devlogs/` (repo root)** — GITIGNORED runtime output. The container
    multi-actor demo bind-mounts and writes fresh `*-case-ledger.jsonl` here on
    every run (`DEVLOGS_DIR`, docker-compose-multi-actor.yml). NOT tracked; a fresh
    clone has none. It was the original home of the samples until 2026-07, when the
    committed fixtures were moved into `ui/src/sample-logs/` so the `ui/` build no
    longer depends on a gitignored dir (a colleague hit "no Logs to follow" on a
    clean checkout). For **manual upload** testing you can still point the uploader
    at your own freshly-generated `devlogs/…` files.
- **`jq`** is available (`/usr/bin/jq`) — use it to inspect `*.jsonl` logs in either location.

---

## 8. Working norms for this subproject

- Identify **which of the two App modes** (Multi-vendor / Log Replay) a request
  targets before editing; they don't share an engine.
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

**JSON shape:** `{ _README, rm, em, vfd, pxa, embargo_viability }`. Each machine =
`{ initial, states[], transitions[{trigger,source,dest}] }`. `embargo_viability`
= `{ _note, patterns[{pattern, flags[]}] }` — a **cross-machine** rule the four
per-machine tables can't express (see below). The exporter is deterministic (no
timestamps, fixed order) so the drift test can do a byte-exact compare.

**Cross-machine embargo viability (2026-07).** "Can a new embargo be
proposed/accepted, or an existing one continue?" is NOT a per-machine fact — it
depends on the combined CS state (the protocol's MUST NOT propose/accept a new
embargo once P/X/A, negotiating.md). The four per-machine tables can't represent
a dependency *between* machines, so this rule was historically hand-coded as an
`isPublic` overlay in the demos — and drifted (Finder/Vendor used P||X||A, the
Case Actor used P-only, so after attacks the Case Actor still offered "Propose
Embargo" but no one could respond). Fixed by making it artifact-driven end to end:
- **Exporter** emits `embargo_viability` from
  [`vultron/core/case_states/patterns/embargo.py`](../vultron/core/case_states/patterns/embargo.py)
  (`_EMBARGO_VIABILITY`), as CS-state (`vVfFdDpPxXaA`) regex patterns → viability
  flags (`START_OK`/`NO_START`/`VIABLE`/`NOT_VIABLE`/`CAUTION`).
- **`protocol.ts`** exposes `canStartEmbargo(pxaToken)` / `embargoViable(pxaToken)`,
  matching the assembled CS state against those patterns. VFD is pinned to base
  `vfd` (the fix-deployed `..Dpxa`→NO_START rule is only a SHOULD-NOT per RFC-2119,
  so the demo must leave it *possible*; wildcarding VFD enforces exactly the hard
  P/X/A MUST-NOT and no more — decided with the maintainer).
- **`actionFilters.ts`** — all three participant functions gate embargo
  propose/accept via these helpers (no more per-function `isPublic`; can't drift).
- **`caseLedgerMapper.ts`** — Log Replay flags a violation if a log advances EM
  into PROPOSED/ACTIVE/REVISE while the CS state forbids it (embargo negotiated in
  a public/exploited/attacked state).

This is the pattern to follow for any future cross-machine rule: **put it in the
artifact (extend the exporter), read it in `protocol.ts`, defer to it in the
demos** — never hand-code a second copy in the UI.

**The boundary of "defer to the artifact" — declarative vs. procedural rules
(2026-07).** The artifact-deferral principle applies to possibilities the protocol
models **declaratively** — enumerable state machines (RM/EM/VFD/PXA) and pattern
tables (`embargo_viability`). Those have a single canonical definition in the
protocol source, so the exporter can capture them and the demo can defer wholesale.
It does NOT apply — and structurally *cannot* — to rules the protocol models
**procedurally**, i.e. as behavior-tree logic. The clearest case: the **CASE_MANAGER
(Case Actor / coordinator) role.** There is no one place defining "what a
CASE_MANAGER can do"; `CVDRole.CASE_MANAGER` is *checked* situationally across many
BTs (note attach, embargo teardown, message routing, auto-close, participant
counting…). Related: there is **no case-level `closed` flag** — `CaseStatus` holds
only `em_state`/`pxa_state`; case closure is per-participant, and "case done" is a
DERIVED fold over participants' RM states (the protocol's own
`_all_participants_closed()` BT node in
[`lifecycle.py`](../vultron/core/behaviors/status/nodes/lifecycle.py), which
excludes CASE_MANAGER). Such rules legitimately stay as **explicit, documented demo
overlays** (the bucket notes/invites/phase-routing are already in). When you write
one, comment it as a deliberate mirror of the specific protocol source (file +
rule) so it's traceable, and do NOT try to export a scraped copy — an export of a
procedural rule is *more* fragile than an honest overlay (it breaks silently if the
BT is refactored). Concrete instance: `buildInviteAction` in
[`actionFilters.ts`](src/state/actionFilters.ts) mirrors `lifecycle.py`'s
CASE_MANAGER exclusion via the demo's `rmState === 'N/A'` coordinator marker. Only
revisit exporting if a future protocol change gives the rule a declarative home.

**Optional, deferred:** add `data/json/**` to the `paths:` triggers in
`.github/workflows/python-app.yml` to also catch hand-edits of the artifact.

### `ui/`-side refactor — protocol deferral (DONE, now the shipping demo)

This refactor was originally built inside an isolated "Validated" fork so the
proven demo wouldn't break; as of 2026-07 the fork was **promoted to be the sole
multi-vendor demo** (`App-multivendor.tsx` + `actions/*` + `state/actionFilters.ts`;
the old hardcoded original and the `validated/` subdirs are gone — §1 History).
So the deferral code described below now lives at the canonical paths, not under
`*/validated/*`. Decision (with the maintainer): **moderate deferral depth** —
handlers compute destinations from the JSON; filters derive RM/EM/VFD legality
from it; non-machine rules (embargo gating, notes, invites, visuals) stay as an
explicit overlay. NOT a full generic engine.

> **Path note:** the `src/actions/validated/*` and `src/state/validated/actionFilters.ts`
> references throughout the rest of §9 are historical — read them as `src/actions/*`
> and `src/state/actionFilters.ts`. There is no longer a "frozen original" to drift
> from; the deferral code IS the demo.

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
  **NOTE (2026-07):** this file is currently **not imported anywhere** — the
  handlers/filters call `requireNextState`/`isLegalTransition` directly rather
  than going through this table. It's kept as reference documentation of the
  action→trigger mapping; delete it if that reference value isn't wanted.

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
(The old hardcoded multi-vendor demo carried the same latent gap; it has since
been deleted, so this is now the only implementation and the gap is fixed here.)

**Gotchas discovered (carry forward):**
- **`DECLINED` RM pseudo-state — REMOVED (Step 5).** It is
  NOT a real RM state in the JSON; it was a demo invention for declined invites
  and was in fact never *written* anywhere (no decline action/handler exists —
  invited vendors enter directly at RM.RECEIVED), so its guards/filters were inert.
  The `rmState === 'DECLINED'` filter guard and the four `!== 'DECLINED'`
  consequence-filter clauses were deleted. A vendor "declining" a report is, at
  the protocol level, `invalidate` (→INVALID→CLOSED) or `defer` (→DEFERRED→CLOSED)
  — both already modeled. (The old hardcoded demo still carried DECLINED; it has
  been deleted, so nothing carries it anymore.)
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

### File layout (post-promotion, 2026-07)

The fork is gone — there is now a single multi-vendor implementation at the
canonical paths:
- `App-multivendor.tsx` — the demo (the deferral-based code, formerly
  `App-multivendor-validated.tsx`). Imported only by `DemoSelector.tsx`.
- `src/actions/{finder,vendor,caseActor,invite,external}Actions.ts` — its
  handlers (import `../state/*`, `../protocol`, `../types`, `../constants`).
- `src/state/actionFilters.ts` — its filters (import `./participantHelpers`,
  `../types`, `../protocol`).

These `actions/*.ts` + `state/actionFilters.ts` are imported ONLY by
`App-multivendor.tsx`; `App-logreplay.tsx` uses only `state/participantHelpers`.

**Shared, treat as stable:** `participantHelpers.ts`, `stateUpdaters.ts`,
`protocol.ts`, `constants.ts`, `types.ts`, `components/` — used by BOTH surviving
demos (Log Replay's mapper imports `protocol.ts`, `constants.ts`, `types.ts`,
`participantHelpers.ts`). A change here affects both; check both before editing.

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
