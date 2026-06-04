/**
 * Finder action handlers
 */

import type { DemoState } from '../types'
import {
  updateParticipant,
  addTimelineEvents,
  addEventLogEntries,
  incrementXPosition,
  setPhase,
  setPxaState,
} from '../state/stateUpdaters'
import { getParticipant } from '../state/participantHelpers'

export function handleSubmitReport(state: DemoState): DemoState {
  const nextX = state.nextXPosition
  const submitEventId = 'event-1'
  const now = Date.now()

  let newState = state

  // Update participants
  newState = updateParticipant(newState, 'finder', { rmState: 'RECEIVED' })
  newState = updateParticipant(newState, 'vendor-1', { rmState: 'RECEIVED', vfdState: 'Vfd', visible: true })
  newState = updateParticipant(newState, 'caseactor', { visible: true })

  // Update phase
  newState = setPhase(newState, 'report-received')

  // Add timeline events
  newState = addTimelineEvents(newState, [
    {
      id: submitEventId,
      actor: 'Finder',
      participantId: 'finder',
      label: 'Submit Report',
      x: nextX,
      lane: 0,
      type: 'decision',
      timestamp: now,
      consequences: [
        'VulnerabilityReport object created',
        'Offer(VulnerabilityReport) activity created',
        'Offer sent to Vendor\'s inbox',
        'Triggers automatic case creation',
      ],
    },
    {
      id: `${submitEventId}-vendor-consequence`,
      actor: 'Vendor',
      participantId: 'vendor-1',
      label: 'Report Received',
      x: nextX,
      lane: 1,
      type: 'consequence',
      causedBy: submitEventId,
      enablesNext: true,
      timestamp: now + 1,
      consequences: [
        'Offer received in inbox',
        'SubmitReportReceived handler triggered',
        'VulnerabilityReport stored in DataLayer',
        'Vendor\'s RM state → RECEIVED',
        'Case creation BT executes automatically',
      ],
    },
    {
      id: `${submitEventId}-case-consequence`,
      actor: 'CaseActor',
      participantId: 'caseactor',
      label: 'Case Created',
      x: nextX,
      lane: 2,
      type: 'consequence',
      causedBy: submitEventId,
      timestamp: now + 2,
      consequences: [
        'VulnerabilityCase created automatically',
        'Case creation BT: create_receive_report_case_tree',
        'Vendor participant created (attributed_to: Vendor)',
        'Vendor\'s RM → RECEIVED, VFD → Vfd',
        'Case Actor acts as authoritative ledger',
      ],
    },
    {
      id: `${submitEventId}-finder-case-consequence`,
      actor: 'Finder',
      participantId: 'finder',
      label: 'Case Announced',
      x: nextX,
      lane: 0,
      type: 'decision',
      causedBy: submitEventId,
      timestamp: now + 3,
      consequences: [
        'Announce(Case) received in inbox',
        'Case replica created in DataLayer',
        'Finder participant record created',
        'Finder\'s RM → RECEIVED',
        'Trust established with CaseActor',
      ],
    },
  ])

  // Add event log
  newState = addEventLogEntries(newState, [
    'Finder submitted report to Vendor',
    'Case created automatically (at RM.RECEIVED)',
  ])

  // Increment X position
  newState = incrementXPosition(newState)

  return newState
}

