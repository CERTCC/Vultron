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
  if (finder && !finder.hasClosed) {
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

export function handleCaseActorProposeRevision(state: DemoState): DemoState {
  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  const caseactor = getParticipant(state, 'caseactor')
  const finder = getParticipant(state, 'finder')
  const activeVendors = getActiveVendors(state)

  let newState = state

  // Per Vultron protocol: A → pR (Active → propose → Revise)
  // The existing embargo remains active until revision is accepted
  newState = setEmState(newState, 'REVISE')

  const events = []
  let timestampOffset = 0

  // Decision node in CaseActor's lane
  events.push({
    id: eventId,
    actor: 'CaseActor',
    participantId: 'caseactor',
    label: 'Propose Embargo Revision',
    x: nextX,
    lane: caseactor?.laneIndex ?? 2,
    type: 'decision' as const,
    timestamp: now,
    consequences: [
      'Embargo revision proposed',
      'EmProposeEmbargoActivity created (revision)',
      'Existing embargo remains active',
      'EM state → REVISE',
      'Awaiting participant responses',
    ],
  })
  timestampOffset++

  // Consequence node in Finder's lane (only if not closed)
  if (finder && finder.embargoAccepted && !finder.hasClosed) {
    events.push({
      id: `${eventId}-finder-consequence`,
      actor: 'Finder',
      participantId: 'finder',
      label: 'Revision Proposal Received',
      x: nextX,
      lane: finder.laneIndex,
      type: 'consequence' as const,
      timestamp: now + timestampOffset,
      causedBy: eventId,
      enablesNext: true,
      consequences: [
        'EmProposeEmbargoActivity received (revision)',
        'Finder sees proposed revision',
        'Current embargo still active',
        'Can accept or reject revision',
      ],
    })
    timestampOffset++
  }

  // Consequence nodes for ALL active vendors who accepted the embargo
  for (const vendor of activeVendors) {
    if (vendor.embargoAccepted) {
      events.push({
        id: `${eventId}-${vendor.id}-consequence`,
        actor: vendor.name,
        participantId: vendor.id,
        label: 'Revision Proposal Received',
        x: nextX,
        lane: vendor.laneIndex,
        type: 'consequence' as const,
        timestamp: now + timestampOffset,
        causedBy: eventId,
        enablesNext: true,
        consequences: [
          'EmProposeEmbargoActivity received (revision)',
          `${vendor.name} sees proposed revision`,
          'Current embargo still active',
          'Can accept or reject revision',
        ],
      })
      timestampOffset++
    }
  }

  newState = addTimelineEvents(newState, events)
  newState = addEventLogEntries(newState, ['CaseActor proposed embargo revision'])
  newState = incrementXPosition(newState)

  return newState
}

export function handleCaseActorAcceptRevision(state: DemoState): DemoState {
  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  const caseactor = getParticipant(state, 'caseactor')

  let newState = state

  // Per Vultron protocol: R → aA (Revise → accept → Active)
  // Revision is accepted, new terms become active
  newState = setEmState(newState, 'ACTIVE')

  const events = [{
    id: eventId,
    actor: 'CaseActor',
    participantId: 'caseactor',
    label: 'Accept Revision',
    x: nextX,
    lane: caseactor?.laneIndex ?? 2,
    type: 'decision' as const,
    timestamp: now,
    consequences: [
      'CaseActor accepted embargo revision',
      'EmAcceptEmbargoActivity created',
      'Revised embargo terms now active',
      'EM state → ACTIVE',
    ],
  }]

  newState = addTimelineEvents(newState, events)
  newState = addEventLogEntries(newState, ['CaseActor accepted embargo revision'])
  newState = incrementXPosition(newState)

  return newState
}

export function handleCaseActorRejectRevision(state: DemoState): DemoState {
  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  const caseactor = getParticipant(state, 'caseactor')

  let newState = state

  // Per Vultron protocol: R → rA (Revise → reject → Active)
  // Revision is rejected, original embargo terms remain active
  newState = setEmState(newState, 'ACTIVE')

  const events = [{
    id: eventId,
    actor: 'CaseActor',
    participantId: 'caseactor',
    label: 'Reject Revision',
    x: nextX,
    lane: caseactor?.laneIndex ?? 2,
    type: 'decision' as const,
    timestamp: now,
    consequences: [
      'CaseActor rejected embargo revision',
      'EmRejectEmbargoActivity created',
      'Original embargo terms remain active',
      'EM state → ACTIVE',
    ],
  }]

  newState = addTimelineEvents(newState, events)
  newState = addEventLogEntries(newState, ['CaseActor rejected embargo revision - original terms remain'])
  newState = incrementXPosition(newState)

  return newState
}
