/**
 * Validating log-replay mapper.
 *
 * Converts a normalized case ledger (see `caseLedgerParser.ts`) into a `DemoState`
 * of timeline events, GROUNDED IN THE PROTOCOL SOURCE OF TRUTH. As it walks the
 * ledger in `logIndex` order it maintains a *shadow* protocol state and, for every
 * trigger it derives from the log, asks `../protocol` whether that transition is
 * legal from the current shadow state:
 *
 *   - legal   → advance the shadow via `requireNextState`; if the computed
 *               destination disagrees with the log's snapshot, record a discrepancy.
 *   - illegal → flag the produced node `violation: true`, log a PROTOCOL VIOLATION
 *               line, and force the shadow to the log's snapshot value so replay
 *               continues from the log's reality (decided behavior: annotate + keep going).
 *
 * This is the "validating function": the Multi-Vendor (Validated) demo's protocol
 * truth (`protocol_states.json` via `../protocol`) judges the events in the log.
 *
 * Key realities of the current ledger this mapper is built around (see ui/CLAUDE.md
 * — note §5–6 there describe the OLD format and are historical):
 *   - The log records STATE SNAPSHOTS, not transitions. We diff each snapshot
 *     against the participant's previous shadow value to recover the trigger(s).
 *   - A case may start MID-STREAM (the sample begins with EM already ACTIVE). We
 *     therefore SEED shadow state from the first snapshot observed, not from
 *     `initialState()`. A first observation is a seed (no transition, no validation).
 *   - One ledger entry = one visual moment = one node, even when it carries several
 *     machine advances (e.g. RM accept + VFD fix-ready in the same entry). The node
 *     is labeled by the primary change; all advances are listed in its consequences
 *     and the event log.
 */

import type { DemoState, ParticipantState, TimelineEvent, StepSnapshot } from '../types'
import {
  PARTICIPANT_COLORS,
  PARTICIPANT_ROLES,
  INITIAL_X_POSITION,
  X_INCREMENT,
  getVendorColor,
} from '../constants'
import {
  isLegalTransition,
  legalTriggers,
  nextState,
  machineStates,
  canStartEmbargo,
  embargoViable,
  type MachineName,
} from '../protocol'
import {
  actorUrlToLaneId,
  type CaseLedgerEntry,
  type CaseStatusSnapshot,
  type LaneId,
} from './caseLedgerParser'

// ---------------------------------------------------------------------------
// Shadow protocol state
// ---------------------------------------------------------------------------

interface ShadowState {
  /** Per-participant RM state, keyed by lane id ('finder' | 'vendor-1'). */
  rm: Record<string, string>
  /** Per-participant VFD state, keyed by lane id. */
  vfd: Record<string, string>
  /** Case-level EM. */
  emState: string
  /** Case-level PXA. */
  pxaState: string
  /** Lane ids whose RM has been seeded (so a matching snapshot isn't a transition). */
  seededRm: Set<string>
  /** Lane ids whose VFD has been seeded. */
  seededVfd: Set<string>
  /** Lane id of whoever asked the currently-unanswered note, or null. */
  pendingQuestionBy: string | null
}

// ---------------------------------------------------------------------------
// Token parsing for status `name` strings
// ---------------------------------------------------------------------------

// Build token-membership sets from the artifact so they never drift from the
// protocol. The four machines' state names are mutually disjoint and the VFD/PXA
// ladders are case-sensitive, so a token maps to exactly one machine.
const RM_TOKENS = new Set(machineStates('rm'))
const VFD_TOKENS = new Set(machineStates('vfd'))
const EM_TOKENS = new Set(machineStates('em'))
const PXA_TOKENS = new Set(machineStates('pxa'))

interface ParsedTokens {
  rm?: string
  vfd?: string
  em?: string
  pxa?: string
}

/**
 * Tokenize a status `name` like "ACCEPTED VFD ACTIVE Pxa" into its machine
 * components by exact, case-sensitive set membership. Used only as a cross-check;
 * first-class fields (`object.rmState`/`vfdState`, `caseStatus.emState`/`pxaState`)
 * are authoritative — the `name` is unreliable for EM (see CaseStatusSnapshot).
 */
function parseStatusName(name: string | undefined): ParsedTokens {
  const out: ParsedTokens = {}
  if (!name) return out
  for (const tok of name.trim().split(/\s+/)) {
    if (RM_TOKENS.has(tok)) out.rm = tok
    else if (VFD_TOKENS.has(tok)) out.vfd = tok
    else if (EM_TOKENS.has(tok)) out.em = tok
    else if (PXA_TOKENS.has(tok)) out.pxa = tok
  }
  return out
}

// ---------------------------------------------------------------------------
// Protocol graph helper: minimal trigger path between two states
// ---------------------------------------------------------------------------

/**
 * BFS the machine's transition graph for the shortest trigger sequence taking
 * `prev` → `next`. Returns `[]` if they're equal, or `null` if `next` is
 * unreachable from `prev` (which the caller treats as a protocol violation).
 *
 * Most real diffs are a single adjacent step; this is a safety net for entries
 * that jump more than one transition in one snapshot.
 */
function triggerPath(machine: MachineName, prev: string, next: string): string[] | null {
  if (prev === next) return []
  const queue: Array<{ state: string; path: string[] }> = [{ state: prev, path: [] }]
  const visited = new Set<string>([prev])
  while (queue.length > 0) {
    const { state, path } = queue.shift()!
    for (const trigger of legalTriggers(machine, state)) {
      const dest = nextState(machine, state, trigger)
      if (dest === null) continue
      const nextPath = [...path, trigger]
      if (dest === next) return nextPath
      if (!visited.has(dest)) {
        visited.add(dest)
        queue.push({ state: dest, path: nextPath })
      }
    }
  }
  return null
}

// ---------------------------------------------------------------------------
// Participant roster helpers
// ---------------------------------------------------------------------------

/** The 1-based vendor number from a `vendor-N` lane id (e.g. 'vendor-2' → 2). */
function vendorNumber(laneId: string): number {
  const m = laneId.match(/^vendor-(\d+)$/)
  return m ? parseInt(m[1], 10) : 1
}

/**
 * A lane-index map keyed by lane id. Built once per replay by pre-scanning the
 * whole ledger (see `buildLaneIndex`): finder is top (0), vendors follow in
 * numeric order, and the Case Actor is always forced to the bottom — regardless
 * of when each actor first appears in the log. Because replay sees every entry
 * up front, indices are assigned deterministically and never need the mid-stream
 * reflow the interactive multi-vendor demo performs on invite.
 */
type LaneIndexMap = Record<string, number>

function makeParticipant(
  laneId: Exclude<LaneId, 'unknown'>,
  laneIndex: number,
  visible: boolean
): ParticipantState {
  if (laneId === 'finder') {
    return {
      id: 'finder',
      name: 'Finder',
      role: PARTICIPANT_ROLES.finder,
      color: PARTICIPANT_COLORS.finder,
      rmState: 'START',
      vfdState: 'vfd',
      embargoAccepted: false,
      hasPublished: false,
      hasClosed: false,
      visible,
      laneIndex,
    }
  }
  if (laneId === 'caseactor') {
    return {
      id: 'caseactor',
      name: 'Case Actor',
      role: PARTICIPANT_ROLES.caseactor,
      color: PARTICIPANT_COLORS.caseactor,
      rmState: 'N/A',
      vfdState: 'N/A',
      embargoAccepted: false,
      hasPublished: false,
      hasClosed: false,
      visible,
      laneIndex,
    }
  }
  if (laneId === 'coordinator') {
    // A real coordinator PARTICIPANT (2026-07 scenarios), distinct from the
    // virtual `caseactor` recorder above. Unlike the recorder, it has a genuine
    // RM/VFD lifecycle (in fcv/fccv-extension it's the CASE_OWNER and validates
    // the report; it also closes at case end), so it starts at the machine
    // initials like the finder/vendor and is seeded from its first status
    // snapshot — NOT the 'N/A' sentinel.
    return {
      id: 'coordinator',
      name: 'Coordinator',
      role: PARTICIPANT_ROLES.coordinator,
      color: PARTICIPANT_COLORS.coordinator,
      rmState: 'START',
      vfdState: 'vfd',
      embargoAccepted: false,
      hasPublished: false,
      hasClosed: false,
      visible,
      laneIndex,
    }
  }
  // vendor-N
  const n = vendorNumber(laneId)
  return {
    id: laneId,
    name: n === 1 ? 'Vendor' : `Vendor ${n}`,
    role: PARTICIPANT_ROLES.vendor,
    color: getVendorColor(n),
    rmState: 'START',
    vfdState: 'vfd',
    embargoAccepted: false,
    hasPublished: false,
    hasClosed: false,
    visible,
    laneIndex,
  }
}

