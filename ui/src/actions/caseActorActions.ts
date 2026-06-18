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
import { getParticipant, getActiveVendors, getVendors } from '../state/participantHelpers'

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
  newState = { ...newState, embargoProposerId: 'caseactor' }  // Track who proposed
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

  let newState = state

  // Per Vultron protocol: A → pR (Active → propose → Revise)
  // The existing embargo remains active until revision is accepted
  newState = setEmState(newState, 'REVISE')
  newState = { ...newState, embargoProposerId: 'caseactor' }  // Track who proposed this revision

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
  if (finder && !finder.hasClosed) {
    // Reset Finder's embargoAccepted - they need to accept the revision
    newState = updateParticipant(newState, 'finder', {
      embargoAccepted: false
    })

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

  // Consequence nodes for ALL vendors (including those who previously rejected)
  // Per Vultron protocol: embargo revision is a new proposal that ALL participants can accept/reject
  // This gives vendors who rejected the original embargo a chance to participate in the revised terms
  for (const vendor of getVendors(newState).filter((v) => v.visible && !v.hasClosed)) {
    const wasParticipating = vendor.embargoAccepted

    // Reset embargoAccepted for ALL vendors - they need to accept the revision
    // Only set embargoProposedToParticipant for vendors who were NOT participating (gives them a new chance)
    // Vendors who WERE participating should see revision actions + normal actions
    newState = updateParticipant(newState, vendor.id, {
      embargoAccepted: false,
      embargoProposedToParticipant: !wasParticipating  // Only true for previously-excluded vendors
    })

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
  const finder = getParticipant(state, 'finder')

  let newState = state

  // Per Vultron protocol: R → aA (Revise → accept → Active)
  // But ONLY if ALL embargo participants (Finder + Vendors) have accepted
  // CaseActor's acceptance doesn't count toward consensus (they facilitate, don't vote)
  const allParticipantsAccepted = (finder?.embargoAccepted || false) &&
    getActiveVendors(newState).every((v) => v.embargoAccepted)

  if (allParticipantsAccepted) {
    newState = setEmState(newState, 'ACTIVE')
    newState = { ...newState, embargoProposerId: undefined }  // Clear proposer when revision is accepted
  }
  // Otherwise, stay in REVISE state

  const events = []
  let timestampOffset = 0

  // Decision node in CaseActor's lane
  events.push({
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
      allParticipantsAccepted ? 'Revised embargo terms now active' : 'Awaiting all participants to accept',
      allParticipantsAccepted ? 'EM state → ACTIVE' : 'EM state remains REVISE',
    ],
  })
  timestampOffset++

  // Consequence node in Finder's lane
  if (finder && !finder.hasClosed) {
    events.push({
      id: `${eventId}-finder-consequence`,
      actor: 'Finder',
      participantId: 'finder',
      label: allParticipantsAccepted ? 'Revision Accepted' : 'CaseActor Accepted',
      x: nextX,
      lane: finder.laneIndex,
      type: 'consequence' as const,
      timestamp: now + timestampOffset,
      causedBy: eventId,
      enablesNext: true,
      consequences: [
        'CaseActor accepted revision',
        allParticipantsAccepted ? 'All participants accepted - EM → ACTIVE' : 'Awaiting other participants',
      ],
    })
    timestampOffset++
  }

  // Consequence nodes for all vendors
  const vendors = getVendors(newState).filter((v) => v.visible && !v.hasClosed)
  for (const vendor of vendors) {
    events.push({
      id: `${eventId}-${vendor.id}-consequence`,
      actor: vendor.name,
      participantId: vendor.id,
      label: allParticipantsAccepted ? 'Revision Accepted' : 'CaseActor Accepted',
      x: nextX,
      lane: vendor.laneIndex,
      type: 'consequence' as const,
      timestamp: now + timestampOffset,
      causedBy: eventId,
      enablesNext: true,
      consequences: [
        'CaseActor accepted revision',
        allParticipantsAccepted ? 'All participants accepted - EM → ACTIVE' : 'Awaiting other participants',
      ],
    })
    timestampOffset++
  }

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
  const finder = getParticipant(state, 'finder')

  let newState = state

  // Per Vultron protocol: R → rA (Revise → reject → Active)
  // Revision is rejected, original embargo terms remain active
  newState = setEmState(newState, 'ACTIVE')
  newState = { ...newState, embargoProposerId: undefined }  // Clear proposer when revision is rejected

  // Restore embargoAccepted for Finder (was participating)
  if (finder) {
    newState = updateParticipant(newState, 'finder', {
      embargoAccepted: true
    })
  }

  // Restore embargoAccepted for vendors who were participating
  // Clear embargoProposedToParticipant for vendors who were excluded (revision opportunity passed)
  for (const vendor of getVendors(newState).filter((v) => v.visible && !v.hasClosed)) {
    if (vendor.embargoProposedToParticipant) {
      // Was excluded, offered revision, rejected/didn't accept - clear the flag
      newState = updateParticipant(newState, vendor.id, {
        embargoProposedToParticipant: false
      })
    } else {
      // Was participating - restore embargoAccepted
      newState = updateParticipant(newState, vendor.id, {
        embargoAccepted: true
      })
    }
  }

  const events = []
  let timestampOffset = 0

  // Decision node in CaseActor's lane
  events.push({
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
  })
  timestampOffset++

  // Consequence node in Finder's lane
  if (finder && !finder.hasClosed) {
    events.push({
      id: `${eventId}-finder-consequence`,
      actor: 'Finder',
      participantId: 'finder',
      label: 'Revision Rejected',
      x: nextX,
      lane: finder.laneIndex,
      type: 'consequence' as const,
      timestamp: now + timestampOffset,
      causedBy: eventId,
      enablesNext: true,
      consequences: [
        'CaseActor rejected revision',
        'Original embargo terms remain',
      ],
    })
    timestampOffset++
  }

  // Consequence nodes for all vendors
  const vendors = getVendors(newState).filter((v) => v.visible && !v.hasClosed)
  for (const vendor of vendors) {
    events.push({
      id: `${eventId}-${vendor.id}-consequence`,
      actor: vendor.name,
      participantId: vendor.id,
      label: 'Revision Rejected',
      x: nextX,
      lane: vendor.laneIndex,
      type: 'consequence' as const,
      timestamp: now + timestampOffset,
      causedBy: eventId,
      enablesNext: true,
      consequences: [
        'CaseActor rejected revision',
        'Original embargo terms remain',
      ],
    })
    timestampOffset++
  }

  newState = addTimelineEvents(newState, events)
  newState = addEventLogEntries(newState, ['CaseActor rejected embargo revision - original terms remain'])
  newState = incrementXPosition(newState)

  return newState
}
