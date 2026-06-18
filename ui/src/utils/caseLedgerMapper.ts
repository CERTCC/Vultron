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

import type { DemoState, ParticipantState, TimelineEvent } from '../types'
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

// Fixed lane ordering, matching the Validated demo (finder top, vendor, caseactor).
const LANE_INDEX: Record<Exclude<LaneId, 'unknown'>, number> = {
  finder: 0,
  'vendor-1': 1,
  caseactor: 2,
}

function makeParticipant(laneId: Exclude<LaneId, 'unknown'>): ParticipantState {
  switch (laneId) {
    case 'finder':
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
        visible: true,
        laneIndex: LANE_INDEX.finder,
      }
    case 'vendor-1':
      return {
        id: 'vendor-1',
        name: 'Vendor',
        role: PARTICIPANT_ROLES.vendor,
        color: getVendorColor(1),
        rmState: 'START',
        vfdState: 'vfd',
        embargoAccepted: false,
        hasPublished: false,
        hasClosed: false,
        visible: true,
        laneIndex: LANE_INDEX['vendor-1'],
      }
    case 'caseactor':
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
        visible: true,
        laneIndex: LANE_INDEX.caseactor,
      }
  }
}

/** Create a lane if it doesn't exist yet (robust to mid-stream / subset ledgers). */
function ensureParticipant(participants: Map<string, ParticipantState>, laneId: LaneId): void {
  if (laneId === 'unknown') return
  if (!participants.has(laneId)) participants.set(laneId, makeParticipant(laneId))
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
  violation: boolean
): TimelineEvent[] {
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
 * Apply a single case-level machine snapshot forward-only. Never regresses the
 * shadow (a participant's embedded `caseStatus` can be stale — e.g. the sample's
 * finder status still reads EM=ACTIVE after the embargo was terminated). Returns
 * the trigger applied (for labeling) or null if nothing/forbidden happened.
 */
function applyCaseLevelForward(
  machine: 'em' | 'pxa',
  shadow: ShadowState,
  snapshot: string | undefined,
  logLines: string[]
): { trigger: string; from: string; to: string } | null {
  if (!snapshot) return null
  const current = machine === 'em' ? shadow.emState : shadow.pxaState
  if (snapshot === current) return null

  const path = triggerPath(machine, current, snapshot)
  if (path === null || path.length === 0) {
    // Unreachable forward — almost always a stale/regressed snapshot. Keep shadow.
    logLines.push(
      `  ↳ ignored stale ${machine.toUpperCase()} snapshot "${snapshot}" (shadow stays "${current}")`
    )
    return null
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
  return { trigger: lastTrigger, from: current, to: snapshot }
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
  let visualEventIndex = 0

  const timeLabel = (entry: CaseLedgerEntry) =>
    new Date(entry.receivedAt).toLocaleTimeString()

  for (const entry of entries) {
    const x = INITIAL_X_POSITION + visualEventIndex * X_INCREMENT
    const result = handleEntry(entry, participants, shadow, x)

    // Keep the actor panels in sync with the shadow after each entry.
    syncParticipantsToShadow(participants, shadow)

    if (result.nodes.length > 0) {
      timelineEvents.push(...result.nodes)
      eventLog.push(`[${timeLabel(entry)}] ${result.nodes[0].label}`)
      for (const line of result.logLines) eventLog.push(line)
      visualEventIndex++
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
  x: number
): MapResult {
  switch (entry.eventType) {
    case 'offer_case_manager_role':
      return handleOffer(entry, participants, shadow, x)
    case 'validate_report':
      return handleValidateReport(entry, participants, shadow, x)
    case 'add_note_to_case':
      return handleNote(entry, participants, shadow, x)
    case 'add_participant_status_to_participant':
      return handleParticipantStatus(entry, participants, shadow, x)
    case 'remove_embargo_event_from_case':
      return handleRemoveEmbargo(entry, participants, shadow, x)
    case 'close_case':
      return handleCloseCase(entry, participants, shadow, x)
    default:
      return { nodes: [], logLines: [`  ↳ unhandled eventType "${entry.eventType}"`] }
  }
}

// --- offer_case_manager_role → case-created bootstrap ----------------------

function handleOffer(
  entry: CaseLedgerEntry,
  participants: Map<string, ParticipantState>,
  shadow: ShadowState,
  x: number
): MapResult {
  const logLines: string[] = []
  const obj = entry.payloadSnapshot?.object

  // Build the roster from the case's actor→participant index (its keys are the
  // three actor URLs). Fall back to the recorded actor if the index is absent.
  const roster = new Set<LaneId>()
  if (obj?.actorParticipantIndex) {
    for (const url of Object.keys(obj.actorParticipantIndex)) roster.add(actorUrlToLaneId(url))
  }
  roster.add(actorUrlToLaneId(entry.payloadSnapshot?.actor))
  for (const laneId of roster) ensureParticipant(participants, laneId)
  // Ensure all three standard lanes exist even if the index was sparse.
  ensureParticipant(participants, 'finder')
  ensureParticipant(participants, 'vendor-1')
  ensureParticipant(participants, 'caseactor')

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

  // Report-receipt seed: the vendor enters at RM.RECEIVED / VFD.Vfd so the later
  // `validate_report` is a legal RECEIVED→VALID step (matches the Validated demo's
  // receipt seed). Seeding the vendor at ACCEPTED would make `validate` illegal.
  shadow.rm['vendor-1'] = 'RECEIVED'
  shadow.vfd['vendor-1'] = 'Vfd'
  shadow.seededRm.add('vendor-1')
  shadow.seededVfd.add('vendor-1')
  // The Finder enters CVD already at RM.ACCEPTED (validated/prioritized privately
  // before disclosure — see Validated demo handleSubmitReport). VFD is seeded
  // lazily from the finder's first status snapshot.
  shadow.rm['finder'] = 'ACCEPTED'
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
      lane.id === 'vendor-1'
        ? ['Report received', 'RM seeded → RECEIVED', 'VFD seeded → Vfd']
        : ['Case announced', 'RM (private) → ACCEPTED', 'Participant record created'],
    false
  )
  return { nodes, logLines }
}

// --- validate_report → rm validate -----------------------------------------

function handleValidateReport(
  entry: CaseLedgerEntry,
  participants: Map<string, ParticipantState>,
  shadow: ShadowState,
  x: number
): MapResult {
  const laneId = actorUrlToLaneId(entry.payloadSnapshot?.actor)
  ensureParticipant(participants, laneId)
  const logLines: string[] = []

  const src = shadow.rm[laneId] ?? 'RECEIVED'
  const legal = isLegalTransition('rm', src, 'validate')
  let violation = false
  if (legal) {
    shadow.rm[laneId] = nextState('rm', src, 'validate')!
  } else {
    violation = true
    logLines.push(
      `  ↳ PROTOCOL VIOLATION: rm "validate" illegal from "${src}" (subject=${laneId}); forcing shadow → VALID`
    )
    shadow.rm[laneId] = 'VALID'
  }

  const nodes = synthesizeCluster(
    entry,
    participants,
    laneId,
    x,
    'Validate Report',
    ['Accept(Offer) — report deemed legitimate', `RM: ${src} → ${shadow.rm[laneId]}`],
    'Report Validated',
    () => ['Vendor validated the report', `RM: → ${shadow.rm[laneId]}`],
    violation
  )
  return { nodes, logLines }
}

// --- add_note_to_case → question / answer (demo-kind, no machine slot) ------

function handleNote(
  entry: CaseLedgerEntry,
  participants: Map<string, ParticipantState>,
  shadow: ShadowState,
  x: number
): MapResult {
  const laneId = actorUrlToLaneId(entry.payloadSnapshot?.actor)
  ensureParticipant(participants, laneId)
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
  x: number
): MapResult {
  const obj = entry.payloadSnapshot?.object
  const subjectUrl = obj?.attributedTo ?? entry.payloadSnapshot?.target?.attributedTo ?? entry.payloadSnapshot?.actor
  const laneId = actorUrlToLaneId(subjectUrl)
  ensureParticipant(participants, laneId)

  const tokens = parseStatusName(obj?.name)
  const rmNext = obj?.rmState ?? tokens.rm
  const vfdNext = obj?.vfdState ?? tokens.vfd
  const logLines: string[] = []

  // Track the changes this entry represents; pick a primary for the node label.
  const changes: Array<{ machine: MachineName; from: string; to: string; trigger: string }> = []
  let violation = false

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
          if (path.length > 1) logLines.push(`  ↳ RM path: ${src} → ${rmNext} via ${path.join(', ')}`)
          shadow.rm[laneId] = rmNext
        } else {
          violation = true
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
          if (path.length > 1) logLines.push(`  ↳ VFD path: ${src} → ${vfdNext} via ${path.join(', ')}`)
          shadow.vfd[laneId] = vfdNext
        } else {
          violation = true
          logLines.push(
            `  ↳ PROTOCOL VIOLATION: vfd has no path "${src}" → "${vfdNext}" (subject=${laneId}); forcing shadow`
          )
          shadow.vfd[laneId] = vfdNext
        }
      }
    }
  }

  // ---- Case-level PXA / EM (forward-only; participant snapshots can be stale) ----
  const cs = readCaseStatus(entry)
  const pxaChange = applyCaseLevelForward('pxa', shadow, cs?.pxaState, logLines)
  if (pxaChange) changes.push({ machine: 'pxa', from: pxaChange.from, to: pxaChange.to, trigger: pxaChange.trigger })
  const emChange = applyCaseLevelForward('em', shadow, cs?.emState, logLines)
  if (emChange) changes.push({ machine: 'em', from: emChange.from, to: emChange.to, trigger: emChange.trigger })

  // No meaningful change (only seeds / no-ops) → no node, no column.
  if (changes.length === 0) return { nodes: [], logLines }

  // Primary change for the label: RM > VFD > PXA > EM.
  const order: MachineName[] = ['rm', 'vfd', 'pxa', 'em']
  const primary = changes.slice().sort((a, b) => order.indexOf(a.machine) - order.indexOf(b.machine))[0]
  const label = TRIGGER_LABEL[`${primary.machine}:${primary.trigger}`] ?? 'Status Update'

  const decisionBullets = changes.map((c) => `${c.machine.toUpperCase()}: ${c.from} → ${c.to}`)
  const subjectName = participants.get(laneId)?.name ?? laneId

  const nodes = synthesizeCluster(
    entry,
    participants,
    laneId,
    x,
    label,
    decisionBullets,
    label,
    () => [`${subjectName} status update`, ...changes.map((c) => `${c.machine.toUpperCase()} → ${c.to}`)],
    violation
  )
  return { nodes, logLines }
}

