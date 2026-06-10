/**
 * Helper functions for working with participants
 */

import type { DemoState, ParticipantState } from '../types'

export function getParticipant(state: DemoState, id: string): ParticipantState | undefined {
  return state.participants.get(id)
}

export function getVendors(state: DemoState): ParticipantState[] {
  return Array.from(state.participants.values()).filter(p => p.id.startsWith('vendor-'))
}

export function getActiveVendors(state: DemoState): ParticipantState[] {
  // Per Vultron protocol (working_with_others.md lines 112-115):
  // Vendors who rejected an existing embargo cannot participate in the case
  // However, if the embargo is terminated (EXITED), they can participate again
  const hasActiveEmbargo = state.emState === 'ACTIVE' || state.emState === 'REVISE'

  return getVendors(state).filter(v => {
    // Basic active check
    if (!v.visible || v.hasClosed) return false

    // If there's an active embargo and vendor rejected it, exclude them
    if (hasActiveEmbargo && !v.embargoAccepted && !v.embargoProposedToParticipant) {
      return false
    }

    return true
  })
}

export function getActiveLanes(state: DemoState): ParticipantState[] {
  return Array.from(state.participants.values())
    .filter(p => p.visible)
    .sort((a, b) => a.laneIndex - b.laneIndex)
}

export function getActiveParticipants(state: DemoState): ParticipantState[] {
  // Returns participants who are still active in the case (not closed)
  // Use this for creating consequence nodes - closed participants shouldn't receive them
  // Per Vultron protocol (working_with_others.md lines 112-115):
  // Vendors who rejected an existing embargo cannot participate in the case
  const hasActiveEmbargo = state.emState === 'ACTIVE' || state.emState === 'REVISE'

  return Array.from(state.participants.values())
    .filter(p => {
      // Basic active check
      if (!p.visible || p.hasClosed) return false

      // Special case for vendors: if there's an active embargo and vendor rejected it, exclude them
      if (p.id.startsWith('vendor-')) {
        if (hasActiveEmbargo && !p.embargoAccepted && !p.embargoProposedToParticipant) {
          return false
        }
      }

      return true
    })
    .sort((a, b) => a.laneIndex - b.laneIndex)
}

export function getVendorByIndex(state: DemoState, index: number): ParticipantState | undefined {
  return state.participants.get(`vendor-${index}`)
}

export function getFinder(state: DemoState): ParticipantState | undefined {
  return state.participants.get('finder')
}

export function getCaseActor(state: DemoState): ParticipantState | undefined {
  return state.participants.get('caseactor')
}

export function getTotalLaneCount(state: DemoState): number {
  return getActiveLanes(state).length
}

export function hasSecondVendor(state: DemoState): boolean {
  const vendor2 = getVendorByIndex(state, 2)
  return vendor2 !== undefined && vendor2.visible
}

export function getVendorCount(state: DemoState): number {
  return getVendors(state).length
}

export function getNextVendorNumber(state: DemoState): number {
  return getVendorCount(state) + 1
}

export function canInviteMoreVendors(state: DemoState): boolean {
  // No artificial limit - vendors can be added indefinitely
  // Practical limits may be imposed by UI/performance considerations
  return true
}