/**
 * Create a lane if it doesn't exist yet (robust to mid-stream / subset ledgers).
 * New lanes are created NOT-YET-JOINED (`visible: false`): the pre-scan assigns a
 * stable lane index up front, but a participant only becomes visible — and thus
 * only starts receiving consequence nodes (see `consequenceLanes`) — at the point
 * it actually joins the case (`markJoined`). This is what stops consequence nodes
 * from being drawn into a lane before that participant is part of the case.
 */
function ensureParticipant(
  participants: Map<string, ParticipantState>,
  laneId: LaneId,
  laneIndex: LaneIndexMap
): void {
  if (laneId === 'unknown') return
  if (!participants.has(laneId)) {
    // Created not-yet-joined; membership is granted separately via `markJoined`.
    participants.set(laneId, makeParticipant(laneId, laneIndex[laneId] ?? participants.size, false))
  }
}

/**
 * Mark a lane as having JOINED the case (visible from now on). Idempotent. This is
 * the membership signal that gates consequence-node emission (`consequenceLanes`)
 * and lane rendering: a participant receives consequence nodes only from the event
 * at which it joins onward. Called at the moments a participant actually enters the
 * case — the offer roster at case creation, an invitee at accept-invite — and
 * defensively whenever a lane is the decision-maker or the subject of a status.
 */
function markJoined(participants: Map<string, ParticipantState>, laneId: LaneId): void {
  if (laneId === 'unknown') return
  const p = participants.get(laneId)
  if (p && !p.visible) participants.set(laneId, { ...p, visible: true })
}

/**
 * Pre-scan every entry to discover the full participant roster and assign stable
 * lane indices: finder=0, then vendors in ascending numeric order, then the Case
 * Actor last. Reads each entry's `actor`, its subject (`object.attributedTo`),
 * and any `actorParticipantIndex` keys so no participant is missed regardless of
 * which verb first mentions them.
 */
function buildLaneIndex(entries: CaseLedgerEntry[]): LaneIndexMap {
  const lanes = new Set<string>()
  const note = (url?: string | null) => {
    const id = actorUrlToLaneId(url)
    if (id !== 'unknown') lanes.add(id)
  }
  for (const entry of entries) {
    const snap = entry.payloadSnapshot
    note(snap?.actor)
    note(snap?.object?.attributedTo)
    const api = snap?.object?.actorParticipantIndex
    if (api) for (const url of Object.keys(api)) note(url)
  }

  const vendors = Array.from(lanes)
    .filter((id) => id.startsWith('vendor-'))
    .sort((a, b) => vendorNumber(a) - vendorNumber(b))

  const map: LaneIndexMap = {}
  let idx = 0
  if (lanes.has('finder')) map.finder = idx++
  for (const v of vendors) map[v] = idx++
  // The real coordinator participant sits below the vendors but above the
  // caseactor recorder lane.
  if (lanes.has('coordinator')) map.coordinator = idx++
  // caseactor is always last; assign the final index without a dangling increment.
  if (lanes.has('caseactor')) map.caseactor = idx
  return map
}

/** Visible, not-yet-closed lanes other than `decisionLaneId`, in lane order. */
function consequenceLanes(
  participants: Map<string, ParticipantState>,
  decisionLaneId: string
): ParticipantState[] {
  return Array.from(participants.values())
    .filter((p) => p.visible && !p.hasClosed && p.id !== decisionLaneId)
    .sort((a, b) => a.laneIndex - b.laneIndex)
}

// ---------------------------------------------------------------------------
// Node synthesis
// ---------------------------------------------------------------------------

/**
 * Build a decision node in `decisionLaneId`'s lane plus paler consequence nodes
 * (same x, `causedBy = decision.id`) in every other active lane. This reproduces
 * the Validated demo's decision/consequence visual grammar (ui/CLAUDE.md §2) and,
 * because we now know the originating entry, every event is a proper cluster — so
 * the arrows the old replay mapper never drew now render.
 */
function synthesizeCluster(
  entry: CaseLedgerEntry,
  participants: Map<string, ParticipantState>,
  decisionLaneId: string,
  x: number,
  label: string,
  decisionConsequences: string[],
  consequenceLabel: string,
  consequenceBullets: (lane: ParticipantState) => string[],
  violation: boolean,
  violationReason?: string,
  inferred?: { note: string }
): TimelineEvent[] {
  // Emitting a decision node means this lane is acting → it has joined the case.
  // This defensive flip covers any lane that produces a node without going through
  // an explicit join handler (e.g. a status/note before its formal join in a
  // reordered ledger); the consequence fan-out below then correctly includes it.
  markJoined(participants, decisionLaneId as LaneId)
  const decision = participants.get(decisionLaneId)
  if (!decision) return []

  const baseTs = new Date(entry.receivedAt).getTime()
  const decisionId = `${entry.id}-decision`
  const nodes: TimelineEvent[] = [
    {
      id: decisionId,
      actor: decision.name,
      participantId: decisionLaneId,
      label,
      x,
      lane: decision.laneIndex,
      type: 'decision',
      consequences: decisionConsequences,
      timestamp: baseTs,
      violation: violation || undefined,
      violationReason: violation ? violationReason : undefined,
      inferred: inferred ? true : undefined,
      inferredNote: inferred?.note,
    },
  ]

  let offset = 1
  for (const lane of consequenceLanes(participants, decisionLaneId)) {
    nodes.push({
      id: `${entry.id}-${lane.id}-consequence`,
      actor: lane.name,
      participantId: lane.id,
      label: consequenceLabel,
      x,
      lane: lane.laneIndex,
      type: 'consequence',
      consequences: consequenceBullets(lane),
      causedBy: decisionId,
      timestamp: baseTs + offset,
    })
    offset++
  }

  return nodes
}

// ---------------------------------------------------------------------------
// Per-entry handling
// ---------------------------------------------------------------------------

/** Read the case-level snapshot off an entry, if present (offer/close or embedded). */
function readCaseStatus(entry: CaseLedgerEntry): CaseStatusSnapshot | null {
  const obj = entry.payloadSnapshot?.object
  if (!obj) return null
  if (obj.caseStatus) return obj.caseStatus
  if (obj.caseStatuses && obj.caseStatuses.length > 0) return obj.caseStatuses[0]
  return null
}

interface MapResult {
  nodes: TimelineEvent[]
  logLines: string[]
}

/**
 * Result of applying a case-level (EM/PXA) snapshot to the shadow.
 *   - `null`                    → no-op (empty/equal snapshot) or a STALE snapshot
 *                                 (an earlier state we've already passed); ignored.
 *   - `{ ..., violation:false }` → a legal forward advance was applied.
 *   - `{ ..., violation:true }`  → an ILLEGAL jump: the snapshot is reachable
 *                                 neither forward nor backward from the current
 *                                 state, so it is not on any legal trajectory.
 *                                 The shadow is forced to the snapshot (replay
 *                                 continues from the log's reality) and the caller
 *                                 flags the node.
 */
interface CaseLevelResult {
  trigger: string
  from: string
  to: string
  violation: boolean
  reason?: string
  inferredNote?: string  // set when the legal forward path was >1 hop (intermediate
                         // case-level states were not logged; the path was inferred)
}

/**
 * Apply a single case-level machine snapshot. Legal forward advances are applied;
 * STALE snapshots (reachable backward — a participant's embedded `caseStatus` can
 * lag, e.g. the sample's finder status still reads EM=ACTIVE after the embargo
 * terminated) are ignored forward-only. A snapshot reachable in NEITHER direction
 * is a genuine protocol violation (e.g. EM jumping NONE→EXITED, or PXA regressing)
 * — distinguished from staleness by testing for a reverse legal path — and is
 * flagged rather than silently ignored.
 */
