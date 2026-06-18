/**
 * Finder action handlers
 */

import type { DemoState } from '../../types'
import {
  updateParticipant,
  addTimelineEvents,
  addEventLogEntries,
  incrementXPosition,
  setPhase,
  setPxaState,
  setEmState,
} from '../../state/stateUpdaters'
import { getParticipant, getActiveVendors, getVendors } from '../../state/participantHelpers'
import { requireNextState } from '../../protocol'

export function handleSubmitReport(state: DemoState): DemoState {
  const nextX = state.nextXPosition
  const submitEventId = 'event-1'
  const now = Date.now()

  let newState = state

  // The Finder enters CVD already at RM.ACCEPTED. Per the formal protocol, a
  // Finder's START → RECEIVED → VALID → ACCEPTED traversal happens privately —
  // they discover, validate, and prioritize their own find before contacting
  // anyone (this is the Finder → Reporter transition; see states.md start-state
  // table: Finder/Reporter starts at (A, N, pxa)). So the only observable RM
  // states for the Finder are ACCEPTED ⇄ DEFERRED → CLOSED. We therefore seed
  // ACCEPTED rather than RECEIVED, which also makes the later `close` transition
  // legal (close is not permitted from RECEIVED).
  newState = updateParticipant(newState, 'finder', { rmState: 'ACCEPTED' })
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
        'Finder\'s RM: ACCEPTED (validated & prioritized privately before disclosure)',
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
  const caseactor = getParticipant(state, 'caseactor')

  let newState = state

  // Update finder to show accepted
  newState = updateParticipant(newState, 'finder', { embargoAccepted: true })

  // Check if ALL vendors have accepted (must check ALL visible vendors, not just active ones)
  const allVendors = getVendors(newState).filter(v => v.visible && !v.hasClosed)
  const allParticipantsAccepted = allVendors.length > 0 && allVendors.every(v => v.embargoAccepted)

  // If all participants accepted, activate embargo
  if (allParticipantsAccepted) {
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
        allParticipantsAccepted ? 'All participants accepted - embargo is now ACTIVE' : `Awaiting ${allVendors.filter(v => !v.embargoAccepted).length} vendor acceptance(s)`,
      ],
    },
    // Consequence node in CaseActor lane - always created
    {
      id: `${eventId}-caseactor-consequence`,
      actor: 'CaseActor',
      participantId: 'caseactor',
      label: allParticipantsAccepted ? 'M1 REACHED' : 'Finder Accepted',
      x: nextX,
      lane: caseactor?.laneIndex ?? 2,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + 1,
      enablesNext: allParticipantsAccepted,
      consequences: allParticipantsAccepted ? [
        '✓ M1 REACHED: Case active',
        `Embargo: ACTIVE with ${allVendors.length + 1} participants`,
        'EmAcceptEmbargoActivity received from all',
        'ActivateEmbargoActivity processed',
        'Authoritative ledger updated',
      ] : [
        'Finder EmAcceptEmbargoActivity received',
        `Awaiting ${allVendors.filter(v => !v.embargoAccepted).length} vendor acceptance(s)`,
        'EM state remains PROPOSED',
      ],
    },
  ]

  // Add consequence nodes to ALL vendors' lanes (not just active ones)
  // During PROPOSED state, ALL vendors need to see the acceptance notification
  let timestampOffset = 2
  allVendors.forEach(vendor => {
    events.push({
      id: `${eventId}-${vendor.id}-consequence`,
      actor: vendor.name,
      participantId: vendor.id,
      label: allParticipantsAccepted ? 'Embargo Active' : 'Finder Accepted',
      x: nextX,
      lane: vendor.laneIndex,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + timestampOffset,
      enablesNext: allParticipantsAccepted,
      consequences: allParticipantsAccepted ? [
        'AnnounceEmbargoActivity received',
        'All participants accepted - EM state → ACTIVE',
        '90-day embargo now in effect',
        `✓ M1 REACHED: Case active with ${allVendors.length + 1} participants, embargo established`,
      ] : [
        'Finder has accepted embargo',
        'Vendor must still accept or reject',
        'EM state remains PROPOSED',
      ],
    })
    timestampOffset++
  })

  newState = addTimelineEvents(newState, events)

  newState = addEventLogEntries(newState, [
    'Finder accepted embargo',
    ...(allParticipantsAccepted ? [`✓ M1 REACHED: Case active with ${allVendors.length + 1} participants, embargo active`] : []),
  ])

  newState = incrementXPosition(newState)

  return newState
}

