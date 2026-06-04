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

export function addTimelineEvent(state: DemoState, event: TimelineEvent): DemoState {
  return {
    ...state,
    timelineEvents: [...state.timelineEvents, event],
  }
}

export function addTimelineEvents(state: DemoState, events: TimelineEvent[]): DemoState {
  return {
    ...state,
    timelineEvents: [...state.timelineEvents, ...events],
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