function applyCaseLevelForward(
  machine: 'em' | 'pxa',
  shadow: ShadowState,
  snapshot: string | undefined,
  logLines: string[]
): CaseLevelResult | null {
  if (!snapshot) return null
  const current = machine === 'em' ? shadow.emState : shadow.pxaState
  if (snapshot === current) return null

  const path = triggerPath(machine, current, snapshot)
  if (path === null || path.length === 0) {
    // No forward path. Distinguish a stale (backward-reachable) snapshot from a
    // genuinely illegal jump (reachable in neither direction) via a reverse probe.
    const reverse = triggerPath(machine, snapshot, current)
    if (reverse && reverse.length > 0) {
      // Stale: snapshot is an earlier state on our path. Keep shadow, no violation.
      logLines.push(
        `  ↳ ignored stale ${machine.toUpperCase()} snapshot "${snapshot}" (shadow stays "${current}")`
      )
      return null
    }
    // Illegal: not on any legal trajectory from `current`. Force shadow + flag.
    logLines.push(
      `  ↳ PROTOCOL VIOLATION: ${machine.toUpperCase()} has no legal path "${current}" → "${snapshot}"; forcing shadow`
    )
    if (machine === 'em') shadow.emState = snapshot
    else shadow.pxaState = snapshot
    return {
      trigger: 'illegal',
      from: current,
      to: snapshot,
      violation: true,
      reason:
        `${machine.toUpperCase()} cannot reach ${snapshot} from ${current}: no sequence of ` +
        `legal ${machine.toUpperCase()} transitions connects them (in either direction), so the ` +
        `case-level ${machine === 'em' ? 'embargo' : 'publicity'} state jumped illegally.`,
    }
  }

  // Apply the (usually single-step) forward path.
  let from = current
  let lastTrigger = path[0]
  for (const trigger of path) {
    const dest = nextState(machine, from, trigger)!
    from = dest
    lastTrigger = trigger
  }
  if (machine === 'em') shadow.emState = snapshot
  else shadow.pxaState = snapshot
  const inferredNote = path.length > 1
    ? `${machine.toUpperCase()} ${current} → ${snapshot} was not a single logged step: the ` +
      `mapper inferred the legal path [${path.join(' → ')}] because intermediate case-level ` +
      `states were not recorded.`
    : undefined
  return { trigger: lastTrigger, from: current, to: snapshot, violation: false, inferredNote }
}

// Friendly labels for triggers, keyed by machine:trigger.
const TRIGGER_LABEL: Record<string, string> = {
  'rm:validate': 'Validate Report',
  'rm:invalidate': 'Invalidate Report',
  'rm:accept': 'Accept Report',
  'rm:defer': 'Defer Report',
  'rm:close': 'Close Case',
  'vfd:vendor_becomes_aware': 'Vendor Aware',
  'vfd:fix_is_ready': 'Fix Ready',
  'vfd:fix_is_deployed': 'Fix Deployed',
  'pxa:public_becomes_aware': 'Vuln Public',
  'pxa:exploit_made_public': 'Exploit Public',
  'pxa:attacks_are_observed': 'Attacks Observed',
  'em:terminate': 'Embargo Terminated',
}

// ---------------------------------------------------------------------------
// Main entry point
// ---------------------------------------------------------------------------

/**
 * Build a replay `DemoState` from normalized ledger entries (see
 * `normalizeLedger`). Walks entries once, in order; emits one node-cluster per
 * meaningful entry and increments the visual column ONLY when a cluster is
 * emitted — so seed-only / no-op entries leave no x-gap (this is the bug the old
 * mapper had: an early `return` that skipped the increment, ui/CLAUDE.md §5 #2).
 */
export function buildTimelineFromCaseLedger(entries: CaseLedgerEntry[]): DemoState {
  const participants = new Map<string, ParticipantState>()
  // Pre-scan the whole ledger for the full roster + stable lane ordering, then
  // pre-create every participant. Replay knows all actors up front, so lanes get
  // fixed indices immediately (finder, vendors…, caseactor) with no mid-stream
  // reflow. Handlers still call ensureParticipant defensively for subset ledgers.
  const laneIndex = buildLaneIndex(entries)
  for (const id of Object.keys(laneIndex)) {
    ensureParticipant(participants, id as LaneId, laneIndex)
  }
  const shadow: ShadowState = {
    rm: {},
    vfd: {},
    emState: 'NONE',
    pxaState: 'pxa',
    seededRm: new Set(),
    seededVfd: new Set(),
    pendingQuestionBy: null,
  }
  const timelineEvents: TimelineEvent[] = []
  const eventLog: string[] = []
  const stepSnapshots: StepSnapshot[] = []
  let visualEventIndex = 0

  const timeLabel = (entry: CaseLedgerEntry) =>
    new Date(entry.receivedAt).toLocaleTimeString()

  // Snapshot the current shadow (deep-copied) for step-by-step panel replay.
  const snapshotShadow = (): StepSnapshot => ({
    rm: { ...shadow.rm },
    vfd: { ...shadow.vfd },
    emState: shadow.emState,
    pxaState: shadow.pxaState,
  })

  for (const entry of entries) {
    const x = INITIAL_X_POSITION + visualEventIndex * X_INCREMENT
    const result = handleEntry(entry, participants, shadow, x, laneIndex)

    // Keep the actor panels in sync with the shadow after each entry.
    syncParticipantsToShadow(participants, shadow)

    if (result.nodes.length > 0) {
      timelineEvents.push(...result.nodes)
      eventLog.push(`[${timeLabel(entry)}] ${result.nodes[0].label}`)
      for (const line of result.logLines) eventLog.push(line)
      visualEventIndex++
      // Record the state as of this visual step. `timelineEvents` may hold several
      // nodes per step (decision + consequences), so snapshots are indexed by
      // visual STEP, not by node index — the app maps a node's step to its snapshot.
      stepSnapshots.push(snapshotShadow())
    } else if (result.logLines.length > 0) {
      // Seed-only / no-op entries: record the note without consuming a column.
      for (const line of result.logLines) eventLog.push(line)
    }
  }

  timelineEvents.sort((a, b) => a.x - b.x || (a.timestamp ?? 0) - (b.timestamp ?? 0))

  return {
    phase: 'replay',
    participants,
    emState: shadow.emState,
    pxaState: shadow.pxaState,
    timelineEvents,
    eventLog,
    nextXPosition: INITIAL_X_POSITION + visualEventIndex * X_INCREMENT,
    invitedVendors: new Set<string>(),
    hasPendingFinderNote: shadow.pendingQuestionBy !== null,
    stepSnapshots,
  }
}

/** Push the shadow's machine states onto the participant records (for the panels). */
function syncParticipantsToShadow(
  participants: Map<string, ParticipantState>,
  shadow: ShadowState
): void {
  for (const [id, p] of participants) {
    const rm = shadow.rm[id]
    const vfd = shadow.vfd[id]
    const updates: Partial<ParticipantState> = {}
    if (rm !== undefined && rm !== p.rmState) updates.rmState = rm
    if (vfd !== undefined && vfd !== p.vfdState) updates.vfdState = vfd
    if (rm === 'CLOSED' && !p.hasClosed) updates.hasClosed = true
    if (Object.keys(updates).length > 0) participants.set(id, { ...p, ...updates })
  }
}