// --- remove_embargo_event_from_case → em terminate --------------------------

function handleRemoveEmbargo(
  entry: CaseLedgerEntry,
  participants: Map<string, ParticipantState>,
  shadow: ShadowState,
  x: number
): MapResult {
  ensureParticipant(participants, 'caseactor')
  const logLines: string[] = []
  const src = shadow.emState
  let violation = false
  if (isLegalTransition('em', src, 'terminate')) {
    shadow.emState = nextState('em', src, 'terminate')!
  } else {
    violation = true
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
    violation
  )
  return { nodes, logLines }
}

// --- close_case → case-level close (per-participant closes arrive via status) -

function handleCloseCase(
  entry: CaseLedgerEntry,
  participants: Map<string, ParticipantState>,
  shadow: ShadowState,
  x: number
): MapResult {
  ensureParticipant(participants, 'caseactor')
  const logLines: string[] = []

  // The per-participant RM→CLOSED transitions arrive as their own status
  // snapshots; close_case is the case manager's case-level close. If a future
  // ledger omits those snapshots, close the subject's RM here as a fallback.
  const subjectUrl = entry.payloadSnapshot?.object?.attributedTo
  const subjectLane = actorUrlToLaneId(subjectUrl)
  if (subjectLane !== 'unknown' && shadow.seededRm.has(subjectLane) && shadow.rm[subjectLane] !== 'CLOSED') {
    const src = shadow.rm[subjectLane]
    if (isLegalTransition('rm', src, 'close')) {
      shadow.rm[subjectLane] = 'CLOSED'
      logLines.push(`  ↳ close_case: ${subjectLane} RM ${src} → CLOSED`)
    } else {
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
    false
  )
  return { nodes, logLines }
}
