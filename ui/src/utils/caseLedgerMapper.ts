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
 * Three sources, none of them kept in `ui/`:
 *   - the lanes come from the ledger (`./replayLanes`): one per participant actor,
 *     keyed on its actor id and labelled by the CVD roles its `CaseParticipant`
 *     records name;
 *   - every node label and entry log line is the semantic registry's phrase for
 *     the entry (`renderPhrase`, DRPT-03-002); the mapper only chooses the slot
 *     values, which are lane labels. A node's first detail is its entry's Wire
 *     Activity, from the same registry. A type the registry does not list is drawn
 *     as an "unrecognized" node (`handleUnrecognized`), never dropped;
 *   - the state machines come from the protocol artifact (`../protocol`).
 *
 * Key realities of the current ledger this mapper is built around:
 *   - The log records STATE SNAPSHOTS, not transitions. We diff each snapshot
 *     against the participant's previous shadow value to recover the trigger(s).
 *   - A case may start MID-STREAM (the sample begins with EM already ACTIVE). We
 *     therefore SEED shadow state from the first snapshot observed, not from
 *     `initialState()`. A first observation is a seed (no transition, no validation).
 *   - One ledger entry = one visual moment = one node, even when it carries several
 *     machine advances (e.g. RM accept + VFD fix-ready in the same entry). All
 *     advances are listed in its consequences and the event log.
 */

import type { DemoState, ParticipantState, TimelineEvent, StepSnapshot } from '../types'
import { INITIAL_X_POSITION, PARTICIPANT_COLORS, X_INCREMENT } from '../constants'
import {
  isLegalTransition,
  legalTriggers,
  nextState,
  nextStates,
  machineStates,
  canStartEmbargo,
  embargoViable,
  type MachineName,
} from '../protocol'
import {
  type As2Object,
  type CaseLedgerEntry,
  type CaseStatusSnapshot,
  type RejectedLedgerLine,
  vfdLadderToken,
} from './caseLedgerParser'
import { buildLanes, type LaneDirectory, type ReplayLane } from './replayLanes'
import { isRegisteredSemanticType, renderPhrase, wireForm, type PhraseSlots } from '../semanticRegistry'


// ---------------------------------------------------------------------------
// Shadow protocol state
// ---------------------------------------------------------------------------

interface ShadowState {
  /** Per-participant RM state, keyed by lane id (the participant's actor id). */
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
  /**
   * Lane id → the RM state it held when its Leave (`close_case`) forced it to
   * CLOSED. The case manager then records the leaver's legal path to CLOSED
   * (e.g. VALID → DEFERRED → CLOSED) as status snapshots AFTER the Leave; those
   * snapshots replay the closure the Leave already depicted, not a regression.
   */
  leftFrom: Record<string, string>
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
 * first-class fields (`object.rmState`/`vfState`/`dState`, `caseStatus.emState`/`pxaState`)
 * are authoritative — the `name` is unreliable for EM (see CaseStatusSnapshot).
 */
function parseStatusName(name: string | null | undefined): ParsedTokens {
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
      // Follow every dest: a trigger may have several (EM accept/reject,
      // ADR-0130), and a real ledger may take any of them.
      for (const dest of nextStates(machine, state, trigger)) {
        const nextPath = [...path, trigger]
        if (dest === next) return nextPath
        if (!visited.has(dest)) {
          visited.add(dest)
          queue.push({ state: dest, path: nextPath })
        }
      }
    }
  }
  return null
}

// ---------------------------------------------------------------------------
// Replay context and lanes
// ---------------------------------------------------------------------------

/** What every handler reads and updates while one ledger is replayed. */
interface ReplayContext {
  /** The lanes, pre-scanned from the whole ledger (`buildLanes`). */
  lanes: LaneDirectory
  /** The lanes' participant records, keyed by actor id. */
  participants: Map<string, ParticipantState>
  shadow: ShadowState
  /** This entry's column. */
  x: number
}

/**
 * The lane an entry is drawn in when the ledger names no lane at all for it
 * (no actor, and no CASE_MANAGER): an entry must still be visible (#4729 AC-3).
 * It is made on first use, outside the pre-scanned directory, below every lane,
 * with the fallback palette `nodeColorsFor` gives an unknown key.
 */
const UNATTRIBUTED_LANE = 'unattributed'

function makeParticipant(lane: ReplayLane, visible: boolean): ParticipantState {
  // The CASE_MANAGER records the ledger: it has no report-management state of
  // its own, so it shows 'N/A' rather than a machine state.
  const recorder = lane.kind === 'casemanager'
  return {
    id: lane.id,
    name: lane.label,
    role: lane.roleLabel,
    color: lane.color,
    rmState: recorder ? 'N/A' : 'START',
    vfd: recorder ? 'N/A' : 'vfd',
    embargoAccepted: false,
    hasPublished: false,
    hasClosed: false,
    visible,
    laneIndex: lane.index,
    laneKind: lane.kind,
    palette: lane.palette,
  }
}

/** The lane id of the actor `url` names, or undefined when no lane is that actor. */
function laneOf(ctx: ReplayContext, url: string | null | undefined): string | undefined {
  return ctx.lanes.get(url)?.id
}

/** Whether `laneId` is the CASE_MANAGER's lane. */
function isCaseManagerLane(ctx: ReplayContext, laneId: string | undefined): boolean {
  return ctx.lanes.get(laneId)?.kind === 'casemanager'
}

/** The CASE_MANAGER's lane, if the ledger names one. */
function caseManagerLane(ctx: ReplayContext): string | undefined {
  return ctx.lanes.lanes.find((lane) => lane.kind === 'casemanager')?.id
}

/** The display name of a lane. */
function nameOf(ctx: ReplayContext, laneId: string | undefined): string | undefined {
  return laneId === undefined ? undefined : ctx.participants.get(laneId)?.name
}

/**
 * Mark a lane as having JOINED the case (visible from now on). Idempotent. This is
 * the membership signal that gates consequence-node emission (`consequenceLanes`)
 * and lane rendering: a participant receives consequence nodes only from the event
 * at which it joins onward. Called at the moments a participant actually enters the
 * case — the roster at case creation, an invitee at accept-invite — and
 * defensively whenever a lane is the decision-maker.
 */
function markJoined(ctx: ReplayContext, laneId: string | undefined): void {
  if (laneId === undefined) return
  const p = ctx.participants.get(laneId)
  if (p && !p.visible) ctx.participants.set(laneId, { ...p, visible: true })
}

/** Visible, not-yet-closed lanes other than `decisionLaneId`, in lane order. */
function consequenceLanes(ctx: ReplayContext, decisionLaneId: string): ParticipantState[] {
  return Array.from(ctx.participants.values())
    .filter((p) => p.visible && !p.hasClosed && p.id !== decisionLaneId)
    .sort((a, b) => a.laneIndex - b.laneIndex)
}