/** Dispatch one ledger entry to its handler. */
function handleEntry(
  entry: CaseLedgerEntry,
  participants: Map<string, ParticipantState>,
  shadow: ShadowState,
  x: number,
  laneIndex: LaneIndexMap
): MapResult {
  switch (entry.eventType) {
    // Case bootstrap. `create_case` is the current verb; `offer_case_manager_role`
    // is the pre-2026-08 verb kept for replaying older uploaded logs. Both carry
    // the same roster + CaseStatus shape and share one handler.
    case 'create_case':
    case 'offer_case_manager_role':
      return handleCreateCase(entry, participants, shadow, x, laneIndex)
    case 'validate_report':
      return handleValidateReport(entry, participants, shadow, x, laneIndex)
    case 'add_note_to_case':
      return handleNote(entry, participants, shadow, x, laneIndex)
    case 'add_participant_status_to_participant':
      return handleParticipantStatus(entry, participants, shadow, x, laneIndex)
    case 'add_case_status_to_case':
      return handleCaseStatus(entry, participants, shadow, x, laneIndex)
    case 'remove_embargo_event_from_case':
      return handleRemoveEmbargo(entry, participants, shadow, x, laneIndex)
    case 'close_case':
      return handleCloseCase(entry, participants, shadow, x, laneIndex)
    case 'case_fully_closed':
      // Derived "all participants have closed" marker (no object, no machine
      // change). The per-participant close_case nodes already depict closure, so
      // this is log-only — it mirrors the protocol's derived fold over participant
      // RM states (lifecycle.py `_all_participants_closed`), not a distinct action.
      return { nodes: [], logLines: ['  ↳ case_fully_closed (all participants closed)'] }
    case 'engage_case':
      // The case owner formally engages the case. EM/PXA are already seeded at
      // create_case, so there is no machine change to apply — log-only.
      return { nodes: [], logLines: ['  ↳ engage_case (owner engaged the case)'] }
    case 'invite_actor_to_case':
      return handleInvite(entry, participants, shadow, x, laneIndex)
    case 'accept_invite_actor_to_case':
      return handleAcceptInvite(entry, participants, shadow, x, laneIndex)
    case 'reject_invite_actor_to_case':
      return handleRejectInvite(entry, participants, shadow, x, laneIndex)
    case 'add_case_participant':
      // Roster bookkeeping: the case manager records a participant on the case.
      // The visible join renders via accept_invite; here we only ensure the lane
      // exists (defensive for a subset ledger). Log-only, no column consumed.
      return handleAddCaseParticipant(entry, participants, shadow, x, laneIndex)
    case 'submit_report':
    case 'add_report_to_case':
      // `add_report_to_case` is the current verb (actor = recorder/owner, finder =
      // object.attributedTo); `submit_report` is the older verb (actor = finder).
      // handleReport resolves the finder lane from whichever is present.
      return handleReport(entry, participants, shadow, x, laneIndex)
    case 'accept_case_manager_role':
      // The recorder (case-actor sub-actor) accepts the case-manager role it was
      // offered at case creation. Bookkeeping that pairs with the case bootstrap
      // (already rendered as "Case Created"); no machine change, so log-only.
      return { nodes: [], logLines: ['  ↳ accept_case_manager_role (Case Manager role accepted)'] }
    case 'accept_actor_recommendation':
      // A leg of the ADR-0026 suggest-actor handshake (fcvcv): an actor accepts a
      // recommendation to bring another actor onto the case. Folded into the
      // "Actor Recommended" overlay (handleOfferActorToCase); log-only here.
      return { nodes: [], logLines: ['  ↳ accept_actor_recommendation (recommendation accepted)'] }
    case 'offer_actor_to_case':
      // First leg of the ADR-0026 suggest-actor handshake (Coordinator recommends a
      // participant). Rendered as a single "Actor Recommended" node; the other two
      // legs are folded in as log lines (see handleOfferActorToCase).
      return handleOfferActorToCase(entry, participants, shadow, x, laneIndex)
    case 'offer_case_participant':
      // Second leg: CaseActor forwards the recommendation to the Case Owner.
      // Folded into the single "Actor Recommended" node above; log-only here.
      return { nodes: [], logLines: ['  ↳ offer_case_participant (recommendation forwarded to Case Owner)'] }
    case 'accept_offer_case_participant':
      // Third leg: Case Owner approves the recommendation. The actual join still
      // renders via the subsequent invite/accept_invite pair; log-only here.
      return { nodes: [], logLines: ['  ↳ accept_offer_case_participant (Case Owner approved recommendation)'] }
    default:
      return { nodes: [], logLines: [`  ↳ unhandled eventType "${entry.eventType}"`] }
  }
}

// --- create_case (or legacy offer_case_manager_role) → case-created bootstrap -

/**
 * Case bootstrap. Handles the current `create_case` verb and the legacy
 * `offer_case_manager_role` (identical roster/CaseStatus shape). Seeds the
 * case-level EM/PXA and the per-participant report-receipt state, then emits the
 * "Case Created" cluster in the caseactor recorder lane.
 */
function handleCreateCase(
  entry: CaseLedgerEntry,
  participants: Map<string, ParticipantState>,
  shadow: ShadowState,
  x: number,
  laneIndex: LaneIndexMap
): MapResult {
  const logLines: string[] = []
  const obj = entry.payloadSnapshot?.object

  // Build the roster from the case's actor→participant index (its keys are the
  // actor URLs). Fall back to the recorded actor if the index is absent. Lanes
  // are normally pre-created (buildLaneIndex), so these are defensive no-ops.
  const roster = new Set<LaneId>()
  if (obj?.actorParticipantIndex) {
    for (const url of Object.keys(obj.actorParticipantIndex)) roster.add(actorUrlToLaneId(url))
  }
  roster.add(actorUrlToLaneId(entry.payloadSnapshot?.actor))
  for (const laneId of roster) ensureParticipant(participants, laneId, laneIndex)
  // Ensure the standard lanes exist even if the index was sparse. NOTE: vendor-1 is
  // created defensively but is NOT auto-joined here — in fcv/fccv the primary vendor
  // is a LATE joiner absent from the offer roster (the coordinator is the receiver),
  // so it must stay hidden until its accept-invite. Only the actual roster joins now.
  ensureParticipant(participants, 'finder', laneIndex)
  ensureParticipant(participants, 'vendor-1', laneIndex)
  ensureParticipant(participants, 'caseactor', laneIndex)

  // Grant membership to the participants actually present at case creation: the
  // offer roster (finder + receiver/owner + the case-actor recorder). These are the
  // only lanes that should receive this event's consequence nodes; late joiners
  // (invited vendors/coordinators) become visible at their own accept-invite.
  for (const laneId of roster) markJoined(participants, laneId)
  markJoined(participants, 'finder')
  markJoined(participants, 'caseactor')

  // Seed case-level EM/PXA from the offer's structured CaseStatus (trust the
  // structured fields, not its `name` — the sample's name "NONE pxa" lies).
  const cs = readCaseStatus(entry)
  if (cs?.emState) {
    shadow.emState = cs.emState
    logLines.push(`  ↳ seeded case EM = ${cs.emState} (from offer)`)
  }
  if (cs?.pxaState) {
    shadow.pxaState = cs.pxaState
    logLines.push(`  ↳ seeded case PXA = ${cs.pxaState} (from offer)`)
  }

  // Report-receipt seed: the case RECEIVER/OWNER enters at RM.RECEIVED so the
  // later `validate_report` is a legal RECEIVED→VALID step (seeding at ACCEPTED
  // would make `validate` illegal). The receiver is the primary vendor in
  // two-actor/fvv/fvcv-extension but the COORDINATOR in fcv/fccv-extension.
  //
  // Identifying the owner (2026-08): `create_case`'s `object.attributedTo` is the
  // case-actor RECORDER, not the owner (the legacy `offer_case_manager_role` put
  // the owner there). So we derive the owner from the roster instead: it is the
  // single participant that is neither the finder nor the caseactor recorder
  // (fv → vendor-1, fcv → coordinator). We still honor `object.attributedTo` when
  // it names a genuine owner lane (legacy logs), falling back to the roster rule,
  // then to vendor-1.
  //
  // GUARDED on `=== undefined` (not on seededRm): some ledgers (e.g. fvv) log
  // validate_report BEFORE the offer, so the receiver's RM may already have
  // advanced to VALID — seeding here would regress it. We only set the baseline
  // when never touched, but always mark the lane seeded so later status snapshots
  // are treated as transitions (and validated), not re-seeded.
  const receiverLane: LaneId = (() => {
    const viaAttr = actorUrlToLaneId(obj?.attributedTo)
    if (viaAttr !== 'unknown' && viaAttr !== 'caseactor' && viaAttr !== 'finder') {
      return viaAttr
    }
    const owner = Array.from(roster).find(
      (id) => id !== 'finder' && id !== 'caseactor' && id !== 'unknown'
    )
    return owner ?? 'vendor-1'
  })()
  if (shadow.rm[receiverLane] === undefined) shadow.rm[receiverLane] = 'RECEIVED'
  shadow.seededRm.add(receiverLane)
  // VFD receipt (vfd→Vfd, "the vendor became aware and began fix development") is a
  // VENDOR concept — seed it ONLY when the receiver is a vendor. A coordinator
  // receiver owns the case but develops no fix, so we leave its VFD unseeded and
  // let its own status snapshots seed it as-is; that surfaces any out-of-place
  // coordinator VFD verbatim (a generator signal) instead of fabricating a Vfd start.
  if (receiverLane.startsWith('vendor-')) {
    if (shadow.vfd[receiverLane] === undefined) shadow.vfd[receiverLane] = 'Vfd'
    shadow.seededVfd.add(receiverLane)
  }
  // The Finder enters CVD already at RM.ACCEPTED (validated/prioritized privately
  // before disclosure — see Validated demo handleSubmitReport). VFD is seeded
  // lazily from the finder's first status snapshot.
  if (shadow.rm['finder'] === undefined) shadow.rm['finder'] = 'ACCEPTED'
  shadow.seededRm.add('finder')

  const nodes = synthesizeCluster(
    entry,
    participants,
    'caseactor',
    x,
    'Case Created',
    [
      'VulnerabilityCase created',
      `Embargo seeded: ${shadow.emState}`,
      'Case Actor offered case-manager role',
      'Authoritative ledger established',
    ],
    'Joined Case',
    (lane) =>
      lane.id === receiverLane
        ? lane.id.startsWith('vendor-')
          ? ['Report received', 'RM seeded → RECEIVED', 'VFD seeded → Vfd']
          : ['Report received', 'RM seeded → RECEIVED']
        : ['Case announced', 'RM (private) → ACCEPTED', 'Participant record created'],
    false
  )
  return { nodes, logLines }
}

