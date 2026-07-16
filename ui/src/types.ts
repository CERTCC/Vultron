/**
 * Type definitions for the Vultron multi-vendor demo
 */

export interface ParticipantState {
  id: string
  name: string
  role: string
  color: string
  rmState: string
  vfdState: string
  embargoAccepted: boolean
  embargoProposedToParticipant?: boolean  // Track if embargo was proposed to this participant (for late joiners)
  hasPublished: boolean
  hasClosed: boolean
  visible: boolean
  laneIndex: number
  hasRepliedToCurrentNote?: boolean  // Track if participant replied to current note
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
  embargoProposerId?: string  // Track who proposed current embargo/revision (e.g., 'finder', 'vendor-1', 'caseactor')
  hasPendingFinderNote?: boolean  // Case-level: an unanswered Finder question exists. Independent of `phase` so RM transitions (e.g. defer) don't hide the reply option (see actionFilters reply gating)
}

export interface Action {
  id: string
  label: string
  description: string
  enabled: boolean
}
