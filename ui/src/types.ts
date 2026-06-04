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
  hasPublished: boolean
  hasClosed: boolean
  visible: boolean
  laneIndex: number
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
}

export interface DemoState {
  phase: string
  participants: Map<string, ParticipantState>
  emState: string  // Case-level embargo state
  pxaState: string  // Case-level PXA state (Public/eXploit/Attacks)
  timelineEvents: TimelineEvent[]
  eventLog: string[]
  nextXPosition: number
  secondVendorInvited: boolean
  secondVendorAccepted: boolean
}

export interface Action {
  id: string
  label: string
  description: string
  enabled: boolean
}