// --- add_report_to_case / submit_report → finder's report -------------------

/**
 * The finder's vulnerability report is added to the case. Two verb shapes:
 *   - `add_report_to_case` (2026-08): `actor` = the recorder/owner, and the
 *     finder is `object.attributedTo` (`object.type = VulnerabilityReport`).
 *   - `submit_report` (legacy): `actor` = the finder directly.
 * Either way the node belongs in the FINDER lane. This is a demo-kind node (no
 * machine slot of its own — the finder's private RM traversal to ACCEPTED is
 * seeded at case creation, CLAUDE.md §9), so it emits a "Submit Report" decision
 * node without touching the shadow. The entry may arrive after case creation, so
 * the finder lane and its ACCEPTED seed already exist; ensureParticipant is
 * defensive.
 */
function handleReport(
  entry: CaseLedgerEntry,
  participants: Map<string, ParticipantState>,
  _shadow: ShadowState,
  x: number,
  laneIndex: LaneIndexMap
): MapResult {
  // Prefer the report author (object.attributedTo = finder) for the current verb;
  // fall back to the actor for the legacy submit_report shape.
  const viaAttr = actorUrlToLaneId(entry.payloadSnapshot?.object?.attributedTo)
  const laneId = viaAttr !== 'unknown' ? viaAttr : actorUrlToLaneId(entry.payloadSnapshot?.actor)
  ensureParticipant(participants, laneId, laneIndex)
  const reportName = entry.payloadSnapshot?.object?.name ?? 'vulnerability report'
  const nodes = synthesizeCluster(
    entry,
    participants,
    laneId,
    x,
    'Submit Report',
    [`Report: "${reportName}"`, 'Offer(VulnerabilityReport) → receiver', 'RM (finder, private) → ACCEPTED'],
    'Report Submitted',
    () => [`Finder submitted "${reportName}"`],
    false
  )
  return { nodes, logLines: [] }
}

// --- offer_actor_to_case → ADR-0026 suggest-actor recommendation -----------

/**
 * First leg of the extension flow's suggest-actor handshake: a participant (the
 * Coordinator in fvcv-extension; the actor5/vendor-2 host in fccv-extension)
 * recommends a new actor to the case. The CaseActor then forwards it to the Case
 * Owner (`offer_case_participant`) who approves it (`accept_offer_case_participant`)
 * — both folded into this single node as log lines — after which the regular
 * invite/accept pair performs the actual join (rendered by handleAcceptInvite).
 *
 * This is a deliberate demo OVERLAY that mirrors the protocol's ADR-0026
 * suggest-actor-to-case flow (`_phase_coordinator_suggests_vendor2` in the
 * scenario source): the recommendation is procedural coordination, not a
 * declarative state-machine step, so it has no artifact to defer to. Emitted as
 * one node in the recommender's lane to keep the teaching timeline focused on the
 * decision (recommend), not the plumbing.
 */
function handleOfferActorToCase(
  entry: CaseLedgerEntry,
  participants: Map<string, ParticipantState>,
  _shadow: ShadowState,
  x: number,
  laneIndex: LaneIndexMap
): MapResult {
  const laneId = actorUrlToLaneId(entry.payloadSnapshot?.actor)
  ensureParticipant(participants, laneId, laneIndex)
  const recommended = entry.payloadSnapshot?.object?.name ?? 'a new actor'
  const recommender = participants.get(laneId)?.name ?? laneId
  const nodes = synthesizeCluster(
    entry,
    participants,
    laneId,
    x,
    'Actor Recommended',
    [
      `${recommender} recommends ${recommended} join the case`,
      'Offer(Actor, Case) → Case Actor (ADR-0026)',
      'Awaiting Case Owner approval + invite',
    ],
    'Actor Recommended',
    () => [`${recommended} recommended to the case`],
    false
  )
  return { nodes, logLines: [] }
}

// --- invite_actor_to_case → an existing member invites a new actor ---------

/**
 * An invitation to join the case.
 *
 * Two payload shapes appear in practice (CLAUDE.md §6 quirk #8, now updated):
 *   - EMPTY (`actor` absent) — the older two-actor/fvv logs, and a leading
 *     placeholder entry that precedes the populated one in the 2026-07 coordinator
 *     scenarios. Carries no attribution, so it's log-only; the join is shown by the
 *     later accept-invite.
 *   - POPULATED — the coordinator scenarios' second invite entry. Carries the
 *     invitee (`object.id`/`name`), the target case, and the real inviter in
 *     `target.attributedTo` (the case owner/manager — NOT the `actor`, which is the
 *     case-actor recorder sub-actor). We render an "Invite Sent" node in the
 *     INVITER's lane so the pair reads "Owner invites X" → "X accepts".
 *
 * Rendering the invite is independent of the ADR-0026 "Actor Recommended" node:
 * both are shown, since recommend (coordinator suggests) and invite (owner sends)
 * are distinct protocol actions.
 */
function handleInvite(
  entry: CaseLedgerEntry,
  participants: Map<string, ParticipantState>,
  _shadow: ShadowState,
  x: number,
  laneIndex: LaneIndexMap
): MapResult {
  // Empty placeholder invite: no attribution to draw. Log-only (matches the older
  // empty-invite behavior); the join still renders at accept-invite.
  if (!entry.payloadSnapshot?.actor) {
    return { nodes: [], logLines: ['  ↳ invite_actor_to_case (awaiting accept)'] }
  }

  // The real inviter is the case owner/manager in `target.attributedTo`, not the
  // recorder `actor`. Fall back to the acting lane if attribution is absent.
  const inviterLane = (() => {
    const viaTarget = actorUrlToLaneId(entry.payloadSnapshot?.target?.attributedTo)
    if (viaTarget !== 'unknown') return viaTarget
    return actorUrlToLaneId(entry.payloadSnapshot?.actor)
  })()
  ensureParticipant(participants, inviterLane, laneIndex)
  if (inviterLane === 'unknown') {
    return { nodes: [], logLines: ['  ↳ invite_actor_to_case (could not resolve inviter)'] }
  }

  const inviteeName = entry.payloadSnapshot?.object?.name ?? 'a new actor'
  const inviterName = participants.get(inviterLane)?.name ?? inviterLane
  const nodes = synthesizeCluster(
    entry,
    participants,
    inviterLane,
    x,
    'Invite Sent',
    [`${inviterName} invites ${inviteeName} to the case`, 'Invite(Actor, Case) → invitee', 'Awaiting the invitee’s acceptance'],
    'Invite Sent',
    () => [`${inviteeName} invited to the case`],
    false
  )
  return { nodes, logLines: [] }
}

// --- accept_invite_actor_to_case → invited vendor joins --------------------

/**
 * A later vendor accepts an invitation to the case. The invited vendor's lane
 * was already created by the roster pre-scan; here we seed its report-receipt
 * state (RM=RECEIVED / VFD=Vfd, like the primary vendor at case creation) and
 * emit a "Joined Case" decision node in the invited vendor's lane. The recorded
 * `actor` is the accepting vendor; `object.attributedTo` is the inviter.
 */