export function handleFinderRejectEmbargo(state: DemoState): DemoState {
  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  const finder = getParticipant(state, 'finder')
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
  const activeVendors = getActiveVendors(newState)

  activeVendors.forEach(vendor => {
    events.push({
      id: `${eventId}-${vendor.id}-consequence`,
      actor: vendor.name,
      participantId: vendor.id,
      label: 'Embargo Rejected',
      x: nextX,
      lane: vendor.laneIndex,
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
  })

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

  // Mark that an unanswered Finder question now exists. This is tracked at the
  // case level (independent of `phase`) so that a later RM transition by any one
  // vendor (e.g. deferring their report, which overwrites `phase`) does not hide
  // the reply option from the other participants. Per Vultron protocol the Q&A
  // dimension is case-wide and independent of any single participant's RM state.
  newState = { ...newState, hasPendingFinderNote: true }

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

  // Add consequence nodes to all active vendors (excluding declined vendors)
  const activeVendors = getActiveVendors(newState).filter(v => v.rmState !== 'DECLINED')

  activeVendors.forEach(vendor => {
    events.push({
      id: `${eventId}-${vendor.id}-consequence`,
      actor: vendor.name,
      participantId: vendor.id,
      label: 'Note Received',
      x: nextX,
      lane: vendor.laneIndex,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + timestampOffset,
      enablesNext: true,
      consequences: [
        'Add(Note) received in inbox',
        `Note delivered to ${vendor.name}'s DataLayer`,
        `${vendor.name} can now see question`,
      ],
    })
    timestampOffset++
  })

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

  // Consequence nodes in all vendor lanes
  const activeVendors = getActiveVendors(newState)

  activeVendors.forEach(vendor => {
    events.push({
      id: `${eventId}-${vendor.id}-consequence`,
      actor: vendor.name,
      participantId: vendor.id,
      label: 'Publication Noted',
      x: nextX,
      lane: vendor.laneIndex,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + timestampOffset,
      consequences: [
        `${vendor.name} notified: Finder acknowledged publication`,
        'PXA: public awareness confirmed',
      ],
    })
    timestampOffset++
  })

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

  const finderState = getParticipant(state, 'finder')
  if (!finderState) return state

  let newState = state

  // RM destination computed from the protocol artifact. The Finder enters CVD at
  // ACCEPTED (see handleSubmitReport) and may pause at DEFERRED; `close` is legal
  // from both. `hasClosed` is a demo-only flag with no machine slot.
  const nextRmState = requireNextState('rm', finderState.rmState, 'close')

  newState = updateParticipant(newState, 'finder', { rmState: nextRmState, hasClosed: true })
  // Don't change phase - in multi-vendor scenarios, finder closing doesn't stop vendors
  // Per Vultron protocol: RM state (including CLOSED) is participant-specific
  // Vendors can continue working after finder closes

  const finder = getParticipant(newState, 'finder')
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

  // Consequence nodes in all vendor lanes (excluding declined vendors)
  const activeVendors = getActiveVendors(newState).filter(v => v.rmState !== 'DECLINED')

  activeVendors.forEach(vendor => {
    events.push({
      id: `${eventId}-${vendor.id}-consequence`,
      actor: vendor.name,
      participantId: vendor.id,
      label: 'Finder Closed',
      x: nextX,
      lane: vendor.laneIndex,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + timestampOffset,
      consequences: [
        `${vendor.name} notified: Finder closed`,
        'Finder participant RM → CLOSED',
        `${vendor.name} can still continue work`,
      ],
    })
    timestampOffset++
  })

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

export function handleFinderProposeRevision(state: DemoState): DemoState {
  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  const finder = getParticipant(state, 'finder')
  const caseactor = getParticipant(state, 'caseactor')

  let newState = state

  // Per Vultron protocol: A → pR (Active → propose → Revise)
  newState = setEmState(newState, 'REVISE')
  newState = { ...newState, embargoProposerId: 'finder' }  // Track who proposed this revision

  const events = []
  let timestampOffset = 0

  // Decision node in Finder's lane
  events.push({
    id: eventId,
    actor: 'Finder',
    participantId: 'finder',
    label: 'Propose Embargo Revision',
    x: nextX,
    lane: finder?.laneIndex ?? 0,
    type: 'decision' as const,
    timestamp: now,
    consequences: [
      'Embargo revision proposed by Finder',
      'EmProposeEmbargoActivity created (revision)',
      'Existing embargo remains active',
      'EM state → REVISE',
    ],
  })
  timestampOffset++

  // Consequence nodes for ALL vendors (including those who previously rejected)
  // Per Vultron protocol: embargo revision is a new proposal that ALL participants can accept/reject
  for (const vendor of getVendors(newState).filter((v) => v.visible && !v.hasClosed)) {
    const wasParticipating = vendor.embargoAccepted

    // Reset embargoAccepted for ALL vendors - they need to accept the revision
    // Only set embargoProposedToParticipant for vendors who were NOT participating
    newState = updateParticipant(newState, vendor.id, {
      embargoAccepted: false,
      embargoProposedToParticipant: !wasParticipating
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
        `${vendor.name} sees Finder's proposed revision`,
        'Current embargo still active',
      ],
    })
    timestampOffset++
  }

  // Finder proposed the revision, which implies acceptance
  newState = updateParticipant(newState, 'finder', {
    embargoAccepted: true
  })

  // Consequence node in CaseActor's lane
  if (caseactor) {
    events.push({
      id: `${eventId}-caseactor-consequence`,
      actor: 'CaseActor',
      participantId: 'caseactor',
      label: 'Revision Proposal Received',
      x: nextX,
      lane: caseactor.laneIndex,
      type: 'consequence' as const,
      timestamp: now + timestampOffset,
      causedBy: eventId,
      consequences: [
        'EmProposeEmbargoActivity received (revision)',
        'CaseActor sees Finder proposed revision',
      ],
    })
  }

  newState = addTimelineEvents(newState, events)
  newState = addEventLogEntries(newState, ['Finder proposed embargo revision'])
  newState = incrementXPosition(newState)

  return newState
}

export function handleFinderAcceptRevision(state: DemoState): DemoState {
  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  const finder = getParticipant(state, 'finder')

  let newState = state

  // Mark Finder as having accepted
  newState = updateParticipant(newState, 'finder', {
    embargoAccepted: true
  })

  // Per Vultron protocol: R → aA (Revise → accept → Active)
  // But ONLY if ALL embargo participants have accepted
  const allParticipantsAccepted = getActiveVendors(newState).every((v) => v.embargoAccepted)

  if (allParticipantsAccepted) {
    newState = setEmState(newState, 'ACTIVE')
    newState = { ...newState, embargoProposerId: undefined }  // Clear proposer when revision is accepted
  }
  // Otherwise, stay in REVISE state

  const caseactor = getParticipant(newState, 'caseactor')
  const events = []
  let timestampOffset = 0

  // Decision node in Finder's lane
  events.push({
    id: eventId,
    actor: 'Finder',
    participantId: 'finder',
    label: 'Accept Revision',
    x: nextX,
    lane: finder?.laneIndex ?? 0,
    type: 'decision' as const,
    timestamp: now,
    consequences: [
      'Finder accepted embargo revision',
      'EmAcceptEmbargoActivity created',
      allParticipantsAccepted ? 'Revised embargo terms now active' : 'Awaiting all vendors to accept',
      allParticipantsAccepted ? 'EM state → ACTIVE' : 'EM state remains REVISE',
    ],
  })
  timestampOffset++

  // Consequence nodes for all vendors
  const vendors = getVendors(newState).filter((v) => v.visible && !v.hasClosed)
  for (const vendor of vendors) {
    events.push({
      id: `${eventId}-${vendor.id}-consequence`,
      actor: vendor.name,
      participantId: vendor.id,
      label: allParticipantsAccepted ? 'Revision Accepted' : 'Finder Accepted',
      x: nextX,
      lane: vendor.laneIndex,
      type: 'consequence' as const,
      timestamp: now + timestampOffset,
      causedBy: eventId,
      enablesNext: true,
      consequences: [
        'Finder accepted revision',
        allParticipantsAccepted ? 'All participants accepted - EM → ACTIVE' : 'Awaiting other participants',
      ],
    })
    timestampOffset++
  }

  // Consequence node in CaseActor's lane
  if (caseactor) {
    events.push({
      id: `${eventId}-caseactor-consequence`,
      actor: 'CaseActor',
      participantId: 'caseactor',
      label: allParticipantsAccepted ? 'Revision Accepted' : 'Finder Accepted',
      x: nextX,
      lane: caseactor.laneIndex,
      type: 'consequence' as const,
      timestamp: now + timestampOffset,
      causedBy: eventId,
      consequences: [
        'Finder accepted revision',
        allParticipantsAccepted ? 'All participants accepted - EM → ACTIVE' : 'Awaiting other participants',
        'Authoritative ledger updated',
      ],
    })
  }

  newState = addTimelineEvents(newState, events)
  newState = addEventLogEntries(newState, ['Finder accepted embargo revision'])
  newState = incrementXPosition(newState)

  return newState
}

export function handleFinderRejectRevision(state: DemoState): DemoState {
  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  const finder = getParticipant(state, 'finder')
  const caseactor = getParticipant(state, 'caseactor')

  let newState = state

  // Per Vultron protocol: R → rA (Revise → reject → Active)
  // Revision rejected - restore original embargo state
  newState = setEmState(newState, 'ACTIVE')
  newState = { ...newState, embargoProposerId: undefined }  // Clear proposer when revision is rejected

  // Restore embargoAccepted for participants who were bound by original embargo
  // Finder was participating, so restore to true
  newState = updateParticipant(newState, 'finder', {
    embargoAccepted: true
  })

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

  // Decision node in Finder's lane
  events.push({
    id: eventId,
    actor: 'Finder',
    participantId: 'finder',
    label: 'Reject Revision',
    x: nextX,
    lane: finder?.laneIndex ?? 0,
    type: 'decision' as const,
    timestamp: now,
    consequences: [
      'Finder rejected embargo revision',
      'EmRejectEmbargoActivity created',
      'Original embargo terms remain active',
      'EM state → ACTIVE',
    ],
  })
  timestampOffset++

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
        'Finder rejected revision',
        'Original embargo terms remain',
      ],
    })
    timestampOffset++
  }

  // Consequence node in CaseActor's lane
  if (caseactor) {
    events.push({
      id: `${eventId}-caseactor-consequence`,
      actor: 'CaseActor',
      participantId: 'caseactor',
      label: 'Revision Rejected',
      x: nextX,
      lane: caseactor.laneIndex,
      type: 'consequence' as const,
      timestamp: now + timestampOffset,
      causedBy: eventId,
      consequences: [
        'Finder rejected revision',
        'Original embargo terms remain',
      ],
    })
  }

  newState = addTimelineEvents(newState, events)
  newState = addEventLogEntries(newState, ['Finder rejected embargo revision - original terms remain'])
  newState = incrementXPosition(newState)

  return newState
}
