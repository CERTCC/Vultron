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
import { getParticipant } from '../state/participantHelpers'

export function handleProposeEmbargo(state: DemoState): DemoState {
  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  const caseactor = getParticipant(state, 'caseactor')
  const vendor1 = getParticipant(state, 'vendor-1')
  const finder = getParticipant(state, 'finder')

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
      lane: caseactor?.laneIndex ?? 2,
      type: 'decision' as const,
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
      lane: vendor1?.laneIndex ?? 1,
      type: 'consequence' as const,
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
      lane: finder?.laneIndex ?? 0,
      type: 'consequence' as const,
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
