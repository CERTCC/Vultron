/**
 * External event action handlers (exploits, attacks)
 */

import type { DemoState } from '../types'
import {
  addTimelineEvents,
  addEventLogEntries,
  incrementXPosition,
  setPxaState,
} from '../state/stateUpdaters'
import { getActiveLanes } from '../state/participantHelpers'

export function handleTriggerExploit(state: DemoState): DemoState {
  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  // Determine new PXA state
  // Per Vultron protocol: exploit publication (X) automatically implies public awareness (P)
  // States pXa and pXA are not valid - once an exploit is published, the public is aware
  const currentPxa = state.pxaState
  let newPxa = currentPxa
  if (currentPxa === 'pxa') {
    newPxa = 'PXa'  // exploit published -> public becomes aware automatically
  } else if (currentPxa === 'Pxa') {
    newPxa = 'PXa'  // public + exploit (already public)
  } else if (currentPxa === 'pxA') {
    newPxa = 'PXA'  // exploit + attacks -> public becomes aware automatically
  } else if (currentPxa === 'PxA') {
    newPxa = 'PXA'  // public + exploit + attacks (already public)
  }

  let newState = state
  newState = setPxaState(newState, newPxa)

  const activeLanes = getActiveLanes(newState)

  // Create consequence nodes for all active participants
  const publicBecameAware = !currentPxa.includes('P') && newPxa.includes('P')
  const events = activeLanes.map((participant, index) => ({
    id: `${eventId}-${participant.id}-consequence`,
    actor: participant.name,
    participantId: participant.id,
    label: 'Exploit Published',
    x: nextX,
    lane: participant.laneIndex,
    type: 'consequence' as const,
    timestamp: now + index,
    consequences: [
      'External event: exploit published',
      ...(publicBecameAware ? ['Public becomes aware (automatic with X)'] : []),
      `${participant.name} observes exploit`,
      'Participant pxa_state updated',
      `Case PXA state: ${currentPxa} → ${newPxa}`,
      'Authoritative ledger updated',
    ],
  }))

  newState = addTimelineEvents(newState, events)
  newState = addEventLogEntries(newState, [
    publicBecameAware
      ? 'Exploit published in the wild (external event) - public becomes aware'
      : 'Exploit published in the wild (external event)'
  ])
  newState = incrementXPosition(newState)

  return newState
}

export function handleTriggerAttacks(state: DemoState): DemoState {
  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  // Determine new PXA state
  const currentPxa = state.pxaState
  let newPxa = currentPxa
  if (currentPxa === 'pxa') {
    newPxa = 'pxA'  // attacks observed
  } else if (currentPxa === 'pXa') {
    newPxa = 'pXA'  // exploit + attacks
  } else if (currentPxa === 'Pxa') {
    newPxa = 'PxA'  // public + attacks
  } else if (currentPxa === 'PXa') {
    newPxa = 'PXA'  // public + exploit + attacks
  }

  let newState = state
  newState = setPxaState(newState, newPxa)

  const activeLanes = getActiveLanes(newState)

  // Create consequence nodes for all active participants
  const events = activeLanes.map((participant, index) => ({
    id: `${eventId}-${participant.id}-consequence`,
    actor: participant.name,
    participantId: participant.id,
    label: 'Attacks Observed',
    x: nextX,
    lane: participant.laneIndex,
    type: 'consequence' as const,
    timestamp: now + index,
    consequences: [
      'External event: attacks observed in the wild',
      `${participant.name} becomes aware`,
      'Participant pxa_state updated',
      `Case PXA state: ${currentPxa} → ${newPxa}`,
      'Authoritative ledger updated',
    ],
  }))

  newState = addTimelineEvents(newState, events)
  newState = addEventLogEntries(newState, ['Attacks observed in the wild (external event)'])
  newState = incrementXPosition(newState)

  return newState
}
