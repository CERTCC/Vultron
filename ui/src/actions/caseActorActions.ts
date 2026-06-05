/**
 * CaseActor action handlers
 */

import type { DemoState } from '../types'
import {
  addTimelineEvents,
  addEventLogEntries,
  incrementXPosition,
  setPhase,
  setEmState,
  updateParticipant,
} from '../state/stateUpdaters'
import { getParticipant, getActiveVendors } from '../state/participantHelpers'

export function handleProposeEmbargo(state: DemoState): DemoState {
  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  const caseactor = getParticipant(state, 'caseactor')
  const finder = getParticipant(state, 'finder')
  const activeVendors = getActiveVendors(state)

  let newState = state

  newState = setPhase(newState, 'embargo-proposed')
  newState = setEmState(newState, 'PROPOSED')
  newState = updateParticipant(newState, 'finder', { embargoAccepted: false })

  // Reset embargoAccepted for ALL active vendors
  for (const vendor of activeVendors) {
    newState = updateParticipant(newState, vendor.id, { embargoAccepted: false })
  }

  const events = []
  let timestampOffset = 0

  // Decision node in CaseActor's lane
  events.push({
    id: eventId,
    actor: 'CaseActor',
    participantId: 'caseactor',
    label: 'Propose Embargo',
    x: nextX,
    lane: caseactor?.laneIndex ?? 2,
    type: 'decision' as const,
    timestamp: now,
    consequences: [
      'EmbargoEvent created (90-day proposal)',
      'EmProposeEmbargoActivity created',
      'Proposal sent to all participants',
      'EM state → PROPOSED',
      'Awaiting participant decisions',
    ],
  })
  timestampOffset++

  // Consequence node in Finder's lane
  if (finder) {
    events.push({
      id: `${eventId}-finder-consequence`,
      actor: 'Finder',
      participantId: 'finder',
      label: 'Proposal Received',
      x: nextX,
      lane: finder.laneIndex,
      type: 'consequence' as const,
      timestamp: now + timestampOffset,
      causedBy: eventId,
      enablesNext: true,
      consequences: [
        'EmProposeEmbargoActivity received',
        'Finder sees 90-day embargo proposal',
        'EM state → PROPOSED',
        'Must accept or reject',
      ],
    })
    timestampOffset++
  }

  // Consequence nodes for ALL active vendors
  for (const vendor of activeVendors) {
    events.push({
      id: `${eventId}-${vendor.id}-consequence`,
      actor: vendor.name,
      participantId: vendor.id,
      label: 'Proposal Received',
      x: nextX,
      lane: vendor.laneIndex,
      type: 'consequence' as const,
      timestamp: now + timestampOffset,
      causedBy: eventId,
      enablesNext: true,
      consequences: [
        'EmProposeEmbargoActivity received',
        'EmbargoEvent stored in DataLayer',
        `${vendor.name} sees 90-day embargo proposal`,
        'Must accept or reject',
      ],
    })
    timestampOffset++
  }

  newState = addTimelineEvents(newState, events)
  newState = addEventLogEntries(newState, ['CaseActor proposed 90-day embargo'])
  newState = incrementXPosition(newState)

  return newState
}
