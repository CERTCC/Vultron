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

  // Get participants for lane indices
  const finder = getParticipant(newState, 'finder')
  const vendor1 = getParticipant(newState, 'vendor-1')
  const caseactor = getParticipant(newState, 'caseactor')

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
      lane: finder?.laneIndex ?? 0,
      type: 'decision' as const,
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
      lane: vendor1?.laneIndex ?? 1,
      type: 'consequence' as const,
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
      lane: caseactor?.laneIndex ?? 2,
      type: 'consequence' as const,
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
      lane: finder?.laneIndex ?? 0,
      type: 'decision' as const,
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

  const finder = getParticipant(state, 'finder')
  const vendor1 = getParticipant(state, 'vendor-1')
  const vendor2 = getParticipant(state, 'vendor-2')
  const caseactor = getParticipant(state, 'caseactor')

  // Check if ALL active vendors have accepted
  const activeVendors = [vendor1, vendor2].filter((v): v is NonNullable<typeof v> => v !== null && v !== undefined && v.visible && !v.hasClosed)
  const allVendorsAccepted = activeVendors.length > 0 && activeVendors.every(v => v.embargoAccepted)
  const bothAccepted = allVendorsAccepted

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
      lane: finder?.laneIndex ?? 0,
      type: 'decision' as const,
      timestamp: now,
      consequences: [
        'EmAcceptEmbargoActivity created',
        'Finder accepts 90-day embargo',
        bothAccepted ? 'All parties accepted - embargo is now ACTIVE' : 'Awaiting Vendor acceptance',
      ],
    },
    // Consequence node in CaseActor lane - always created
    {
      id: `${eventId}-caseactor-consequence`,
      actor: 'CaseActor',
      participantId: 'caseactor',
      label: bothAccepted ? 'M1 REACHED' : 'Finder Accepted',
      x: nextX,
      lane: caseactor?.laneIndex ?? 2,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + 1,
      enablesNext: bothAccepted,
      consequences: bothAccepted ? [
        '✓ M1 REACHED: Case active',
        'Embargo: ACTIVE',
        'EmAcceptEmbargoActivity received from all',
        'ActivateEmbargoActivity processed',
        'Authoritative ledger updated',
      ] : [
        'Finder EmAcceptEmbargoActivity received',
        'Awaiting Vendor acceptance',
        'EM state remains PROPOSED',
      ],
    },
  ]

  // Add consequence nodes to all active vendors' lanes
  let timestampOffset = 2
  if (vendor1 && vendor1.visible && !vendor1.hasClosed) {
    events.push({
      id: `${eventId}-vendor1-consequence`,
      actor: 'Vendor',
      participantId: 'vendor-1',
      label: bothAccepted ? 'Embargo Active' : 'Finder Accepted',
      x: nextX,
      lane: vendor1.laneIndex,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + timestampOffset,
      enablesNext: bothAccepted,
      consequences: bothAccepted ? [
        'AnnounceEmbargoActivity received',
        'EM state → ACTIVE',
        '90-day embargo now in effect',
        '✓ M1 REACHED: Case active, embargo established',
      ] : [
        'Finder has accepted embargo',
        'Vendor must still accept or reject',
        'EM state remains PROPOSED',
      ],
    })
    timestampOffset++
  }

  if (vendor2 && vendor2.visible && !vendor2.hasClosed) {
    events.push({
      id: `${eventId}-vendor2-consequence`,
      actor: 'Vendor 2',
      participantId: 'vendor-2',
      label: bothAccepted ? 'Embargo Active' : 'Finder Accepted',
      x: nextX,
      lane: vendor2.laneIndex,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + timestampOffset,
      enablesNext: bothAccepted,
      consequences: bothAccepted ? [
        'AnnounceEmbargoActivity received',
        'EM state → ACTIVE',
        '90-day embargo now in effect',
        '✓ M1 REACHED: Case active, embargo established',
      ] : [
        'Finder has accepted embargo',
        'Vendor must still accept or reject',
        'EM state remains PROPOSED',
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

  const finder = getParticipant(state, 'finder')
  const vendor1 = getParticipant(state, 'vendor-1')
  const vendor2 = getParticipant(state, 'vendor-2')
  const caseactor = getParticipant(state, 'caseactor')

  let newState = state

  newState = { ...newState, emState: 'NONE', phase: 'embargo-rejected' }

  const events = []
  let timestampOffset = 0

  // Decision node in Finder's lane
  events.push({
    id: eventId,
    actor: 'Finder',
    participantId: 'finder',
    label: 'Reject Embargo',
    x: nextX,
    lane: finder?.laneIndex ?? 0,
    type: 'decision' as const,
    timestamp: now,
    consequences: [
      'EmRejectEmbargoActivity created',
      'Finder rejects embargo proposal',
      'Case proceeds without embargo',
      'EM state → NONE',
    ],
  })

  timestampOffset++

  // Consequence node in CaseActor lane
  if (caseactor) {
    events.push({
      id: `${eventId}-caseactor-consequence`,
      actor: 'CaseActor',
      participantId: 'caseactor',
      label: 'Embargo Rejected',
      x: nextX,
      lane: caseactor.laneIndex,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + timestampOffset,
      enablesNext: true,
      consequences: [
        'EmRejectEmbargoActivity received',
        'Embargo proposal discarded',
        'EM state → NONE',
        'Can repropose with revised terms',
      ],
    })
    timestampOffset++
  }

  // Consequence nodes in all vendor lanes
  if (vendor1 && vendor1.visible && !vendor1.hasClosed) {
    events.push({
      id: `${eventId}-vendor1-consequence`,
      actor: 'Vendor',
      participantId: 'vendor-1',
      label: 'Embargo Rejected',
      x: nextX,
      lane: vendor1.laneIndex,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + timestampOffset,
      consequences: [
        'Finder rejected embargo',
        'EM state → NONE',
        'Awaiting reproposal or continuation',
      ],
    })
    timestampOffset++
  }

  if (vendor2 && vendor2.visible && !vendor2.hasClosed) {
    events.push({
      id: `${eventId}-vendor2-consequence`,
      actor: 'Vendor 2',
      participantId: 'vendor-2',
      label: 'Embargo Rejected',
      x: nextX,
      lane: vendor2.laneIndex,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + timestampOffset,
      consequences: [
        'Finder rejected embargo',
        'EM state → NONE',
        'Awaiting reproposal or continuation',
      ],
    })
  }

  newState = addTimelineEvents(newState, events)

  newState = addEventLogEntries(newState, ['Finder rejected embargo proposal'])
  newState = incrementXPosition(newState)

  return newState
}

export function handleFinderAddNote(state: DemoState): DemoState {
  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  let newState = state

  newState = setPhase(newState, 'finder-asked')

  // Reset hasRepliedToCurrentNote for all vendors when a new question is asked
  // Per Vultron protocol: each vendor can independently reply to notes
  const updatedParticipants = new Map(newState.participants)
  for (const [id, participant] of updatedParticipants.entries()) {
    if (id.startsWith('vendor-')) {
      updatedParticipants.set(id, { ...participant, hasRepliedToCurrentNote: false })
    }
  }
  newState = { ...newState, participants: updatedParticipants }

  // Get participants for lane indices
  const finder = getParticipant(newState, 'finder')
  const vendor1 = getParticipant(newState, 'vendor-1')
  const vendor2 = getParticipant(newState, 'vendor-2')
  const caseactor = getParticipant(newState, 'caseactor')

  const events = []
  let timestampOffset = 0

  // Decision node in Finder's lane
  events.push({
    id: eventId,
    actor: 'Finder',
    participantId: 'finder',
    label: 'Ask Question',
    x: nextX,
    lane: finder?.laneIndex ?? 0,
    type: 'decision' as const,
    timestamp: now,
    consequences: [
      'Note created: "Question from Finder"',
      'Content: "Is there a workaround available?"',
      'Add(Note, target=Case) activity created',
      'Activity sent via Finder\'s outbox',
      'Triggers delivery to participants',
    ],
  })

  timestampOffset++

  // Add consequence node in Vendor 1 lane if vendor exists and is active
  if (vendor1 && vendor1.visible && !vendor1.hasClosed && vendor1.rmState !== 'DECLINED') {
    events.push({
      id: `${eventId}-vendor1-consequence`,
      actor: 'Vendor',
      participantId: 'vendor-1',
      label: 'Note Received',
      x: nextX,
      lane: vendor1.laneIndex,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + timestampOffset,
      enablesNext: true,
      consequences: [
        'Add(Note) received in inbox',
        'Note delivered to Vendor\'s DataLayer',
        'Vendor can now see question',
      ],
    })
    timestampOffset++
  }

  // Add consequence node in Vendor 2 lane if vendor exists and is active
  if (vendor2 && vendor2.visible && !vendor2.hasClosed && vendor2.rmState !== 'DECLINED') {
    events.push({
      id: `${eventId}-vendor2-consequence`,
      actor: 'Vendor 2',
      participantId: 'vendor-2',
      label: 'Note Received',
      x: nextX,
      lane: vendor2.laneIndex,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + timestampOffset,
      enablesNext: true,
      consequences: [
        'Add(Note) received in inbox',
        'Note delivered to Vendor 2\'s DataLayer',
        'Vendor 2 can now see question',
      ],
    })
    timestampOffset++
  }

  // Add consequence node in CaseActor lane
  if (caseactor) {
    events.push({
      id: `${eventId}-caseactor-consequence`,
      actor: 'CaseActor',
      participantId: 'caseactor',
      label: 'Note Tracked',
      x: nextX,
      lane: caseactor.laneIndex,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + timestampOffset,
      consequences: [
        'Note tracked by Case Actor',
        'Note added to case history',
        'Authoritative ledger updated',
        'Part of case audit trail',
      ],
    })
  }

  newState = addTimelineEvents(newState, events)

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

  const finder = getParticipant(newState, 'finder')
  const vendor1 = getParticipant(newState, 'vendor-1')
  const vendor2 = getParticipant(newState, 'vendor-2')
  const caseactor = getParticipant(newState, 'caseactor')

  const events = []
  let timestampOffset = 0

  // Decision node in Finder's lane
  events.push({
    id: eventId,
    actor: 'Finder',
    participantId: 'finder',
    label: 'Acknowledge Publication',
    x: nextX,
    lane: finder?.laneIndex ?? 0,
    type: 'decision' as const,
    timestamp: now,
    consequences: [
      'Finder acknowledges publication',
      'PXA: public awareness confirmed',
    ],
  })

  timestampOffset++

  // Consequence node in Vendor 1 lane (if exists)
  if (vendor1 && vendor1.visible && !vendor1.hasClosed) {
    events.push({
      id: `${eventId}-vendor1-consequence`,
      actor: 'Vendor',
      participantId: 'vendor-1',
      label: 'Publication Noted',
      x: nextX,
      lane: vendor1.laneIndex,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + timestampOffset,
      consequences: [
        'Vendor notified: Finder acknowledged publication',
        'PXA: public awareness confirmed',
      ],
    })
    timestampOffset++
  }

  // Consequence node in Vendor 2 lane (if exists)
  if (vendor2 && vendor2.visible && !vendor2.hasClosed) {
    events.push({
      id: `${eventId}-vendor2-consequence`,
      actor: 'Vendor 2',
      participantId: 'vendor-2',
      label: 'Publication Noted',
      x: nextX,
      lane: vendor2.laneIndex,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + timestampOffset,
      consequences: [
        'Vendor 2 notified: Finder acknowledged publication',
        'PXA: public awareness confirmed',
      ],
    })
    timestampOffset++
  }

  // Consequence node in CaseActor lane
  if (caseactor) {
    events.push({
      id: `${eventId}-caseactor-consequence`,
      actor: 'CaseActor',
      participantId: 'caseactor',
      label: 'Publication Tracked',
      x: nextX,
      lane: caseactor.laneIndex,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + timestampOffset,
      consequences: [
        'Finder acknowledgment tracked',
        'Authoritative ledger updated',
      ],
    })
  }

  newState = addTimelineEvents(newState, events)

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
  // Don't change phase - in multi-vendor scenarios, finder closing doesn't stop vendors
  // Per Vultron protocol: RM state (including CLOSED) is participant-specific
  // Vendors can continue working after finder closes

  const finder = getParticipant(newState, 'finder')
  const vendor1 = getParticipant(newState, 'vendor-1')
  const vendor2 = getParticipant(newState, 'vendor-2')
  const caseactor = getParticipant(newState, 'caseactor')

  const events = []
  let timestampOffset = 0

  // Decision node in Finder's lane
  events.push({
    id: eventId,
    actor: 'Finder',
    participantId: 'finder',
    label: 'Close Case',
    x: nextX,
    lane: finder?.laneIndex ?? 0,
    type: 'decision' as const,
    timestamp: now,
    consequences: [
      'Finder RM state: → CLOSED',
      'Finder leaves the case (ActivityPub: Leave)',
      'No further actions available for Finder',
      'Vendors can still continue case work',
    ],
  })

  timestampOffset++

  // Consequence node in Vendor 1 lane (if exists)
  if (vendor1 && vendor1.visible && !vendor1.hasClosed && vendor1.rmState !== 'DECLINED') {
    events.push({
      id: `${eventId}-vendor1-consequence`,
      actor: 'Vendor',
      participantId: 'vendor-1',
      label: 'Finder Closed',
      x: nextX,
      lane: vendor1.laneIndex,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + timestampOffset,
      consequences: [
        'Vendor notified: Finder closed',
        'Finder participant RM → CLOSED',
        'Vendor can still continue work',
      ],
    })
    timestampOffset++
  }

  // Consequence node in Vendor 2 lane (if exists)
  if (vendor2 && vendor2.visible && !vendor2.hasClosed && vendor2.rmState !== 'DECLINED') {
    events.push({
      id: `${eventId}-vendor2-consequence`,
      actor: 'Vendor 2',
      participantId: 'vendor-2',
      label: 'Finder Closed',
      x: nextX,
      lane: vendor2.laneIndex,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + timestampOffset,
      consequences: [
        'Vendor 2 notified: Finder closed',
        'Finder participant RM → CLOSED',
        'Vendor 2 can still continue work',
      ],
    })
    timestampOffset++
  }

  // Consequence node in CaseActor lane
  if (caseactor) {
    events.push({
      id: `${eventId}-caseactor-consequence`,
      actor: 'CaseActor',
      participantId: 'caseactor',
      label: 'Finder Closed',
      x: nextX,
      lane: caseactor.laneIndex,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + timestampOffset,
      consequences: [
        'Finder participant RM → CLOSED',
        'Leave activity tracked',
        'Authoritative ledger updated',
        'Case remains open for other participants',
      ],
    })
  }

  newState = addTimelineEvents(newState, events)

  newState = addEventLogEntries(newState, ['Finder closed their participation in the case'])
  newState = incrementXPosition(newState)

  return newState
}
