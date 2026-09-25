# Vultron Log Replay

## Overview

**Log Replay** is one of the two modes in the Vultron UI demo (the other is the
illustrative Multi-Vendor simulation — see [README.md](README.md)). It reads
real **case-ledger JSONL** files produced by the container-based Vultron demos
and replays them on the same swimlane timeline, so you can watch an actual
protocol run rather than a simulation.

Unlike the Multi-Vendor mode, Log Replay does not simulate anything: it
reconstructs each state transition from the logged snapshots and **validates it
against the protocol** (`data/json/protocol_states.json`, via
[src/protocol.ts](src/protocol.ts)), flagging any illegal transition it finds in
the data.

## How to Use

1. **(Optional) generate fresh logs** with a container demo (run on a machine
   with Docker — not required if you use the bundled samples):

   ```bash
   bash integration_tests/demo/run_multi_actor_integration_test.sh fvv
   ```

   This writes per-actor `*-case-ledger.jsonl` files under the gitignored
   `devlogs/<scenario>/` directory (e.g. `devlogs/fvv/finder/…-case-ledger.jsonl`).

2. **Start the UI:**
   ```bash
   cd ui
   npm run dev
   ```

3. **Load a case:**
   - Click **Log Replay** in the top selector bar.
   - Use one of the **Load …** buttons to open a bundled sample, **or** click the
     upload control and select one or more `*-case-ledger.jsonl` files.
   - The timeline renders in `logIndex` order.

### Bundled samples

The **Load …** buttons import committed ledgers from
[src/sample-logs/](src/sample-logs/) (in-tree, so a fresh clone works without
the container demo). Each scenario directory holds the case-actor copy of the
ledger; `synthetic/` holds hand-authored fixtures that exercise violation and
inferred-multistep flagging.

## Pipeline

```
DemoSelector
  └─ Log Replay → App-logreplay.tsx
                     │
        utils/caseLedgerParser.ts  →  utils/caseLedgerMapper.ts  →  timeline
```

- **[caseLedgerParser.ts](src/utils/caseLedgerParser.ts)** — `parseCaseLedger()`
  reads one `CaseLedgerEntry` per line; `normalizeLedger()` dedups by `entryHash`
  and sorts by `logIndex`; `actorUrlToLaneId()` maps actor URLs to lanes
  (`finder`, `vendor-N`, `coordinator`, `caseactor`).
- **[caseLedgerMapper.ts](src/utils/caseLedgerMapper.ts)** —
  `buildTimelineFromCaseLedger()` pre-scans the ledger to fix lane order, then
  walks entries once while maintaining a **shadow protocol state**. The log
  records state *snapshots*, so the mapper diffs each snapshot against the
  previous one to recover the trigger, validates it against the protocol, and
  either advances (legal) or flags `violation: true` (illegal) and continues.
- **[App-logreplay.tsx](src/App-logreplay.tsx)** — renders the timeline with the
  same decision/consequence + `causedBy` grammar as the interactive mode;
  violation nodes get a red outline + ⚠️, and hovering shows a tooltip.

## Event Types

The case-ledger vocabulary (the mapper's `handleEntry` switch). Verbs not listed
are recorded in the event log without changing machine state.

| Event type | Visualization |
|---|---|
| `create_case` | Seeds the case roster + initial `CaseStatus` (no node) |
| `add_report_to_case` / `submit_report` | Report node in the Finder's lane |
| `validate_report` | Report validated (RM `RECEIVED → VALID`) |
| `add_participant_status` | Per-participant RM/VFD state snapshot |
| `add_case_status_to_case` | Case-level EM/PXA snapshot |
| `invite_actor_to_case` / `accept_invite_actor_to_case` | Invite sent / accepted (adds a vendor lane) |
| `reject_invite_actor_to_case` | "Declined Invite" node in the rejecter's lane |
| `offer_actor_to_case` / `offer_case_participant` / `accept_offer_case_participant` | Suggest-actor onboarding handshake |
| `offer_case_ownership_transfer` / `accept_case_ownership_transfer` | Ownership offer → accept node pair |
| `close_case` | Self-declaratory Leave; "Close Case" node in the closer's lane (RM → `CLOSED`) |

> The exhaustive, up-to-date handler list — including scenario coverage,
> attribution quirks, and the 2026-08 vocabulary shift (`offer_case_manager_role`
> → `create_case`, `submit_report` → `add_report_to_case`, etc.) — lives in
> [CLAUDE.md](CLAUDE.md) §5–6. Consult it before changing the mapper.

## Supported Log Fields

From each `CaseLedgerEntry`:

- `logIndex` — ordering key (entries are sorted by this, **not** `receivedAt`)
- `eventType` — the event verb
- `entryHash` / `prevLogHash` — dedup + chain integrity
- `payloadSnapshot` — the ActivityStreams activity, including:
  - `payloadSnapshot.actor` — who performed the action
  - `payloadSnapshot.object.rmState` / `.vfdState` — per-participant RM/VFD
  - `payloadSnapshot.object.caseStatus` / `caseStatuses[0]` — case-level EM/PXA
    (or `object.emState` / `object.pxaState` directly on `add_case_status_to_case`)

## Notes

- The pipeline reuses the shared visualization components, so replay looks
  identical to the interactive mode.
- No changes to the protocol or the container demos are needed to visualize a run.
- `protocol_states.json` is the single source of truth for what transitions are
  legal — the mapper validates against it rather than hardcoding the rules.