export function handleFinderAcceptEmbargo(state: DemoState): DemoState {
  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  const vendor1 = getParticipant(state, 'vendor-1')
  const bothAccepted = vendor1?.embargoAccepted

  let newState = state

  // Update finder to show accepted
  newState = updateParticipant(newState, 'finder', { embargoAccepted: true })

  // If both accepted, activate embargo
  if (bothAccepted) {
    newState = { ...newState, emState: 'ACTIVE', phase: 'embargo-accepted' }
  }

  // Add timeline events
  const events = [
    {
      id: eventId,
      actor: 'Finder',
      participantId: 'finder',
      label: 'Accept Embargo',
      x: nextX,
      lane: 0,
      type: 'decision' as const,
      timestamp: now,
      consequences: [
        'EmAcceptEmbargoActivity created',
        'Finder accepts 90-day embargo',
        bothAccepted ? 'Both parties accepted - embargo is now ACTIVE' : 'Awaiting Vendor acceptance',
      ],
    },
  ]

  if (bothAccepted) {
    events.push({
      id: `${eventId}-case-consequence`,
      actor: 'CaseActor',
      participantId: 'caseactor',
      label: 'M1 REACHED',
      x: nextX,
      lane: 2,
      type: 'consequence',
      causedBy: eventId,
      timestamp: now + 1,
      enablesNext: true,
      consequences: [
        '✓ M1 REACHED: Case active',
        'Embargo: ACTIVE',
        '3 participants engaged',
        'Coordinated disclosure timeline begins',
      ],
    })
  }

  newState = addTimelineEvents(newState, events)

  newState = addEventLogEntries(newState, [
    `Finder accepted embargo${bothAccepted ? ' (awaiting Vendor)' : ''}`,
    ...(bothAccepted ? ['✓ M1 REACHED: Case active with 3 participants, embargo active'] : []),
  ])

  newState = incrementXPosition(newState)

  return newState
}

export function handleFinderRejectEmbargo(state: DemoState): DemoState {
  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  let newState = state

  newState = { ...newState, emState: 'NONE', phase: 'embargo-rejected' }

  newState = addTimelineEvents(newState, [
    {
      id: eventId,
      actor: 'Finder',
      participantId: 'finder',
      label: 'Reject Embargo',
      x: nextX,
      lane: 0,
      type: 'decision',
      timestamp: now,
      consequences: [
        'EmRejectEmbargoActivity created',
        'Finder rejects embargo proposal',
        'Case proceeds without embargo',
      ],
    },
  ])

  newState = addEventLogEntries(newState, ['Finder rejected embargo'])
  newState = incrementXPosition(newState)

  return newState
}

export function handleFinderAddNote(state: DemoState): DemoState {
  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  let newState = state

  newState = setPhase(newState, 'finder-asked')

  newState = addTimelineEvents(newState, [
    {
      id: eventId,
      actor: 'Finder',
      participantId: 'finder',
      label: 'Ask Question',
      x: nextX,
      lane: 0,
      type: 'decision',
      timestamp: now,
      consequences: [
        'Note added to case',
        'Question asked to Vendor',
        'E.g., "Are there workarounds available?"',
      ],
    },
  ])

  newState = addEventLogEntries(newState, ['Finder asked question'])
  newState = incrementXPosition(newState)

  return newState
}

export function handleFinderNotifyPublished(state: DemoState): DemoState {
  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  let newState = state

  newState = updateParticipant(newState, 'finder', { hasPublished: true })
  newState = setPhase(newState, 'finder-published')

  // Update PXA state to P if not already
  if (state.pxaState === 'pxa') {
    newState = setPxaState(newState, 'Pxa')
  }

  newState = addTimelineEvents(newState, [
    {
      id: eventId,
      actor: 'Finder',
      participantId: 'finder',
      label: 'Acknowledge Publication',
      x: nextX,
      lane: 0,
      type: 'decision',
      timestamp: now,
      consequences: [
        'Finder acknowledges publication',
        'PXA: public awareness confirmed',
      ],
    },
  ])

  newState = addEventLogEntries(newState, ['Finder acknowledged publication'])
  newState = incrementXPosition(newState)

  return newState
}

export function handleFinderCloseCase(state: DemoState): DemoState {
  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  let newState = state

  newState = updateParticipant(newState, 'finder', { rmState: 'CLOSED', hasClosed: true })
  newState = setPhase(newState, 'finder-closed')

  newState = addTimelineEvents(newState, [
    {
      id: eventId,
      actor: 'Finder',
      participantId: 'finder',
      label: 'Close Case',
      x: nextX,
      lane: 0,
      type: 'decision',
      timestamp: now,
      consequences: [
        'Finder RM state: → CLOSED',
        'Finder leaves the case (ActivityPub: Leave)',
        'No further actions available for Finder',
        'Vendor can still continue case work',
      ],
    },
  ])

  newState = addEventLogEntries(newState, ['Finder closed their participation in the case'])
  newState = incrementXPosition(newState)

  return newState
}
