/**
 * Helper functions for updating state immutably
 */

import type { DemoState, ParticipantState, TimelineEvent } from '../types'
import { X_INCREMENT } from '../constants'

export function updateParticipant(
  state: DemoState,
  id: string,
  updates: Partial<ParticipantState>
): DemoState {
  const participant = state.participants.get(id)
  if (!participant) {
    console.warn(`Participant ${id} not found`)
    return state
  }

  const newParticipants = new Map(state.participants)
  newParticipants.set(id, { ...participant, ...updates })

  return {
    ...state,
    participants: newParticipants,
  }
}

export function updateMultipleParticipants(
  state: DemoState,
  updates: Array<{ id: string; updates: Partial<ParticipantState> }>
): DemoState {
  let newState = state
  for (const { id, updates: participantUpdates } of updates) {
    newState = updateParticipant(newState, id, participantUpdates)
  }
  return newState
}

/**
 * Drop CONSEQUENCE nodes aimed at a participant who has already closed: a closed
 * participant receives no further notifications, so it should not sprout new
 * consequence nodes (e.g. a Finder who closed before an embargo was accepted must
 * not show a "Vendor Accepted Embargo" node). Applied centrally here rather than in
 * each handler — many handlers hardcode an "always create the Finder consequence"
 * node, and this is the single choke point they all commit through.
 *
 * Only consequence nodes are filtered. Decision nodes are never dropped — they
 * represent the acting participant's own action (a closed participant can't act, so
 * this never suppresses a legitimate decision), and dropping one would lose the
 * event entirely.
 */
function keepEventForOpenTarget(state: DemoState, event: TimelineEvent): boolean {
  if (event.type !== 'consequence') return true
  const target = event.participantId ? state.participants.get(event.participantId) : undefined
  return !(target && target.hasClosed)
}

export function addTimelineEvent(state: DemoState, event: TimelineEvent): DemoState {
  if (!keepEventForOpenTarget(state, event)) return state
  return {
    ...state,
    timelineEvents: [...state.timelineEvents, event],
  }
}

export function addTimelineEvents(state: DemoState, events: TimelineEvent[]): DemoState {
  const kept = events.filter((e) => keepEventForOpenTarget(state, e))
  return {
    ...state,
    timelineEvents: [...state.timelineEvents, ...kept],
  }
}

export function addEventLogEntry(state: DemoState, message: string): DemoState {
  return {
    ...state,
    eventLog: [...state.eventLog, message],
  }
}

export function addEventLogEntries(state: DemoState, messages: string[]): DemoState {
  return {
    ...state,
    eventLog: [...state.eventLog, ...messages],
  }
}

export function incrementXPosition(state: DemoState): DemoState {
  return {
    ...state,
    nextXPosition: state.nextXPosition + X_INCREMENT,
  }
}

export function setPhase(state: DemoState, phase: string): DemoState {
  return {
    ...state,
    phase,
  }
}

export function setPxaState(state: DemoState, pxaState: string): DemoState {
  return {
    ...state,
    pxaState,
  }
}

export function setEmState(state: DemoState, emState: string): DemoState {
  return {
    ...state,
    emState,
  }
}
