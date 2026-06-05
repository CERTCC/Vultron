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
  return getVendors(state).filter(v => v.visible && !v.hasClosed)
}

export function getActiveLanes(state: DemoState): ParticipantState[] {
  return Array.from(state.participants.values())
    .filter(p => p.visible)
    .sort((a, b) => a.laneIndex - b.laneIndex)
}

export function getActiveParticipants(state: DemoState): ParticipantState[] {
  // Returns participants who are still active in the case (not closed)
  // Use this for creating consequence nodes - closed participants shouldn't receive them
  return Array.from(state.participants.values())
    .filter(p => p.visible && !p.hasClosed)
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