function handleAcceptInvite(
  entry: CaseLedgerEntry,
  participants: Map<string, ParticipantState>,
  shadow: ShadowState,
  x: number,
  laneIndex: LaneIndexMap
): MapResult {
  const laneId = actorUrlToLaneId(entry.payloadSnapshot?.actor)
  ensureParticipant(participants, laneId, laneIndex)
  const logLines: string[] = []

  if (laneId === 'unknown') {
    return { nodes: [], logLines: ['  ↳ accept_invite: could not resolve accepting actor'] }
  }

  // Report-receipt seed for the joining participant (mirrors the receiver seed in
  // handleCreateCase). Guarded so a pre-existing status snapshot isn't regressed. Every
  // joiner — vendor OR coordinator — receives & manages the report, so RM is seeded
  // for all. VFD (fix development) is seeded ONLY for a vendor joiner, matching
  // handleCreateCase: a coordinator owns/manages but builds no fix, so its VFD is left
  // unseeded and surfaced verbatim from its own status snapshots (a generator signal
  // rather than a fabricated Vfd start).
  const isVendorJoiner = laneId.startsWith('vendor-')
  if (!shadow.seededRm.has(laneId)) {
    shadow.rm[laneId] = 'RECEIVED'
    shadow.seededRm.add(laneId)
    logLines.push(`  ↳ seeded ${laneId} RM = RECEIVED (invite accepted)`)
  }
  if (isVendorJoiner && !shadow.seededVfd.has(laneId)) {
    shadow.vfd[laneId] = 'Vfd'
    shadow.seededVfd.add(laneId)
  }

  const name = participants.get(laneId)?.name ?? laneId
  const decisionBullets = isVendorJoiner
    ? [`${name} accepted the invitation to the case`, 'RM seeded → RECEIVED', 'VFD seeded → Vfd']
    : [`${name} accepted the invitation to the case`, 'RM seeded → RECEIVED']
  const nodes = synthesizeCluster(
    entry,
    participants,
    laneId,
    x,
    'Accept Invite',
    decisionBullets,
    'Participant Joined',
    () => [`${name} joined the case`],
    false
  )
  return { nodes, logLines }
}

// --- reject_invite_actor_to_case → invitee declines -------------------------

/**
 * An invited actor declines the invitation (the fcv-reject scenario). The
 * recorded `actor` is the rejecter; the wrapped `object` is the Invite, whose
 * `object` is the invitee and whose `actor` is the inviter. We render a
 * "Declined Invite" decision node in the rejecter's lane. No machine change — the
 * rejecter never joins — so the lane is left not-joined (a rejecter that never
 * produced a status won't have been made visible, so it simply doesn't appear as
 * an ongoing lane).
 */
function handleRejectInvite(
  entry: CaseLedgerEntry,
  participants: Map<string, ParticipantState>,
  _shadow: ShadowState,
  x: number,
  laneIndex: LaneIndexMap
): MapResult {
  const laneId = actorUrlToLaneId(entry.payloadSnapshot?.actor)
  ensureParticipant(participants, laneId, laneIndex)
  if (laneId === 'unknown') {
    return { nodes: [], logLines: ['  ↳ reject_invite: could not resolve rejecting actor'] }
  }
  const name = participants.get(laneId)?.name ?? laneId
  const nodes = synthesizeCluster(
    entry,
    participants,
    laneId,
    x,
    'Declined Invite',
    [`${name} declined the invitation to the case`, 'Reject(Invite) → inviter', 'Actor does not join the case'],
    'Invite Declined',
    () => [`${name} declined to join the case`],
    false
  )
  return { nodes, logLines: [] }
}

// --- add_case_participant → roster bookkeeping (log-only) --------------------

/**
 * The case manager records a participant on the case roster (2026-08). The
 * visible join renders via `accept_invite_actor_to_case`; this entry is
 * bookkeeping, so it is log-only and consumes no column. We still ensure the
 * lane exists defensively (subset ledgers), keyed off the recorded participant
 * (`object.name`/`object.attributedTo` = the participant URL).
 */
function handleAddCaseParticipant(
  entry: CaseLedgerEntry,
  participants: Map<string, ParticipantState>,
  _shadow: ShadowState,
  _x: number,
  laneIndex: LaneIndexMap
): MapResult {
  const obj = entry.payloadSnapshot?.object
  const laneId = actorUrlToLaneId(obj?.attributedTo ?? obj?.name)
  ensureParticipant(participants, laneId, laneIndex)
  const label = laneId === 'unknown' ? 'a participant' : participants.get(laneId)?.name ?? laneId
  return { nodes: [], logLines: [`  ↳ add_case_participant (${label} recorded on case roster)`] }
}

// --- validate_report → rm validate -----------------------------------------

function handleValidateReport(
  entry: CaseLedgerEntry,
  participants: Map<string, ParticipantState>,
  shadow: ShadowState,
  x: number,
  laneIndex: LaneIndexMap
): MapResult {
  const laneId = actorUrlToLaneId(entry.payloadSnapshot?.actor)
  ensureParticipant(participants, laneId, laneIndex)
  const logLines: string[] = []

  const src = shadow.rm[laneId] ?? 'RECEIVED'
  const legal = isLegalTransition('rm', src, 'validate')
  let violation = false
  let violationReason: string | undefined
  if (legal) {
    shadow.rm[laneId] = nextState('rm', src, 'validate')!
  } else {
    violation = true
    violationReason =
      `The RM machine has no "validate" transition from ${src}. ` +
      `"validate" is only legal from RECEIVED or INVALID. Recording it from ` +
      `${src} would skip or repeat the report-validation step.`
    logLines.push(
      `  ↳ PROTOCOL VIOLATION: rm "validate" illegal from "${src}" (subject=${laneId}); forcing shadow → VALID`
    )
    shadow.rm[laneId] = 'VALID'
  }

  // The validator is the case receiver/owner, which is the primary vendor in
  // two-actor/fvv/fvcv-extension but the COORDINATOR in fcv/fccv-extension — name
  // the actual lane rather than assuming "Vendor".
  const validatorName = participants.get(laneId)?.name ?? laneId
  const nodes = synthesizeCluster(
    entry,
    participants,
    laneId,
    x,
    'Validate Report',
    ['Accept(Offer) — report deemed legitimate', `RM: ${src} → ${shadow.rm[laneId]}`],
    'Report Validated',
    () => [`${validatorName} validated the report`, `RM: → ${shadow.rm[laneId]}`],
    violation,
    violationReason
  )
  return { nodes, logLines }
}

// --- add_note_to_case → question / answer (demo-kind, no machine slot) ------

function handleNote(
  entry: CaseLedgerEntry,
  participants: Map<string, ParticipantState>,
  shadow: ShadowState,
  x: number,
  laneIndex: LaneIndexMap
): MapResult {
  const laneId = actorUrlToLaneId(entry.payloadSnapshot?.actor)
  ensureParticipant(participants, laneId, laneIndex)
  const obj = entry.payloadSnapshot?.object
  const noteName = obj?.name ?? 'Note'
  const content = (obj?.content ?? '').trim()
  const snippet = content.length > 90 ? content.slice(0, 87) + '…' : content

  // The ledger lacks inReplyTo linkage (CLAUDE.md §6 gap #4), so classify by a
  // heuristic: the first unanswered note is a question; the next note from a
  // DIFFERENT actor while a question is pending is its answer.
  const explicitReply = obj?.inReplyTo != null
  const isAnswer =
    explicitReply ||
    (shadow.pendingQuestionBy !== null && shadow.pendingQuestionBy !== laneId)

  let label: string
  let decisionBullets: string[]
  let consequenceLabel: string
  if (isAnswer) {
    label = 'Answer Question'
    consequenceLabel = 'Answer Received'
    decisionBullets = [`Note: "${noteName}"`, snippet || '(reply)', 'Reply delivered to participants']
    shadow.pendingQuestionBy = null
  } else {
    label = 'Ask Question'
    consequenceLabel = 'Note Received'
    decisionBullets = [`Note: "${noteName}"`, snippet || '(question)', 'Add(Note, target=Case)']
    shadow.pendingQuestionBy = laneId
  }

  const nodes = synthesizeCluster(
    entry,
    participants,
    laneId,
    x,
    label,
    decisionBullets,
    consequenceLabel,
    () => [`Note "${noteName}" delivered`, snippet || ''],
    false
  )
  return { nodes, logLines: [] }
}

// --- add_participant_status_to_participant → snapshot diff ------------------

