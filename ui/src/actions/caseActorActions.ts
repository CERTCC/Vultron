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

export function handleProposeEmbargo(state: DemoState): DemoState {
  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  let newState = state

  newState = setPhase(newState, 'embargo-proposed')
  newState = setEmState(newState, 'PROPOSED')
  newState = updateParticipant(newState, 'finder', { embargoAccepted: false })
  newState = updateParticipant(newState, 'vendor-1', { embargoAccepted: false })

  newState = addTimelineEvents(newState, [
    {
      id: eventId,
      actor: 'CaseActor',
      participantId: 'caseactor',
      label: 'Propose Embargo',
      x: nextX,
      lane: 2,
      type: 'decision',
      timestamp: now,
      consequences: [
        'EmbargoEvent created (90-day proposal)',
        'EmProposeEmbargoActivity created',
        'Proposal sent to Vendor inbox',
        'EM state → PROPOSED',
        'Awaiting Vendor decision',
      ],
    },
    {
      id: `${eventId}-vendor-consequence`,
      actor: 'Vendor',
      participantId: 'vendor-1',
      label: 'Proposal Received',
      x: nextX,
      lane: 1,
      type: 'consequence',
      timestamp: now + 1,
      causedBy: eventId,
      enablesNext: true,
      consequences: [
        'EmProposeEmbargoActivity received',
        'EmbargoEvent stored in DataLayer',
        'Vendor sees 90-day embargo proposal',
        'Must accept or reject',
      ],
    },
    {
      id: `${eventId}-finder-consequence`,
      actor: 'Finder',
      participantId: 'finder',
      label: 'Proposal Received',
      x: nextX,
      lane: 0,
      type: 'consequence',
      timestamp: now + 2,
      causedBy: eventId,
      enablesNext: true,
      consequences: [
        'EmProposeEmbargoActivity received',
        'Finder sees 90-day embargo proposal',
        'EM state → PROPOSED',
        'Must accept or reject',
      ],
    },
  ])

  newState = addEventLogEntries(newState, ['CaseActor proposed 90-day embargo'])
  newState = incrementXPosition(newState)

  return newState
}
