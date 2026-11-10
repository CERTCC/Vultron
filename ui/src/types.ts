/**
 * Type definitions for the Vultron multi-vendor demo
 */

import type { RejectedLedgerLine } from './utils/caseLedgerParser'
import type { LaneKind } from './utils/replayLanes'

export interface ParticipantState {
  id: string
  name: string
  role: string
  color: string
  rmState: string
  vfd: string
  embargoAccepted: boolean
  embargoProposedToParticipant?: boolean  // Track if embargo was proposed to this participant (for late joiners)
  hasPublished: boolean
  hasClosed: boolean
  visible: boolean
  laneIndex: number
  hasRepliedToCurrentNote?: boolean  // Track if participant replied to current note
  laneKind?: LaneKind  // Log Replay only: what the lane does, from its ledger roles
                       // (utils/replayLanes.ts); the casemanager lane has no RM/VFD.
  palette?: string     // Log Replay only: the `nodeColorsFor` key of the lane's colors
}

export interface TimelineEvent {
  id: string
  actor: string
  participantId?: string  // Which specific participant (e.g., 'vendor-1', 'vendor-2')
  label: string
  x: number
  lane: number
  type: 'decision' | 'consequence'
  consequences: string[]
  causedBy?: string
  enablesNext?: boolean
  timestamp?: number
  violation?: boolean  // set by the validating replay mapper when the derived
                       // protocol trigger was illegal from the shadow source state
                       // (see ui/src/utils/caseLedgerMapper.ts). Renderers may
                       // style flagged nodes (e.g. red); all other code ignores it.
  violationReason?: string  // human-readable explanation of WHY the transition is
                            // illegal per the protocol, shown in the replay hover
                            // tooltip. Set only when `violation` is true.
  inferred?: boolean        // set by the replay mapper when a single-machine state
                            // diff had to be bridged by MORE THAN ONE legal trigger
                            // (a multi-hop triggerPath). The log records snapshots,
                            // not transitions, so a >1-hop diff means intermediate
                            // states were not logged and the mapper GUESSED the legal
                            // path between them — which could mask an illegal 1-step
                            // jump that happens to be bridgeable by a longer legal
                            // detour. Not a violation; a "this step was inferred, not
                            // observed" tripwire. Renderers may style it distinctly.
  inferredNote?: string     // human-readable explanation of the inferred path, shown
                            // in the hover tooltip. Set only when `inferred` is true.
  unrecognized?: boolean    // set by the replay mapper on the node it draws for an
                            // entry whose semanticType the semantic registry does not
                            // list (a log from another protocol version). Shown as such,
                            // never dropped. Renderers style it distinctly.
  unrecognizedNote?: string // why the node is unrecognized, for the hover tooltip.
                            // Set only when `unrecognized` is true.
}

export interface DemoState {
  phase: string
  participants: Map<string, ParticipantState>
  emState: string  // Case-level embargo state
  pxaState: string  // Case-level PXA state (Public/eXploit/Attacks)
  timelineEvents: TimelineEvent[]
  eventLog: string[]
  nextXPosition: number
  invitedVendors: Set<string>  // Track all invited vendors (e.g., 'vendor-2', 'vendor-3')
  embargoProposerId?: string  // Track who proposed current embargo/revision (e.g., 'reporter', 'vendor-1', 'casemanager')
  caseOwnerId?: string  // Case-level: which participant currently holds CASE_OWNER. Seeded to
                        // 'vendor-1'; moves on an accepted ownership transfer (ownershipActions).
                        // The CASE_OWNER label is DERIVED from this at render, so the badge migrates.
  pendingOwnerOfferTo?: string  // Participant id an ownership offer is currently addressed to
                                // (offer→accept handshake), or undefined when none is pending.
  hasPendingReporterNote?: boolean  // Case-level: an unanswered Reporter question exists. Independent of `phase` so RM transitions (e.g. defer) don't hide the reply option (see actionFilters reply gating)
  stepSnapshots?: StepSnapshot[]  // Log Replay only: machine states as of each visual
                                  // step (index i = state after timeline column i is
                                  // revealed). The side panels index this by the
                                  // playback position so status reflects the current
                                  // step, not the final end-state. See caseLedgerMapper.
  rejectedLines?: RejectedLedgerLine[]  // Log Replay only: ledger lines that failed the
                                        // shape check and were not replayed (parseCaseLedger).
}

/**
 * A snapshot of all machine states at one Log Replay step, so the side panels can
 * show state as-of the current playback position rather than the terminal state.
 * `rm`/`vfd` are keyed by participant lane id (the actor id in Log Replay);
 * `emState`/`pxaState` are case-level.
 */
export interface StepSnapshot {
  rm: Record<string, string>
  vfd: Record<string, string>
  emState: string
  pxaState: string
}

export interface Action {
  id: string
  label: string
  description: string
  enabled: boolean
}