function handleParticipantStatus(
  entry: CaseLedgerEntry,
  participants: Map<string, ParticipantState>,
  shadow: ShadowState,
  x: number,
  laneIndex: LaneIndexMap
): MapResult {
  const obj = entry.payloadSnapshot?.object
  const subjectUrl = obj?.attributedTo ?? entry.payloadSnapshot?.target?.attributedTo ?? entry.payloadSnapshot?.actor
  const laneId = actorUrlToLaneId(subjectUrl)
  ensureParticipant(participants, laneId, laneIndex)

  const tokens = parseStatusName(obj?.name)
  // The case-actor recorder is the virtual CASE_MANAGER (§9): it has no report-
  // management disposition of its own and stays at RM/VFD = 'N/A'. The 2026-08
  // ledger attributes a case-management RM lifecycle to the case-actor sub-actor
  // URL (e.g. fv logIndex 2–4: RECEIVED→VALID→ACCEPTED), but that merely mirrors
  // the OWNER's progress — the owner's own participant lane (vendor/coordinator)
  // already carries it. So we ignore RM/VFD on the caseactor lane to keep it N/A
  // and avoid a spurious lifecycle in the recorder lane; case-level EM/PXA still
  // apply below.
  const isRecorder = laneId === 'caseactor'
  const rmNext = isRecorder ? undefined : obj?.rmState ?? tokens.rm
  const vfdNext = isRecorder ? undefined : obj?.vfdState ?? tokens.vfd
  const logLines: string[] = []

  // Track the changes this entry represents; pick a primary for the node label.
  const changes: Array<{ machine: MachineName; from: string; to: string; trigger: string }> = []
  let violation = false
  const violationReasons: string[] = []
  // Multi-hop inferences: a status diff bridged by >1 legal trigger means the log
  // skipped intermediate states and the mapper GUESSED the path (see `inferred` in
  // types.ts). Collected here and surfaced as an "inferred, not observed" tripwire.
  const inferredNotes: string[] = []

  // ---- RM ----
  if (rmNext !== undefined) {
    if (!shadow.seededRm.has(laneId)) {
      shadow.rm[laneId] = rmNext
      shadow.seededRm.add(laneId)
      logLines.push(`  ↳ seeded ${laneId} RM = ${rmNext} (first snapshot)`)
    } else {
      const src = shadow.rm[laneId]
      if (rmNext !== src) {
        const path = triggerPath('rm', src, rmNext)
        if (path && path.length > 0) {
          changes.push({ machine: 'rm', from: src, to: rmNext, trigger: path[path.length - 1] })
          if (path.length > 1) {
            logLines.push(`  ↳ RM path: ${src} → ${rmNext} via ${path.join(', ')}`)
            inferredNotes.push(
              `RM ${src} → ${rmNext} was not a single logged step: the mapper inferred the ` +
                `legal path [${path.join(' → ')}] because intermediate states were not recorded.`
            )
          }
          shadow.rm[laneId] = rmNext
        } else {
          violation = true
          // Record the illegal jump as a change so a flagged node still renders.
          // Without this, a status entry whose ONLY content is an illegal RM jump
          // would hit the `changes.length === 0` early return and be invisible.
          changes.push({ machine: 'rm', from: src, to: rmNext, trigger: 'illegal' })
          violationReasons.push(
            `RM cannot reach ${rmNext} from ${src}: no sequence of legal RM ` +
              `transitions connects them. The report's management state jumped illegally.`
          )
          logLines.push(
            `  ↳ PROTOCOL VIOLATION: rm has no path "${src}" → "${rmNext}" (subject=${laneId}); forcing shadow`
          )
          shadow.rm[laneId] = rmNext
        }
      }
    }
  }

  // ---- VFD ----
  if (vfdNext !== undefined) {
    if (!shadow.seededVfd.has(laneId)) {
      shadow.vfd[laneId] = vfdNext
      shadow.seededVfd.add(laneId)
      logLines.push(`  ↳ seeded ${laneId} VFD = ${vfdNext} (first snapshot)`)
    } else {
      const src = shadow.vfd[laneId]
      if (vfdNext !== src) {
        const path = triggerPath('vfd', src, vfdNext)
        if (path && path.length > 0) {
          changes.push({ machine: 'vfd', from: src, to: vfdNext, trigger: path[path.length - 1] })
          if (path.length > 1) {
            logLines.push(`  ↳ VFD path: ${src} → ${vfdNext} via ${path.join(', ')}`)
            inferredNotes.push(
              `VFD ${src} → ${vfdNext} was not a single logged step: the mapper inferred the ` +
                `legal path [${path.join(' → ')}] because intermediate milestones were not recorded.`
            )
          }
          shadow.vfd[laneId] = vfdNext
        } else {
          violation = true
          // See the RM branch above: record the illegal jump so the flagged node
          // renders instead of vanishing via the `changes.length === 0` return.
          changes.push({ machine: 'vfd', from: src, to: vfdNext, trigger: 'illegal' })
          violationReasons.push(
            `VFD cannot reach ${vfdNext} from ${src}: the fix-development ladder ` +
              `(vfd → Vfd → VFd → VFD) advances one milestone at a time and cannot ` +
              `skip or regress. This snapshot jumped illegally.`
          )
          logLines.push(
            `  ↳ PROTOCOL VIOLATION: vfd has no path "${src}" → "${vfdNext}" (subject=${laneId}); forcing shadow`
          )
          shadow.vfd[laneId] = vfdNext
        }
      }
    }
  }

  // ---- Case-level PXA / EM (forward-only; participant snapshots can be stale, but
  // a snapshot on no legal trajectory is a violation — see applyCaseLevelForward) ----
  const cs = readCaseStatus(entry)
  const pxaChange = applyCaseLevelForward('pxa', shadow, cs?.pxaState, logLines)
  if (pxaChange) {
    changes.push({ machine: 'pxa', from: pxaChange.from, to: pxaChange.to, trigger: pxaChange.trigger })
    if (pxaChange.violation) {
      violation = true
      if (pxaChange.reason) violationReasons.push(pxaChange.reason)
    }
    if (pxaChange.inferredNote) inferredNotes.push(pxaChange.inferredNote)
  }
  const emChange = applyCaseLevelForward('em', shadow, cs?.emState, logLines)
  if (emChange) {
    changes.push({ machine: 'em', from: emChange.from, to: emChange.to, trigger: emChange.trigger })
    if (emChange.violation) {
      violation = true
      if (emChange.reason) violationReasons.push(emChange.reason)
    }
    if (emChange.inferredNote) inferredNotes.push(emChange.inferredNote)

    // Cross-machine embargo-viability check (artifact rule): even a per-machine-
    // LEGAL EM advance can violate the protocol if the embargo is being negotiated
    // in a CS state that forbids it (MUST NOT propose/accept a new embargo once
    // P/X/A — negotiating.md). `shadow.pxaState` was just advanced by the pxa call
    // above, so it reflects this entry's publicity. Starting a new embargo (into
    // PROPOSED) needs `canStartEmbargo`; establishing/continuing one (into
    // ACTIVE/REVISE) needs `embargoViable`.
    const enteringNew = emChange.to === 'PROPOSED'
    const enteringActive = emChange.to === 'ACTIVE' || emChange.to === 'REVISE'
    const viabilityOk = enteringNew
      ? canStartEmbargo(shadow.pxaState)
      : enteringActive
      ? embargoViable(shadow.pxaState)
      : true
    if (!viabilityOk) {
      violation = true
      violationReasons.push(
        `Embargo entered ${emChange.to} while the case is at PXA ${shadow.pxaState}, but the ` +
          `protocol forbids ${enteringNew ? 'proposing' : 'establishing/continuing'} an embargo ` +
          `once the vulnerability is public, an exploit is public, or attacks are observed ` +
          `(per the artifact's embargo-viability rule).`
      )
      logLines.push(
        `  ↳ PROTOCOL VIOLATION: EM → ${emChange.to} not viable at PXA=${shadow.pxaState} (embargo-viability rule)`
      )
    }
  }

  // No meaningful change (only seeds / no-ops) → no node, no column.
  if (changes.length === 0) return { nodes: [], logLines }

  // Primary change for the label: RM > VFD > PXA > EM.
  const order: MachineName[] = ['rm', 'vfd', 'pxa', 'em']
  const primary = changes.slice().sort((a, b) => order.indexOf(a.machine) - order.indexOf(b.machine))[0]
  const label = TRIGGER_LABEL[`${primary.machine}:${primary.trigger}`] ?? 'Status Update'

  const decisionBullets = changes.map((c) => `${c.machine.toUpperCase()}: ${c.from} → ${c.to}`)
  const subjectName = participants.get(laneId)?.name ?? laneId

  // A violation supersedes an inference (a flagged illegal jump is the stronger
  // signal); only annotate as inferred when there's no violation on this node.
  const inferred = !violation && inferredNotes.length > 0
    ? { note: inferredNotes.join(' ') }
    : undefined

  const nodes = synthesizeCluster(
    entry,
    participants,
    laneId,
    x,
    label,
    decisionBullets,
    label,
    () => [`${subjectName} status update`, ...changes.map((c) => `${c.machine.toUpperCase()} → ${c.to}`)],
    violation,
    violationReasons.join(' ') || undefined,
    inferred
  )
  return { nodes, logLines }
}