// ---------------------------------------------------------------------------
// Registry phrasing
// ---------------------------------------------------------------------------

/**
 * A display name for an actor URL no lane claims, by the Python report's path
 * segment heuristic (DRPT-03-008): the last path segment, title-cased, or the
 * host when that segment is an opaque id.
 */
function urlSegmentLabel(url: string): string {
  const segments = url.replace(/\/+$/, '').split('/')
  const last = segments[segments.length - 1] ?? ''
  const opaque = /^[0-9a-f-]{16,}$/i.test(last) || last.includes(':')
  const word = opaque ? (url.match(/\/\/([^:/]+)/)?.[1] ?? last) : last
  return word.replace(/[-_]+/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

/** The `{actor}` slot for an actor URL: its lane's label, else its path segment. */
function actorSlot(ctx: ReplayContext, url: string | null | undefined): string | undefined {
  if (!url) return undefined
  return nameOf(ctx, laneOf(ctx, url)) ?? urlSegmentLabel(url)
}

/**
 * A friendly label for an activity's object or target, never a bare URI
 * (DRPT-03-001): the lane name of the actor it is or is attributed to, else its
 * type as a lowercase noun (`CaseParticipant` → "case participant"), as the
 * Python report's `friendly_object_label` does.
 */
function referentLabel(ctx: ReplayContext, ref: As2Object | string | null | undefined): string | undefined {
  if (!ref) return undefined
  if (typeof ref === 'string') return nameOf(ctx, laneOf(ctx, ref))
  return (
    nameOf(ctx, laneOf(ctx, ref.id)) ??
    nameOf(ctx, laneOf(ctx, ref.attributedTo)) ??
    ref.type?.replace(/([a-z])([A-Z])/g, '$1 $2').toLowerCase()
  )
}

/**
 * The entry's summary in the semantic registry's phrasing, rendered as the
 * Python demo report's `CaseTimelineEvent.summary` renders it (DRPT-03-002): the
 * actor slot is the acting lane's name, and the object and target slots both
 * take the label of the activity's object. An unfilled slot renders as `—`.
 */
function entryPhrase(ctx: ReplayContext, entry: CaseLedgerEntry): string {
  const snapshot = entry.payloadSnapshot
  const objectLabel = referentLabel(ctx, snapshot?.object)
  return renderPhrase(entry.semanticType, {
    actor: actorSlot(ctx, snapshot?.actor),
    object: objectLabel,
    target: objectLabel,
  })
}

/** The Wire Activity of `semanticType` as a node detail, or none for a type with no form. */
function wireDetail(semanticType: string): string[] {
  const form = wireForm(semanticType)
  return form === undefined ? [] : [form]
}

/** A log-only result: the entry's registry phrase, consuming no column. */
function logOnly(ctx: ReplayContext, entry: CaseLedgerEntry, extra: string[] = []): MapResult {
  return { nodes: [], logLines: [`  ↳ ${entry.semanticType}: ${entryPhrase(ctx, entry)}`, ...extra] }
}

// ---------------------------------------------------------------------------
// Node synthesis
// ---------------------------------------------------------------------------

/** How a node is annotated beyond its label and details. */
interface NodeFlags {
  violation?: string
  inferred?: string
  unrecognized?: string
}

/**
 * Build a decision node in `decisionLaneId`'s lane plus paler consequence nodes
 * (same x, `causedBy = decision.id`) in every other active lane, all carrying
 * `label`. This reproduces the Validated demo's decision/consequence visual
 * grammar (ui/AGENTS.md §2).
 *
 * `flags.violation` / `flags.inferred` / `flags.unrecognized` set the matching
 * annotation on the decision node, with the string as its explanation.
 */
function synthesizeCluster(
  ctx: ReplayContext,
  entry: CaseLedgerEntry,
  decisionLaneId: string,
  label: string,
  decisionDetails: string[],
  consequenceDetails: (lane: ParticipantState) => string[],
  flags: NodeFlags = {}
): TimelineEvent[] {
  // Emitting a decision node means this lane is acting → it has joined the case.
  // This defensive flip covers any lane that produces a node without going through
  // an explicit join handler (e.g. a status/note before its formal join in a
  // reordered ledger); the consequence fan-out below then correctly includes it.
  markJoined(ctx, decisionLaneId)
  const decision = ctx.participants.get(decisionLaneId)
  if (!decision) return []

  const baseTs = new Date(entry.receivedAt).getTime()
  const decisionId = `${entry.id}-decision`
  const nodes: TimelineEvent[] = [
    {
      id: decisionId,
      actor: decision.name,
      participantId: decisionLaneId,
      label,
      x: ctx.x,
      lane: decision.laneIndex,
      type: 'decision',
      consequences: decisionDetails,
      timestamp: baseTs,
      violation: flags.violation !== undefined || undefined,
      violationReason: flags.violation,
      inferred: (flags.violation === undefined && flags.inferred !== undefined) || undefined,
      inferredNote: flags.violation === undefined ? flags.inferred : undefined,
      unrecognized: flags.unrecognized !== undefined || undefined,
      unrecognizedNote: flags.unrecognized,
    },
  ]

  let offset = 1
  for (const lane of consequenceLanes(ctx, decisionLaneId)) {
    nodes.push({
      id: `${entry.id}-${lane.id}-consequence`,
      actor: lane.name,
      participantId: lane.id,
      label,
      x: ctx.x,
      lane: lane.laneIndex,
      type: 'consequence',
      consequences: consequenceDetails(lane),
      causedBy: decisionId,
      timestamp: baseTs + offset,
    })
    offset++
  }

  return nodes
}

/** A node cluster in `laneId` for `entry`, labelled with the registry phrase under `slots`. */
function phrasedCluster(
  ctx: ReplayContext,
  entry: CaseLedgerEntry,
  laneId: string,
  slots: PhraseSlots,
  details: string[] = [],
  consequenceDetails: (lane: ParticipantState) => string[] = () => [],
  flags: NodeFlags = {}
): TimelineEvent[] {
  return synthesizeCluster(
    ctx,
    entry,
    laneId,
    renderPhrase(entry.semanticType, slots),
    [...wireDetail(entry.semanticType), ...details],
    consequenceDetails,
    flags
  )
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
 * lag, e.g. the sample's reporter status still reads EM=ACTIVE after the embargo
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

  // Apply the (usually single-step) forward path. `triggerPath` found it over
  // the legal moves, so the shadow lands on the snapshot; only the last
  // trigger is reported.
  const lastTrigger = path[path.length - 1]
  if (machine === 'em') shadow.emState = snapshot
  else shadow.pxaState = snapshot
  const inferredNote = path.length > 1
    ? `${machine.toUpperCase()} ${current} → ${snapshot} was not a single logged step: the ` +
      `mapper inferred the legal path [${path.join(' → ')}] because intermediate case-level ` +
      `states were not recorded.`
    : undefined
  return { trigger: lastTrigger, from: current, to: snapshot, violation: false, inferredNote }
}

// ---------------------------------------------------------------------------
// Main entry point
// ---------------------------------------------------------------------------

/**
 * Build a replay `DemoState` from normalized ledger entries (see
 * `normalizeLedger`). Walks entries once, in order; emits one node-cluster per
 * meaningful entry and increments the visual column ONLY when a cluster is
 * emitted — so seed-only / no-op entries leave no x-gap.
 *
 * `rejected` is the lines `parseCaseLedger` set aside. They are not replayed, but
 * each one heads the event log with its problems and is carried on the returned
 * state (`rejectedLines`) for the replay view to show.
 */
export function buildTimelineFromCaseLedger(
  entries: CaseLedgerEntry[],
  rejected: readonly RejectedLedgerLine[] = []
): DemoState {
  // Pre-scan the whole ledger for its lanes, then pre-create every participant.
  // Replay knows all actors up front, so lanes get fixed indices immediately with
  // no mid-stream reflow; each is hidden until its participant joins.
  const lanes = buildLanes(entries)
  const participants = new Map<string, ParticipantState>()
  for (const lane of lanes.lanes) participants.set(lane.id, makeParticipant(lane, false))
  const shadow: ShadowState = {
    rm: {},
    vfd: {},
    emState: 'NONE',
    pxaState: 'pxa',
    seededRm: new Set(),
    seededVfd: new Set(),
    pendingQuestionBy: null,
    leftFrom: {},
  }
  const timelineEvents: TimelineEvent[] = []
  const eventLog: string[] = rejected.flatMap(rejectedLineLog)
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
    const ctx: ReplayContext = {
      lanes,
      participants,
      shadow,
      x: INITIAL_X_POSITION + visualEventIndex * X_INCREMENT,
    }
    const result = handleEntry(ctx, entry)

    // Keep the actor panels in sync with the shadow after each entry.
    syncParticipantsToShadow(participants, shadow)

    if (result.nodes.length > 0) {
      timelineEvents.push(...result.nodes)
      // The node's label is a registry phrase; the entry's own phrase follows
      // when the node depicts another act (a report added → its submission).
      const label = result.nodes[0].label
      const phrase = entryPhrase(ctx, entry)
      eventLog.push(`[${timeLabel(entry)}] ${label}${phrase === label ? '' : ` — ${phrase}`}`)
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
    hasPendingReporterNote: shadow.pendingQuestionBy !== null,
    stepSnapshots,
    rejectedLines: [...rejected],
  }
}

/** The event-log lines that report one rejected ledger line. */
function rejectedLineLog(line: RejectedLedgerLine): string[] {
  return [
    `⚠️ REJECTED ${line.source} line ${line.lineNumber}: not a well-formed CaseLedgerEntry, not replayed`,
    ...line.problems.map((problem) => `  ↳ ${problem}`),
  ]
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
    if (vfd !== undefined && vfd !== p.vfd) updates.vfd = vfd
    if (rm === 'CLOSED' && !p.hasClosed) updates.hasClosed = true
    if (Object.keys(updates).length > 0) participants.set(id, { ...p, ...updates })
  }
}

/** Dispatch one ledger entry to its handler. */
function handleEntry(ctx: ReplayContext, entry: CaseLedgerEntry): MapResult {
  switch (entry.semanticType) {
    // Case bootstrap. `create_case` is the current verb; `offer_case_manager_role`
    // is the pre-2026-08 verb kept for replaying older uploaded logs. Both carry
    // the same roster + CaseStatus shape and share one handler.
    case 'create_case':
    case 'offer_case_manager_role':
      return handleCreateCase(ctx, entry)
    case 'validate_report':
      return handleValidateReport(ctx, entry)
    // A note reaches the case as an `Add(Note)[target=VulnerabilityCase]` carrying the note
    // (`add_note_to_case`). `create_note` is the pre-2026-10 verb (a received
    // `Create(Note)`, retired by #4707), kept for replaying older uploaded logs.
    case 'create_note':
    case 'add_note_to_case':
      return handleNote(ctx, entry)
    case 'add_participant_status_to_participant':
      return handleParticipantStatus(ctx, entry)
    case 'add_case_status_to_case':
      return handleCaseStatus(ctx, entry)
    case 'remove_embargo_event_from_case':
      return handleRemoveEmbargo(ctx, entry)
    case 'close_case':
      return handleCloseCase(ctx, entry)
    case 'invite_actor_to_case':
      return handleInvite(ctx, entry)
    case 'accept_invite_actor_to_case':
      return handleAcceptInvite(ctx, entry)
    case 'reject_invite_actor_to_case':
      return handleRejectInvite(ctx, entry)
    case 'offer_case_ownership_transfer':
      return handleOfferOwnershipTransfer(ctx, entry)
    case 'accept_case_ownership_transfer':
      return handleAcceptOwnershipTransfer(ctx, entry)
    case 'submit_report':
    case 'add_report_to_case':
      // `add_report_to_case` is the current verb (actor = recorder/owner, reporter =
      // object.attributedTo); `submit_report` is the older verb (actor = reporter).
      // handleReport resolves the reporter lane from whichever is present.
      return handleReport(ctx, entry)
    case 'offer_actor_to_case':
      // First leg of the ADR-0026 suggest-actor handshake (a participant
      // recommends an actor). Drawn as one node; the other legs
      // (`offer_case_participant`, `accept_offer_case_participant`,
      // `accept_actor_recommendation`) are log-only, as every other registered
      // type with no handler is.
      return handleOfferActorToCase(ctx, entry)
    case 'accept_case_manager_role':
    case 'add_case_participant':
      // Retired verbs (the CASE_MANAGER role offer, and the roster entry now
      // `create_case_participant`), kept so older uploaded logs replay: roster
      // bookkeeping, log-only like their current counterparts.
      return logOnly(ctx, entry)
    default:
      // A registered type with no visual handler (roster bookkeeping such as
      // `create_case_participant`, `engage_case`, the suggest-actor legs) is
      // recorded in the event log in the registry's own phrasing. A type the
      // registry does not list is from another protocol version (or a corrupt
      // line) and is drawn as an unrecognized node, so it is never only a line.
      if (isRegisteredSemanticType(entry.semanticType)) return logOnly(ctx, entry)
      return handleUnrecognized(ctx, entry)
  }
}

// --- an unregistered semantic type → a visible "unrecognized" node ------------

/**
 * An entry whose semantic type the registry does not list (#4729 AC-3). It is
 * drawn in its actor's lane, or the CASE_MANAGER's when no lane is its actor,
 * as a node flagged `unrecognized` and labelled with the humanized type
 * (DRPT-03-006). Its content is not interpreted: no machine state changes.
 */
function handleUnrecognized(ctx: ReplayContext, entry: CaseLedgerEntry): MapResult {
  const laneId = laneOf(ctx, entry.payloadSnapshot?.actor) ?? caseManagerLane(ctx) ?? unattributedLane(ctx)
  const note =
    `The semantic registry does not list "${entry.semanticType}", so this entry was not ` +
    `interpreted: it may come from another protocol version.`
  const nodes = synthesizeCluster(
    ctx,
    entry,
    laneId,
    `Unrecognized: ${renderPhrase(entry.semanticType)}`,
    [`semanticType: ${entry.semanticType}`, ...(entry.payloadSnapshot?.type ? [`payload type: ${entry.payloadSnapshot.type}`] : [])],
    () => [],
    { unrecognized: note }
  )
  return {
    nodes,
    logLines: [`  ↳ UNRECOGNIZED semanticType "${entry.semanticType}" (not in the semantic registry)`],
  }
}

/** The lane for an entry no lane can hold, created on first use. */
function unattributedLane(ctx: ReplayContext): string {
  if (!ctx.participants.has(UNATTRIBUTED_LANE)) {
    const lane: ReplayLane = {
      id: UNATTRIBUTED_LANE,
      roles: [],
      kind: 'participant',
      label: 'Unattributed',
      roleLabel: '',
      palette: 'participant',
      color: PARTICIPANT_COLORS.reporter,
      index: ctx.participants.size,
    }
    ctx.participants.set(UNATTRIBUTED_LANE, makeParticipant(lane, true))
  }
  return UNATTRIBUTED_LANE
}

// --- create_case (or legacy offer_case_manager_role) → case-created bootstrap -

/**
 * Case bootstrap. Seeds the case-level EM/PXA and the per-participant
 * report-receipt state, then emits the case-created cluster in the lane of the
 * entry's actor (the CASE_MANAGER).
 */
function handleCreateCase(ctx: ReplayContext, entry: CaseLedgerEntry): MapResult {
  const { shadow } = ctx
  const logLines: string[] = []
  const obj = entry.payloadSnapshot?.object

  // The roster at creation: the case's actor→participant index (its keys are the
  // actor URLs) and the recording actor. Only these lanes join now; late joiners
  // (invited vendors / coordinators) become visible at their own accept-invite.
  const roster = new Set<string>()
  for (const url of Object.keys(obj?.actorParticipantIndex ?? {})) {
    const laneId = laneOf(ctx, url)
    if (laneId !== undefined) roster.add(laneId)
  }
  const recorder = laneOf(ctx, entry.payloadSnapshot?.actor)
  if (recorder !== undefined) roster.add(recorder)
  for (const laneId of roster) markJoined(ctx, laneId)

  // Seed case-level EM/PXA from the structured CaseStatus (trust the structured
  // fields, not its `name` — the sample's name "NONE pxa" lies).
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
  // rv/rvv/rvcv-* but the COORDINATOR in rcv/rccv-*. It is the case's
  // `attributedTo` when that names a participant lane other than a Reporter or
  // the CASE_MANAGER; else the one such lane on the roster.
  //
  // GUARDED on `=== undefined` (not on seededRm): some ledgers log
  // validate_report BEFORE the offer, so the receiver's RM may already have
  // advanced to VALID — seeding here would regress it. We only set the baseline
  // when never touched, but always mark the lane seeded so later status snapshots
  // are treated as transitions (and validated), not re-seeded.
  const isOwnerCandidate = (laneId: string | undefined) => {
    const kind = ctx.lanes.get(laneId)?.kind
    return kind !== undefined && kind !== 'reporter' && kind !== 'casemanager'
  }
  const viaAttr = laneOf(ctx, obj?.attributedTo)
  const receiverLane = isOwnerCandidate(viaAttr) ? viaAttr : [...roster].find(isOwnerCandidate)
  const seeded = new Map<string, string[]>()
  const seed = (laneId: string, detail: string) => seeded.set(laneId, [...(seeded.get(laneId) ?? []), detail])
  if (receiverLane !== undefined) {
    if (shadow.rm[receiverLane] === undefined) shadow.rm[receiverLane] = 'RECEIVED'
    shadow.seededRm.add(receiverLane)
    seed(receiverLane, `RM → ${shadow.rm[receiverLane]}`)
    // VFD baseline: a Vendor receiver starts at the machine's INITIAL state `vfd`;
    // the recorder logs `vendor_becomes_aware` (vfd→Vfd) as a later snapshot. A
    // Coordinator receiver develops no fix, so its VFD is left unseeded.
    if (ctx.lanes.get(receiverLane)?.roles.includes('vendor')) {
      if (shadow.vfd[receiverLane] === undefined) shadow.vfd[receiverLane] = 'vfd'
      shadow.seededVfd.add(receiverLane)
      seed(receiverLane, `VFD → ${shadow.vfd[receiverLane]}`)
    }
  }
  // A Reporter enters CVD already at RM.ACCEPTED (validated/prioritized privately
  // before disclosure). VFD is seeded lazily from its first status snapshot.
  for (const laneId of roster) {
    if (ctx.lanes.get(laneId)?.kind !== 'reporter') continue
    if (shadow.rm[laneId] === undefined) shadow.rm[laneId] = 'ACCEPTED'
    shadow.seededRm.add(laneId)
    seed(laneId, `RM → ${shadow.rm[laneId]}`)
  }

  const laneId = recorder ?? caseManagerLane(ctx) ?? unattributedLane(ctx)
  const nodes = phrasedCluster(
    ctx,
    entry,
    laneId,
    { actor: actorSlot(ctx, entry.payloadSnapshot?.actor) },
    [`EM: ${shadow.emState}`, `PXA: ${shadow.pxaState}`],
    (lane) => seeded.get(lane.id) ?? []
  )
  return { nodes, logLines }
}

// --- add_report_to_case / submit_report → reporter's report -------------------

/**
 * The reporter's vulnerability report is added to the case. Two verb shapes:
 *   - `add_report_to_case` (2026-08): `actor` = the recorder/owner, and the
 *     reporter is `object.attributedTo` (`object.type = VulnerabilityReport`).
 *   - `submit_report` (legacy): `actor` = the reporter directly.
 * Either way the node is the Reporter's submission, in the Reporter's lane, so
 * it is phrased as the act it follows: the registry's `submit_report`, with the
 * Reporter as its actor. The event log adds the entry's own phrase. This is a
 * demo-kind node (no machine slot of its own — the reporter's private RM
 * traversal to ACCEPTED is seeded at case creation), so the shadow is untouched.
 */
function handleReport(ctx: ReplayContext, entry: CaseLedgerEntry): MapResult {
  const snapshot = entry.payloadSnapshot
  const laneId = laneOf(ctx, snapshot?.object?.attributedTo) ?? laneOf(ctx, snapshot?.actor)
  if (laneId === undefined) return logOnly(ctx, entry)
  const reportName = snapshot?.object?.name
  const nodes = synthesizeCluster(
    ctx,
    entry,
    laneId,
    renderPhrase('submit_report', { actor: nameOf(ctx, laneId) }),
    [...wireDetail('submit_report'), ...(reportName ? [`Report: "${reportName}"`] : [])],
    () => []
  )
  return { nodes, logLines: [] }
}

// --- offer_actor_to_case → ADR-0026 suggest-actor recommendation -----------

/**
 * First leg of the extension flow's suggest-actor handshake: a participant
 * recommends a new actor to the case. The CASE_MANAGER then forwards it to the
 * Case Owner (`offer_case_participant`) who approves it
 * (`accept_offer_case_participant`) — both log-only — after which the regular
 * invite/accept pair performs the actual join.
 *
 * A deliberate demo OVERLAY of the protocol's ADR-0026 suggest-actor-to-case flow:
 * the recommendation is procedural coordination, not a declarative state-machine
 * step, so it has no artifact to defer to. One node in the recommender's lane.
 */
function handleOfferActorToCase(ctx: ReplayContext, entry: CaseLedgerEntry): MapResult {
  const snapshot = entry.payloadSnapshot
  const laneId = laneOf(ctx, snapshot?.actor)
  if (laneId === undefined) return logOnly(ctx, entry)
  const recommended = referentLabel(ctx, snapshot?.object) ?? snapshot?.object?.name ?? undefined
  const nodes = phrasedCluster(ctx, entry, laneId, { actor: nameOf(ctx, laneId), object: recommended })
  return { nodes, logLines: [] }
}

// --- invite_actor_to_case → an existing member invites a new actor ---------

/**
 * An invitation to join the case.
 *
 * Two payload shapes appear in practice:
 *   - EMPTY (`actor` absent) — older logs, and a leading placeholder entry that
 *     precedes the populated one. Carries no attribution, so it's log-only; the
 *     join is shown by the later accept-invite.
 *   - POPULATED — carries the invitee (`object`), the target case, and the real
 *     inviter in `target.attributedTo` (the case owner — NOT the `actor`, which
 *     is the CASE_MANAGER relaying it). The node goes in the INVITER's lane so the
 *     pair reads "Owner invited X" → "X accepted".
 */
function handleInvite(ctx: ReplayContext, entry: CaseLedgerEntry): MapResult {
  const snapshot = entry.payloadSnapshot
  if (!snapshot?.actor) return logOnly(ctx, entry)
  const inviterLane = laneOf(ctx, snapshot.target?.attributedTo) ?? laneOf(ctx, snapshot.actor)
  if (inviterLane === undefined) return logOnly(ctx, entry)
  const invitee = referentLabel(ctx, snapshot.object) ?? snapshot.object?.name ?? undefined
  const nodes = phrasedCluster(ctx, entry, inviterLane, { actor: nameOf(ctx, inviterLane), object: invitee })
  return { nodes, logLines: [] }
}

// --- accept_invite_actor_to_case → invited participant joins ------------------

/**
 * A participant accepts an invitation to the case. Here its lane joins and its
 * report-receipt state is seeded (RM=RECEIVED, and VFD=vfd for a Vendor, like
 * the receiver at case creation), in a node in the joiner's lane. The recorded
 * `actor` is the joiner.
 */
function handleAcceptInvite(ctx: ReplayContext, entry: CaseLedgerEntry): MapResult {
  const { shadow } = ctx
  const laneId = laneOf(ctx, entry.payloadSnapshot?.actor)
  if (laneId === undefined) return logOnly(ctx, entry)
  const logLines: string[] = []
  const details: string[] = []

  // Guarded so a pre-existing status snapshot isn't regressed. Every joiner
  // receives & manages the report, so RM is seeded for all; VFD only for a Vendor
  // (a Coordinator builds no fix). The VFD seed is the machine's INITIAL state
  // `vfd`: the recorder logs the joiner's `vendor_becomes_aware` explicitly.
  if (!shadow.seededRm.has(laneId)) {
    shadow.rm[laneId] = 'RECEIVED'
    shadow.seededRm.add(laneId)
    details.push('RM → RECEIVED')
    logLines.push(`  ↳ seeded ${nameOf(ctx, laneId)} RM = RECEIVED (invite accepted)`)
  }
  if (ctx.lanes.get(laneId)?.roles.includes('vendor') && !shadow.seededVfd.has(laneId)) {
    shadow.vfd[laneId] = 'vfd'
    shadow.seededVfd.add(laneId)
    details.push('VFD → vfd')
  }

  const nodes = phrasedCluster(ctx, entry, laneId, { actor: nameOf(ctx, laneId) }, details)
  return { nodes, logLines }
}

// --- reject_invite_actor_to_case → invitee declines -------------------------

/**
 * An invited actor declines the invitation (the rcv-reject scenario). The
 * recorded `actor` is the rejecter. No machine change — the rejecter never joins
 * — but the decision node makes its lane visible from here on.
 */
function handleRejectInvite(ctx: ReplayContext, entry: CaseLedgerEntry): MapResult {
  const laneId = laneOf(ctx, entry.payloadSnapshot?.actor)
  if (laneId === undefined) return logOnly(ctx, entry)
  const nodes = phrasedCluster(ctx, entry, laneId, { actor: nameOf(ctx, laneId) })
  return { nodes, logLines: [] }
}

// --- offer/accept_case_ownership_transfer → case-ownership handoff -----------

/**
 * Case-ownership HANDOFF (the `-handoff` scenarios). The current case owner
 * offers to transfer ownership to another actor, who then accepts: an
 * offer→accept node pair across the two lanes.
 *
 * A deliberate demo OVERLAY (ui/AGENTS.md §9): ownership transfer moves the
 * CASE_OWNER role, but it is NOT an RM/EM/VFD/PXA machine transition, so it
 * touches NO shadow machine state. Nor does it move a lane: a lane is keyed on
 * the actor id and its label leaves CASE_OWNER out (`./replayLanes`), so both
 * participants keep their lanes and labels through the handoff.
 *
 * `offer`: `actor` = the actor that sent the offer (the CASE_MANAGER relaying it
 * in the current recordings; the outgoing owner in older logs); `target` = the
 * INCOMING owner. The node goes in the sender's lane.
 */
function handleOfferOwnershipTransfer(ctx: ReplayContext, entry: CaseLedgerEntry): MapResult {
  const snapshot = entry.payloadSnapshot
  const outgoingLane = laneOf(ctx, snapshot?.actor)
  if (outgoingLane === undefined) return logOnly(ctx, entry)
  const incoming =
    nameOf(ctx, laneOf(ctx, snapshot?.target?.id ?? snapshot?.target?.attributedTo)) ??
    snapshot?.target?.name ??
    undefined
  const nodes = phrasedCluster(ctx, entry, outgoingLane, { actor: nameOf(ctx, outgoingLane), object: incoming })
  return { nodes, logLines: [] }
}

/** The incoming owner accepts the ownership transfer: a node in its lane. */
function handleAcceptOwnershipTransfer(ctx: ReplayContext, entry: CaseLedgerEntry): MapResult {
  const incomingLane = laneOf(ctx, entry.payloadSnapshot?.actor)
  if (incomingLane === undefined) return logOnly(ctx, entry)
  const nodes = phrasedCluster(ctx, entry, incomingLane, { actor: nameOf(ctx, incomingLane) })
  return { nodes, logLines: [] }
}

// --- validate_report → rm validate -----------------------------------------

function handleValidateReport(ctx: ReplayContext, entry: CaseLedgerEntry): MapResult {
  const { shadow } = ctx
  const laneId = laneOf(ctx, entry.payloadSnapshot?.actor)
  if (laneId === undefined) return logOnly(ctx, entry)
  const logLines: string[] = []

  const src = shadow.rm[laneId] ?? 'RECEIVED'
  let violation: string | undefined
  if (isLegalTransition('rm', src, 'validate')) {
    shadow.rm[laneId] = nextState('rm', src, 'validate')!
  } else {
    violation =
      `The RM machine has no "validate" transition from ${src}. ` +
      `"validate" is only legal from RECEIVED or INVALID. Recording it from ` +
      `${src} would skip or repeat the report-validation step.`
    logLines.push(
      `  ↳ PROTOCOL VIOLATION: rm "validate" illegal from "${src}" (subject=${nameOf(ctx, laneId)}); forcing shadow → VALID`
    )
    shadow.rm[laneId] = 'VALID'
  }

  const name = nameOf(ctx, laneId)
  const nodes = phrasedCluster(
    ctx,
    entry,
    laneId,
    { actor: name },
    [`RM: ${src} → ${shadow.rm[laneId]}`],
    () => [`${name}: RM → ${shadow.rm[laneId]}`],
    { violation }
  )
  return { nodes, logLines }
}

// --- create_note / add_note_to_case → a note (demo-kind, no machine slot) ------

/**
 * The legacy `Create(Note)` wire form, for the retired `create_note` verb the
 * registry no longer lists (#4707).
 */
const LEGACY_NOTE_FORM = 'Create(Note)'

function handleNote(ctx: ReplayContext, entry: CaseLedgerEntry): MapResult {
  const { shadow } = ctx
  const laneId = laneOf(ctx, entry.payloadSnapshot?.actor)
  if (laneId === undefined) return logOnly(ctx, entry)
  const obj = entry.payloadSnapshot?.object
  const content = (obj?.content ?? '').trim()
  const snippet = content.length > 90 ? content.slice(0, 87) + '…' : content

  // The ledger lacks inReplyTo linkage, so whether a note awaits an answer is a
  // heuristic: the first unanswered note is a question; the next note from a
  // DIFFERENT actor while a question is pending is its answer.
  const isAnswer =
    obj?.inReplyTo != null || (shadow.pendingQuestionBy !== null && shadow.pendingQuestionBy !== laneId)
  shadow.pendingQuestionBy = isAnswer ? null : laneId

  const details = [
    ...(entry.semanticType === 'create_note' ? [LEGACY_NOTE_FORM] : []),
    ...(obj?.name ? [`Note: "${obj.name}"`] : []),
    ...(snippet ? [snippet] : []),
  ]
  const nodes = phrasedCluster(ctx, entry, laneId, { actor: nameOf(ctx, laneId) }, details, () =>
    snippet ? [snippet] : []
  )
  return { nodes, logLines: [] }
}

// --- add_participant_status_to_participant → snapshot diff ------------------

/** One machine advance an entry carries. */
interface MachineChange {
  machine: MachineName
  from: string
  to: string
  trigger: string
}

/** A change as a node detail: `RM: VALID → ACCEPTED (accept)`. */
function changeDetail(change: MachineChange): string {
  return `${change.machine.toUpperCase()}: ${change.from} → ${change.to} (${change.trigger})`
}

/** A change as a consequence detail, naming whose state moved. */
function changeConsequence(change: MachineChange, subject: string | undefined): string {
  const whose = change.machine === 'em' || change.machine === 'pxa' ? 'Case' : subject ?? '—'
  return `${whose}: ${change.machine.toUpperCase()} → ${change.to}`
}

/**
 * Apply a case-level snapshot's PXA, then EM, to the shadow, collecting the
 * changes, violations and inferences, and run the cross-machine
 * embargo-viability check (artifact rule): even a per-machine-LEGAL EM advance
 * violates the protocol if the embargo is being negotiated in a CS state that
 * forbids it. PXA goes first so the check sees this entry's publicity.
 */
function applyCaseLevel(
  shadow: ShadowState,
  snapshot: { pxaState?: string; emState?: string },
  changes: MachineChange[],
  violations: string[],
  inferences: string[],
  logLines: string[]
): void {
  for (const machine of ['pxa', 'em'] as const) {
    const change = applyCaseLevelForward(
      machine,
      shadow,
      machine === 'pxa' ? snapshot.pxaState : snapshot.emState,
      logLines
    )
    if (!change) continue
    changes.push({ machine, from: change.from, to: change.to, trigger: change.trigger })
    if (change.violation && change.reason) violations.push(change.reason)
    if (change.inferredNote) inferences.push(change.inferredNote)
    if (machine !== 'em') continue
    // Starting a new embargo (into PROPOSED) needs `canStartEmbargo`;
    // establishing/continuing one (into ACTIVE/REVISE) needs `embargoViable`.
    const enteringNew = change.to === 'PROPOSED'
    const enteringActive = change.to === 'ACTIVE' || change.to === 'REVISE'
    const viabilityOk = enteringNew
      ? canStartEmbargo(shadow.pxaState)
      : enteringActive
      ? embargoViable(shadow.pxaState)
      : true
    if (!viabilityOk) {
      violations.push(
        `Embargo entered ${change.to} while the case is at PXA ${shadow.pxaState}, but the ` +
          `protocol forbids ${enteringNew ? 'proposing' : 'establishing/continuing'} an embargo ` +
          `once the vulnerability is public, an exploit is public, or attacks are observed ` +
          `(per the artifact's embargo-viability rule).`
      )
      logLines.push(
        `  ↳ PROTOCOL VIOLATION: EM → ${change.to} not viable at PXA=${shadow.pxaState} (embargo-viability rule)`
      )
    }
  }
}

/**
 * Diff one participant-machine snapshot (`rm` or `vfd`) for `laneId` against the
 * shadow: seed it the first time, else record the legal path to it, or flag it
 * when no legal path exists. The shadow lands on the snapshot either way.
 */
function applyParticipantMachine(
  shadow: ShadowState,
  machine: 'rm' | 'vfd',
  laneId: string,
  laneName: string | undefined,
  next: string,
  changes: MachineChange[],
  violations: string[],
  inferences: string[],
  logLines: string[]
): void {
  const seededSet = machine === 'rm' ? shadow.seededRm : shadow.seededVfd
  const states = shadow[machine]
  const label = machine.toUpperCase()
  if (!seededSet.has(laneId)) {
    states[laneId] = next
    seededSet.add(laneId)
    logLines.push(`  ↳ seeded ${laneName} ${label} = ${next} (first snapshot)`)
    return
  }
  const src = states[laneId]
  if (next === src) return
  const path = triggerPath(machine, src, next)
  if (path && path.length > 0) {
    changes.push({ machine, from: src, to: next, trigger: path[path.length - 1] })
    if (path.length > 1) {
      logLines.push(`  ↳ ${label} path: ${src} → ${next} via ${path.join(', ')}`)
      inferences.push(
        `${label} ${src} → ${next} was not a single logged step: the mapper inferred the ` +
          `legal path [${path.join(' → ')}] because intermediate states were not recorded.`
      )
    }
  } else {
    // Record the illegal jump as a change so a flagged node still renders.
    // Without this, a status entry whose ONLY content is an illegal jump would
    // hit the `changes.length === 0` early return and be invisible.
    changes.push({ machine, from: src, to: next, trigger: 'illegal' })
    violations.push(
      machine === 'rm'
        ? `RM cannot reach ${next} from ${src}: no sequence of legal RM ` +
            `transitions connects them. The report's management state jumped illegally.`
        : `VFD cannot reach ${next} from ${src}: the fix-development ladder ` +
            `(vfd → Vfd → VFd → VFD) advances one milestone at a time and cannot ` +
            `skip or regress. This snapshot jumped illegally.`
    )
    logLines.push(
      `  ↳ PROTOCOL VIOLATION: ${machine} has no path "${src}" → "${next}" (subject=${laneName}); forcing shadow`
    )
  }
  states[laneId] = next
}

function handleParticipantStatus(ctx: ReplayContext, entry: CaseLedgerEntry): MapResult {
  const { shadow } = ctx
  const snapshot = entry.payloadSnapshot
  const obj = snapshot?.object
  const subjectUrl = obj?.attributedTo ?? snapshot?.target?.attributedTo ?? snapshot?.actor
  const laneId = laneOf(ctx, subjectUrl)
  const logLines: string[] = []
  const changes: MachineChange[] = []
  const violations: string[] = []
  const inferences: string[] = []

  // The CASE_MANAGER has no report-management disposition of its own and stays
  // at RM/VFD = 'N/A'. The ledger attributes a case-management RM lifecycle to it,
  // but that mirrors the OWNER's progress, which the owner's own lane carries. So
  // RM/VFD on its lane are ignored; case-level EM/PXA still apply below.
  const tokens = parseStatusName(obj?.name)
  const subject = nameOf(ctx, laneId)

  if (laneId !== undefined && !isCaseManagerLane(ctx, laneId)) {
    const rmNext = obj?.rmState ?? tokens.rm
    if (rmNext !== undefined) {
      const recordedByCaseManager = isCaseManagerLane(ctx, laneOf(ctx, snapshot?.actor))
      if (shadow.seededRm.has(laneId) && isRecordedClosePath(shadow, laneId, rmNext, recordedByCaseManager)) {
        // Shadow stays CLOSED: the Leave already depicted this participant's
        // closure. Advance the cursor so the next step must follow this one.
        logLines.push(
          `  ↳ recorded close path after Leave: ${subject} RM ${shadow.leftFrom[laneId]} → ${rmNext} → CLOSED`
        )
        shadow.leftFrom[laneId] = rmNext
      } else {
        // Any close path is over: CLOSED was recorded again, or this snapshot is
        // not its next step and is judged as a transition.
        delete shadow.leftFrom[laneId]
        applyParticipantMachine(shadow, 'rm', laneId, subject, rmNext, changes, violations, inferences, logLines)
      }
    }
    const vfdNext = vfdLadderToken(obj) ?? tokens.vfd
    if (vfdNext !== undefined) {
      applyParticipantMachine(shadow, 'vfd', laneId, subject, vfdNext, changes, violations, inferences, logLines)
    }
  }

  // Case-level PXA / EM (forward-only; participant snapshots can be stale, but a
  // snapshot on no legal trajectory is a violation — see applyCaseLevelForward).
  applyCaseLevel(shadow, readCaseStatus(entry) ?? {}, changes, violations, inferences, logLines)

  // No meaningful change (only seeds / no-ops) → no node, no column.
  if (changes.length === 0) return { nodes: [], logLines }
  const decisionLane = laneId ?? caseManagerLane(ctx) ?? unattributedLane(ctx)
  const nodes = phrasedCluster(
    ctx,
    entry,
    decisionLane,
    { actor: actorSlot(ctx, snapshot?.actor), object: subject },
    changes.map(changeDetail),
    () => changes.map((c) => changeConsequence(c, subject)),
    { violation: violations.join(' ') || undefined, inferred: inferences.join(' ') || undefined }
  )
  return { nodes, logLines }
}

// --- add_case_status_to_case → case-level EM/PXA snapshot -------------------

/**
 * A first-class case-level status snapshot. Here the `object` IS the
 * `CaseStatus`, so `emState`/`pxaState` sit directly on it. Applies the EM/PXA
 * advances forward-only (as `handleParticipantStatus` does) and emits a node in
 * the recording actor's lane only when something changed; a redundant
 * re-snapshot is log-only and consumes no column.
 */
function handleCaseStatus(ctx: ReplayContext, entry: CaseLedgerEntry): MapResult {
  const obj = entry.payloadSnapshot?.object
  const tokens = parseStatusName(obj?.name)
  const logLines: string[] = []
  const changes: MachineChange[] = []
  const violations: string[] = []
  const inferences: string[] = []
  applyCaseLevel(
    ctx.shadow,
    { pxaState: obj?.pxaState ?? tokens.pxa, emState: obj?.emState ?? tokens.em },
    changes,
    violations,
    inferences,
    logLines
  )
  if (changes.length === 0) return { nodes: [], logLines }

  const laneId = laneOf(ctx, entry.payloadSnapshot?.actor) ?? caseManagerLane(ctx) ?? unattributedLane(ctx)
  const nodes = phrasedCluster(
    ctx,
    entry,
    laneId,
    { actor: actorSlot(ctx, entry.payloadSnapshot?.actor) },
    changes.map(changeDetail),
    () => changes.map((c) => changeConsequence(c, undefined)),
    { violation: violations.join(' ') || undefined, inferred: inferences.join(' ') || undefined }
  )
  return { nodes, logLines }
}

// --- remove_embargo_event_from_case → em terminate --------------------------

function handleRemoveEmbargo(ctx: ReplayContext, entry: CaseLedgerEntry): MapResult {
  const { shadow } = ctx
  const logLines: string[] = []
  const src = shadow.emState
  let violation: string | undefined
  if (isLegalTransition('em', src, 'terminate')) {
    shadow.emState = nextState('em', src, 'terminate')!
  } else {
    violation =
      `The EM machine has no "terminate" transition from ${src}. ` +
      `An embargo can only be terminated from ACTIVE or REVISE. From ${src} ` +
      `there is no active embargo to end.`
    logLines.push(`  ↳ PROTOCOL VIOLATION: em "terminate" illegal from "${src}"; forcing shadow → EXITED`)
    shadow.emState = 'EXITED'
  }

  const laneId = laneOf(ctx, entry.payloadSnapshot?.actor) ?? caseManagerLane(ctx) ?? unattributedLane(ctx)
  const nodes = phrasedCluster(
    ctx,
    entry,
    laneId,
    { actor: actorSlot(ctx, entry.payloadSnapshot?.actor) },
    [`EM: ${src} → ${shadow.emState} (terminate)`],
    () => [`Case: EM → ${shadow.emState}`],
    { violation }
  )
  return { nodes, logLines }
}

// --- close_case → a participant's self-declaratory Leave (CM-23-012) -----------

/**
 * Whether an RM snapshot of `rmNext` for a lane its Leave already CLOSED is the
 * next step of the leaver's legal path to CLOSED, as the case manager records it
 * after the Leave. It must be recorded by the case manager
 * (`recordedByCaseManager`), be ONE legal RM transition from the cursor
 * `shadow.leftFrom[laneId]` (the rung the lane left from, then each recorded
 * step), and be strictly nearer CLOSED than the cursor (fewer legal transitions
 * from it to CLOSED). The distance rule rejects the ACCEPTED ↔ DEFERRED cycle and
 * any step away from CLOSED; the one-step rule rejects a skipped rung. Anything
 * else after a Leave is judged as a transition.
 */
function isRecordedClosePath(
  shadow: ShadowState,
  laneId: string,
  rmNext: string,
  recordedByCaseManager: boolean
): boolean {
  const cursor = shadow.leftFrom[laneId]
  if (cursor === undefined || !recordedByCaseManager) return false
  if (shadow.rm[laneId] !== 'CLOSED' || rmNext === 'CLOSED') return false
  const toStep = triggerPath('rm', cursor, rmNext)
  const fromCursor = triggerPath('rm', cursor, 'CLOSED')
  const fromNext = triggerPath('rm', rmNext, 'CLOSED')
  if (toStep === null || toStep.length !== 1) return false
  if (fromCursor === null || fromNext === null) return false
  return fromNext.length < fromCursor.length
}

function handleCloseCase(ctx: ReplayContext, entry: CaseLedgerEntry): MapResult {
  const { shadow } = ctx
  const logLines: string[] = []

  // Identify the CLOSER. The recorded `actor` is the participant closing its own
  // report, while `object.attributedTo` is the case owner — NOT the closer. Legacy
  // logs inverted this (`actor` = the CASE_MANAGER, `attributedTo` = the closed
  // participant), so `attributedTo` is the closer only when `actor` is the
  // CASE_MANAGER or absent.
  const actorLane = laneOf(ctx, entry.payloadSnapshot?.actor)
  const attrLane = laneOf(ctx, entry.payloadSnapshot?.object?.attributedTo)
  const closerLane =
    actorLane !== undefined && !isCaseManagerLane(ctx, actorLane)
      ? actorLane
      : attrLane !== undefined && !isCaseManagerLane(ctx, attrLane)
      ? attrLane
      : actorLane ?? caseManagerLane(ctx) ?? unattributedLane(ctx)

  // Advance the closer's RM to CLOSED as a SELF-DECLARATORY LEAVE — from ANY rung,
  // with NO RM-machine adjacency check. A `close_case` ledger entry is the leaving
  // actor's own Leave(VulnerabilityCase): per CM-23-012 / ADR-0084 a Leave is that
  // actor's authoritative closure act, so it advances ONLY that actor to RM.CLOSED
  // regardless of the rung it currently holds, intentionally OVERRIDING the RM
  // adjacency rule (CLOSED reachable only from ACCEPTED / DEFERRED / INVALID) that
  // the RM machine — and thus protocol_states.json — enforces.
  //
  // This is a DELIBERATE procedural overlay, NOT a machine transition. The Leave /
  // `force_rm_state` rule lives in behavior-tree code (leave.py, close_case_effect.py)
  // and a prose spec statement (CM-23-038); it has no exportable transition table, so
  // it MUST NOT be judged via isLegalTransition('rm', …, 'close') nor "fixed" by adding
  // an edge to the artifact — the RM machine is shared by every role, so doing so would
  // make it falsely accept an un-disposed report `close` for a vendor too, masking a
  // real violation. See ui/AGENTS.md §9 (declarative-vs-procedural boundary). The
  // CM-23-012 citation here is the anti-drift tripwire if the rule ever changes.
  const details: string[] = []
  if (!isCaseManagerLane(ctx, closerLane) && shadow.seededRm.has(closerLane) && shadow.rm[closerLane] !== 'CLOSED') {
    const src = shadow.rm[closerLane]
    shadow.rm[closerLane] = 'CLOSED'
    shadow.leftFrom[closerLane] = src
    details.push(`RM: ${src} → CLOSED (Leave)`)
    logLines.push(`  ↳ close_case: ${nameOf(ctx, closerLane)} Leave → RM ${src} → CLOSED (CM-23-012)`)
  }

  const closer = nameOf(ctx, closerLane)
  const nodes = phrasedCluster(
    ctx,
    entry,
    closerLane,
    { actor: closer },
    [...details, `EM: ${shadow.emState}`],
    () => (details.length > 0 ? [`${closer}: RM → CLOSED`] : [])
  )
  return { nodes, logLines }
}