// --- add_case_status_to_case → case-level EM/PXA snapshot -------------------

/**
 * A first-class case-level status snapshot (2026-08). Unlike the embedded
 * `caseStatus` on participant statuses / the case bootstrap, here the `object`
 * IS the `CaseStatus`, so `emState`/`pxaState` sit directly on it. This is the
 * case-level analog of `handleParticipantStatus`: apply the EM/PXA advances
 * forward-only against the shadow (stale snapshots ignored, illegal jumps
 * flagged), run the cross-machine embargo-viability check, and emit a node in the
 * caseactor recorder lane only when something actually changed (otherwise the
 * entry is a redundant re-snapshot → log-only, no column consumed).
 */
function handleCaseStatus(
  entry: CaseLedgerEntry,
  participants: Map<string, ParticipantState>,
  shadow: ShadowState,
  x: number,
  laneIndex: LaneIndexMap
): MapResult {
  ensureParticipant(participants, 'caseactor', laneIndex)
  const obj = entry.payloadSnapshot?.object
  const tokens = parseStatusName(obj?.name)
  const emNext = obj?.emState ?? tokens.em
  const pxaNext = obj?.pxaState ?? tokens.pxa
  const logLines: string[] = []

  const changes: Array<{ machine: MachineName; from: string; to: string; trigger: string }> = []
  let violation = false
  const violationReasons: string[] = []
  const inferredNotes: string[] = []

  // PXA first, then EM — matches handleParticipantStatus so the embargo-viability
  // check below sees this entry's publicity (shadow.pxaState just advanced).
  const pxaChange = applyCaseLevelForward('pxa', shadow, pxaNext, logLines)
  if (pxaChange) {
    changes.push({ machine: 'pxa', from: pxaChange.from, to: pxaChange.to, trigger: pxaChange.trigger })
    if (pxaChange.violation) {
      violation = true
      if (pxaChange.reason) violationReasons.push(pxaChange.reason)
    }
    if (pxaChange.inferredNote) inferredNotes.push(pxaChange.inferredNote)
  }
  const emChange = applyCaseLevelForward('em', shadow, emNext, logLines)
  if (emChange) {
    changes.push({ machine: 'em', from: emChange.from, to: emChange.to, trigger: emChange.trigger })
    if (emChange.violation) {
      violation = true
      if (emChange.reason) violationReasons.push(emChange.reason)
    }
    if (emChange.inferredNote) inferredNotes.push(emChange.inferredNote)

    const enteringNew = emChange.to === 'PROPOSED'
    const enteringActive = emChange.to === 'ACTIVE' || emChange.to === 'REVISE'
    const viabilityOk = enteringNew
      ? canStartEmbargo(shadow.pxaState)
      : enteringActive
      ? embargoViable(shadow.pxaState)
      : true
    if (!viabilityOk) {
      violation = true
      violationReasons.push(
        `Embargo entered ${emChange.to} while the case is at PXA ${shadow.pxaState}, but the ` +
          `protocol forbids ${enteringNew ? 'proposing' : 'establishing/continuing'} an embargo ` +
          `once the vulnerability is public, an exploit is public, or attacks are observed ` +
          `(per the artifact's embargo-viability rule).`
      )
      logLines.push(
        `  ↳ PROTOCOL VIOLATION: EM → ${emChange.to} not viable at PXA=${shadow.pxaState} (embargo-viability rule)`
      )
    }
  }

  // No meaningful change (redundant re-snapshot) → no node, no column.
  if (changes.length === 0) return { nodes: [], logLines }

  // Primary change for the label: PXA > EM (RM/VFD don't appear on a CaseStatus).
  const order: MachineName[] = ['pxa', 'em']
  const primary = changes.slice().sort((a, b) => order.indexOf(a.machine) - order.indexOf(b.machine))[0]
  const label = TRIGGER_LABEL[`${primary.machine}:${primary.trigger}`] ?? 'Case Status Update'

  const inferred = !violation && inferredNotes.length > 0 ? { note: inferredNotes.join(' ') } : undefined

  const nodes = synthesizeCluster(
    entry,
    participants,
    'caseactor',
    x,
    label,
    changes.map((c) => `${c.machine.toUpperCase()}: ${c.from} → ${c.to}`),
    label,
    () => ['Case status update', ...changes.map((c) => `${c.machine.toUpperCase()} → ${c.to}`)],
    violation,
    violationReasons.join(' ') || undefined,
    inferred
  )
  return { nodes, logLines }
}

// --- remove_embargo_event_from_case → em terminate --------------------------

function handleRemoveEmbargo(
  entry: CaseLedgerEntry,
  participants: Map<string, ParticipantState>,
  shadow: ShadowState,
  x: number,
  laneIndex: LaneIndexMap
): MapResult {
  ensureParticipant(participants, 'caseactor', laneIndex)
  const logLines: string[] = []
  const src = shadow.emState
  let violation = false
  let violationReason: string | undefined
  if (isLegalTransition('em', src, 'terminate')) {
    shadow.emState = nextState('em', src, 'terminate')!
  } else {
    violation = true
    violationReason =
      `The EM machine has no "terminate" transition from ${src}. ` +
      `An embargo can only be terminated from ACTIVE or REVISE. From ${src} ` +
      `there is no active embargo to end.`
    logLines.push(
      `  ↳ PROTOCOL VIOLATION: em "terminate" illegal from "${src}"; forcing shadow → EXITED`
    )
    shadow.emState = 'EXITED'
  }

  const nodes = synthesizeCluster(
    entry,
    participants,
    'caseactor',
    x,
    'Embargo Terminated',
    ['EmbargoEvent removed from case', `EM: ${src} → ${shadow.emState}`, 'Embargo period ended'],
    'Embargo Ended',
    () => ['Embargo terminated', `EM: → ${shadow.emState}`],
    violation,
    violationReason
  )
  return { nodes, logLines }
}

// --- close_case → case-level close (per-participant closes arrive via status) -

function handleCloseCase(
  entry: CaseLedgerEntry,
  participants: Map<string, ParticipantState>,
  shadow: ShadowState,
  x: number,
  laneIndex: LaneIndexMap
): MapResult {
  ensureParticipant(participants, 'caseactor', laneIndex)
  const logLines: string[] = []

  // The per-participant RM→CLOSED transitions arrive as their own status
  // snapshots; close_case is the case manager's case-level close. If a future
  // ledger omits those snapshots, close the subject's RM here as a fallback.
  const subjectUrl = entry.payloadSnapshot?.object?.attributedTo
  const subjectLane = actorUrlToLaneId(subjectUrl)
  let violation = false
  let violationReason: string | undefined
  if (subjectLane !== 'unknown' && shadow.seededRm.has(subjectLane) && shadow.rm[subjectLane] !== 'CLOSED') {
    const src = shadow.rm[subjectLane]
    if (isLegalTransition('rm', src, 'close')) {
      shadow.rm[subjectLane] = 'CLOSED'
      logLines.push(`  ↳ close_case: ${subjectLane} RM ${src} → CLOSED`)
    } else {
      violation = true
      violationReason =
        `The RM machine has no "close" transition from ${src}. ` +
        `A case can only be closed from ACCEPTED, DEFERRED, or INVALID — ` +
        `closing from ${src} skips the required disposition of the report.`
      logLines.push(
        `  ↳ PROTOCOL VIOLATION: rm "close" illegal from "${src}" (subject=${subjectLane}); forcing CLOSED`
      )
      shadow.rm[subjectLane] = 'CLOSED'
    }
  }

  const nodes = synthesizeCluster(
    entry,
    participants,
    'caseactor',
    x,
    'Close Case',
    ['VulnerabilityCase closed', `EM: ${shadow.emState}`, 'Case archived in ledger'],
    'Case Closed',
    () => ['Case closed by Case Manager'],
    violation,
    violationReason
  )
  return { nodes, logLines }
}
