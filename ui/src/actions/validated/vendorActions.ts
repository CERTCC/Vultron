/**
 * Vendor action handlers (works for vendor-1, vendor-2, etc.)
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
import { getParticipant, getActiveParticipants, getActiveVendors, getVendors } from '../../state/participantHelpers'
import { requireNextState } from '../../protocol'

export function handleValidateReport(state: DemoState, vendorId: string): DemoState {
  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  const vendor = getParticipant(state, vendorId)
  if (!vendor) return state

  let newState = state

  // RM destination is computed from the protocol artifact (protocol_states.json)
  // rather than hardcoded. The `validate` trigger is legal from RECEIVED and
  // also from INVALID (re-validation), so deriving from the vendor's current
  // rmState is more faithful than assuming RECEIVED → VALID.
  const nextRmState = requireNextState('rm', vendor.rmState, 'validate')

  newState = updateParticipant(newState, vendorId, { rmState: nextRmState })
  newState = setPhase(newState, 'report-validated')

  // Per Vultron protocol: case state changes should broadcast to all participants
  const activeLanes = getActiveParticipants(newState)
  const events = []
  let timestampOffset = 0

  // Decision node in validating vendor's lane
  events.push({
    id: eventId,
    actor: vendor.name,
    participantId: vendorId,
    label: 'Validate Report',
    x: nextX,
    lane: vendor.laneIndex,
    type: 'decision' as const,
    timestamp: now + timestampOffset++,
    consequences: [
      'Accept(Offer) activity created',
      'ValidateReportReceivedUseCase executes',
      `${vendor.name} RM state: RECEIVED → VALID`,
      'Report deemed legitimate',
      'Can proceed with case work',
    ],
  })

  // Consequence nodes for ALL other active participants
  activeLanes
    .filter(p => p.id !== vendorId) // Exclude the validating vendor
    .forEach(participant => {
      events.push({
        id: `${eventId}-${participant.id}-consequence`,
        actor: participant.name,
        participantId: participant.id,
        label: 'Validation Noted',
        x: nextX,
        lane: participant.laneIndex,
        type: 'consequence' as const,
        timestamp: now + timestampOffset++,
        causedBy: eventId,
        consequences: [
          'Accept activity received',
          `${vendor.name} has validated the report`,
          `${vendor.name} RM → VALID`,
          participant.id === 'caseactor'
            ? 'Authoritative ledger updated'
            : 'Case work can proceed',
        ],
      })
    })

  newState = addTimelineEvents(newState, events)
  newState = addEventLogEntries(newState, [`${vendor.name} validated the report (RM → VALID)`])
  newState = incrementXPosition(newState)

  return newState
}

export function handleAcceptReport(state: DemoState, vendorId: string): DemoState {
  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  const vendor = getParticipant(state, vendorId)
  if (!vendor) return state

  let newState = state

  // RM destination computed from the protocol artifact. `accept` is legal from
  // VALID and from DEFERRED (resume work) — both land at ACCEPTED — so deriving
  // from the vendor's current rmState is more faithful than a hardcoded value.
  const nextRmState = requireNextState('rm', vendor.rmState, 'accept')

  newState = updateParticipant(newState, vendorId, { rmState: nextRmState })
  newState = setPhase(newState, 'report-accepted')

  const activeLanes = getActiveParticipants(newState)
  const events = []
  let timestampOffset = 0

  // Decision node in accepting vendor's lane
  events.push({
    id: eventId,
    actor: vendor.name,
    participantId: vendorId,
    label: 'Accept Report',
    x: nextX,
    lane: vendor.laneIndex,
    type: 'decision' as const,
    timestamp: now + timestampOffset++,
    consequences: [
      'Accept(Report) activity created',
      `${vendor.name} RM state: ${vendor.rmState} → ACCEPTED`,
      'Report accepted and prioritized',
      'Vendor commits to working on fix',
    ],
  })

  // Consequence nodes for ALL other active participants
  activeLanes
    .filter(p => p.id !== vendorId)
    .forEach(participant => {
      events.push({
        id: `${eventId}-${participant.id}-consequence`,
        actor: participant.name,
        participantId: participant.id,
        label: 'Acceptance Noted',
        x: nextX,
        lane: participant.laneIndex,
        type: 'consequence' as const,
        causedBy: eventId,
        timestamp: now + timestampOffset++,
        consequences: [
          'Accept activity received',
          `${vendor.name} has accepted the report`,
          `${vendor.name} RM → ACCEPTED`,
          participant.id === 'caseactor'
            ? 'Authoritative ledger updated'
            : 'Vendor committed to fix development',
        ],
      })
    })

  newState = addTimelineEvents(newState, events)
  newState = addEventLogEntries(newState, [`${vendor.name} accepted the report (RM → ACCEPTED)`])
  newState = incrementXPosition(newState)

  return newState
}

export function handleDeferReport(state: DemoState, vendorId: string): DemoState {
  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  const vendor = getParticipant(state, vendorId)
  if (!vendor) return state

  let newState = state

  // RM destination computed from the protocol artifact (defer is legal from
  // VALID and from ACCEPTED; the demo only surfaces it from VALID).
  const nextRmState = requireNextState('rm', vendor.rmState, 'defer')

  newState = updateParticipant(newState, vendorId, { rmState: nextRmState })
  newState = setPhase(newState, 'report-deferred')

  const activeLanes = getActiveParticipants(newState)
  const events = []
  let timestampOffset = 0

  // Decision node in deferring vendor's lane
  events.push({
    id: eventId,
    actor: vendor.name,
    participantId: vendorId,
    label: 'Defer Report',
    x: nextX,
    lane: vendor.laneIndex,
    type: 'decision' as const,
    timestamp: now + timestampOffset++,
    consequences: [
      'Defer(Report) activity created',
      `${vendor.name} RM state: VALID → DEFERRED`,
      'Report deferred for later consideration',
      'Work paused pending re-prioritization',
    ],
  })

  // Consequence nodes for ALL other active participants
  activeLanes
    .filter(p => p.id !== vendorId)
    .forEach(participant => {
      events.push({
        id: `${eventId}-${participant.id}-consequence`,
        actor: participant.name,
        participantId: participant.id,
        label: 'Deferral Noted',
        x: nextX,
        lane: participant.laneIndex,
        type: 'consequence' as const,
        causedBy: eventId,
        timestamp: now + timestampOffset++,
        consequences: [
          'Defer activity received',
          `${vendor.name} has deferred the report`,
          `${vendor.name} RM → DEFERRED`,
          participant.id === 'caseactor'
            ? 'Authoritative ledger updated'
            : 'Vendor has paused work',
        ],
      })
    })

  newState = addTimelineEvents(newState, events)
  newState = addEventLogEntries(newState, [`${vendor.name} deferred the report (RM → DEFERRED)`])
  newState = incrementXPosition(newState)

  return newState
}

export function handleInvalidateReport(state: DemoState, vendorId: string): DemoState {
  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  const vendor = getParticipant(state, vendorId)
  if (!vendor) return state

  let newState = state

  // RM destination computed from the protocol artifact (invalidate: RECEIVED → INVALID).
  const nextRmState = requireNextState('rm', vendor.rmState, 'invalidate')

  newState = updateParticipant(newState, vendorId, { rmState: nextRmState })
  newState = setPhase(newState, 'report-invalidated')

  // Per Vultron protocol: case state changes should broadcast to all participants
  const activeLanes = getActiveParticipants(newState)
  const events = []
  let timestampOffset = 0

  // Decision node in invalidating vendor's lane
  events.push({
    id: eventId,
    actor: vendor.name,
    participantId: vendorId,
    label: 'Invalidate Report',
    x: nextX,
    lane: vendor.laneIndex,
    type: 'decision' as const,
    timestamp: now + timestampOffset++,
    consequences: [
      'Reject(Offer) activity created',
      `${vendor.name} RM state: RECEIVED → INVALID`,
      'Report deemed invalid',
      'Case held until reconsideration or closure',
    ],
  })

  // Consequence nodes for ALL other active participants
  activeLanes
    .filter(p => p.id !== vendorId) // Exclude the invalidating vendor
    .forEach(participant => {
      events.push({
        id: `${eventId}-${participant.id}-consequence`,
        actor: participant.name,
        participantId: participant.id,
        label: 'Invalidation Noted',
        x: nextX,
        lane: participant.laneIndex,
        type: 'consequence' as const,
        causedBy: eventId,
        timestamp: now + timestampOffset++,
        consequences: [
          'TentativeReject activity received',
          `${vendor.name} has invalidated the report`,
          `${vendor.name} RM → INVALID`,
          participant.id === 'caseactor'
            ? 'Authoritative ledger updated'
            : 'Report held, may be reconsidered',
        ],
      })
    })

  newState = addTimelineEvents(newState, events)

  newState = addEventLogEntries(newState, [`${vendor.name} invalidated the report (RM → INVALID)`])
  newState = incrementXPosition(newState)

  return newState
}

export function handleAcceptEmbargo(state: DemoState, vendorId: string): DemoState {
  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  const vendor = getParticipant(state, vendorId)
  const finder = getParticipant(state, 'finder')
  const caseactor = getParticipant(state, 'caseactor')
  if (!vendor) return state

  // Distinguish between different acceptance scenarios:
  // 1. Late joiner accepting an ACTIVE embargo (true late joiner)
  // 2. Vendor accepting a REVISE state (revision acceptance)
  // 3. Initial embargo proposal acceptance
  const isRevisionAcceptance = vendor.embargoProposedToParticipant && state.emState === 'REVISE'
  const isLateJoiner = vendor.embargoProposedToParticipant && state.emState === 'ACTIVE'

  let newState = state

  newState = updateParticipant(newState, vendorId, {
    embargoAccepted: true,
    embargoProposedToParticipant: false  // Clear the flag once accepted
  })

  // Calculate consensus: ALL participants (Finder + ALL visible vendors) must accept
  // For PROPOSED state: check ALL vendors who received the proposal
  // For REVISE state: check ALL active vendors (those participating in embargo)
  const allVendors = isRevisionAcceptance ? getActiveVendors(newState) : getVendors(newState).filter(v => v.visible && !v.hasClosed)
  const allParticipantsAccepted = (finder?.embargoAccepted || false) &&
    allVendors.every((v) => v.embargoAccepted)

  // Handle EM state transitions:
  // - Revision acceptance: check if ALL embargo participants have accepted before REVISE → ACTIVE
  // - Late joiner: stays ACTIVE
  // - Initial proposal: check if ALL parties (Finder + ALL vendors) accepted
  if (isRevisionAcceptance) {
    if (allParticipantsAccepted) {
      // EM destination computed from the protocol artifact (accept: REVISE → ACTIVE).
      newState = setEmState(newState, requireNextState('em', state.emState, 'accept'))
      newState = { ...newState, embargoProposerId: undefined }  // Clear proposer when revision is accepted
    }
    // Otherwise, stay in REVISE state
  } else if (!isLateJoiner && allParticipantsAccepted) {
    // EM destination computed from the protocol artifact (accept: PROPOSED → ACTIVE).
    newState = { ...newState, emState: requireNextState('em', state.emState, 'accept'), phase: 'embargo-accepted' }
  }

  const events = [
    {
      id: eventId,
      actor: vendor.name,
      participantId: vendorId,
      label: isRevisionAcceptance ? 'Accept Revision' : (isLateJoiner ? 'Accept Existing Embargo' : 'Accept Embargo'),
      x: nextX,
      lane: vendor.laneIndex,
      type: 'decision' as const,
      timestamp: now,
      consequences: isRevisionAcceptance ? [
        'EmAcceptEmbargoActivity created',
        `${vendor.name} accepts revised embargo terms`,
        allParticipantsAccepted ? 'All participants accepted - EM state → ACTIVE' : 'Awaiting other participants',
        `${vendor.name} can now fully participate`,
      ] : (isLateJoiner ? [
        'EmAcceptEmbargoActivity created',
        `${vendor.name} accepts existing embargo`,
        'Embargo remains ACTIVE',
        `${vendor.name} can now fully participate`,
      ] : [
        'EmAcceptEmbargoActivity created',
        `${vendor.name} accepts 90-day embargo`,
        allParticipantsAccepted ? 'All participants accepted - embargo is now ACTIVE' : 'Awaiting other participants to accept',
      ]),
    },
    // Consequence node in CaseActor lane - always created
    {
      id: `${eventId}-caseactor-consequence`,
      actor: 'CaseActor',
      participantId: 'caseactor',
      label: isRevisionAcceptance ? (allParticipantsAccepted ? 'Revision Accepted' : `${vendor.name} Accepted`) : (isLateJoiner ? `${vendor.name} Joined` : (allParticipantsAccepted ? 'M1 REACHED' : `${vendor.name} Accepted`)),
      x: nextX,
      lane: caseactor?.laneIndex ?? 2,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + 1,
      enablesNext: allParticipantsAccepted && !isLateJoiner && !isRevisionAcceptance,
      consequences: isRevisionAcceptance ? [
        `${vendor.name} EmAcceptEmbargoActivity received`,
        allParticipantsAccepted ? 'Revised embargo terms now active' : `Awaiting ${allVendors.filter(v => !v.embargoAccepted).length} more acceptance(s)`,
        allParticipantsAccepted ? 'EM state → ACTIVE' : 'EM state remains REVISE',
        'Authoritative ledger updated',
      ] : (isLateJoiner ? [
        `${vendor.name} EmAcceptEmbargoActivity received`,
        `${vendor.name} bound by existing embargo`,
        'Embargo remains ACTIVE',
        `${vendor.name} can now fully participate`,
        'Authoritative ledger updated',
      ] : (allParticipantsAccepted ? [
        '✓ M1 REACHED: Case active',
        `Embargo: ACTIVE with ${allVendors.length + 1} participants`,
        'EmAcceptEmbargoActivity received from all',
        'ActivateEmbargoActivity processed',
        'Authoritative ledger updated',
      ] : [
        `${vendor.name} EmAcceptEmbargoActivity received`,
        `Awaiting ${allVendors.filter(v => !v.embargoAccepted).length + (finder?.embargoAccepted ? 0 : 1)} more acceptance(s)`,
        'EM state remains PROPOSED',
      ])),
    },
    // Consequence node in Finder lane - always created
    {
      id: `${eventId}-finder-consequence`,
      actor: 'Finder',
      participantId: 'finder',
      label: isRevisionAcceptance ? (allParticipantsAccepted ? 'Revision Accepted' : `${vendor.name} Accepted`) : (isLateJoiner ? `${vendor.name} Joined` : (allParticipantsAccepted ? 'Embargo Active' : `${vendor.name} Accepted`)),
      x: nextX,
      lane: finder?.laneIndex ?? 0,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + 2,
      consequences: isRevisionAcceptance ? [
        `${vendor.name} accepted revision`,
        allParticipantsAccepted ? 'All participants accepted - EM → ACTIVE' : 'Awaiting other participants',
      ] : (isLateJoiner ? [
        `${vendor.name} accepted existing embargo`,
        `${vendor.name} is now bound by embargo`,
        'Embargo remains ACTIVE',
      ] : (allParticipantsAccepted ? [
        'AnnounceEmbargoActivity received',
        'All participants accepted - embargo is now ACTIVE',
        'Coordinated disclosure begins',
      ] : [
        `Notified: ${vendor.name} accepted embargo`,
        'Awaiting other participants',
        'EM state remains PROPOSED',
      ])),
    },
  ]

  // Add consequence nodes to ALL other vendors' lanes (not just active ones)
  // During PROPOSED state, ALL vendors need to see the acceptance notifications
  let timestampOffset = 3
  const allOtherVendors = getVendors(newState).filter(v => v.visible && !v.hasClosed && v.id !== vendorId)

  allOtherVendors.forEach(otherVendor => {
    events.push({
      id: `${eventId}-${otherVendor.id}-consequence`,
      actor: otherVendor.name,
      participantId: otherVendor.id,
      label: isRevisionAcceptance ? (allParticipantsAccepted ? 'Revision Accepted' : `${vendor.name} Accepted`) : (isLateJoiner ? `${vendor.name} Joined` : (allParticipantsAccepted ? 'Embargo Active' : `${vendor.name} Accepted`)),
      x: nextX,
      lane: otherVendor.laneIndex,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + timestampOffset,
      consequences: isRevisionAcceptance ? [
        `${vendor.name} accepted revision`,
        allParticipantsAccepted ? 'All participants accepted - EM → ACTIVE' : 'Awaiting other participants',
      ] : (isLateJoiner ? [
        `${vendor.name} accepted existing embargo`,
        `${vendor.name} is now bound by embargo`,
        'Embargo remains ACTIVE',
      ] : (allParticipantsAccepted ? [
        'AnnounceEmbargoActivity received',
        'All participants accepted - embargo is now ACTIVE',
        'Coordinated disclosure begins',
      ] : [
        `Notified: ${vendor.name} accepted embargo`,
        'Awaiting other participants',
        'EM state remains PROPOSED',
      ])),
    })
    timestampOffset++
  })

  newState = addTimelineEvents(newState, events)
  newState = addEventLogEntries(newState, [
    isLateJoiner ? `${vendor.name} accepted existing embargo and joined case` : `${vendor.name} accepted embargo`,
    ...(allParticipantsAccepted && !isLateJoiner ? [`✓ M1 REACHED: Case active with ${allVendors.length + 1} participants, embargo active`] : []),
  ])
  newState = incrementXPosition(newState)

  return newState
}

export function handleRejectEmbargo(state: DemoState, vendorId: string): DemoState {
  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  const vendor = getParticipant(state, vendorId)
  if (!vendor) return state

  const finder = getParticipant(state, 'finder')
  const caseactor = getParticipant(state, 'caseactor')

  // Check if this is a late-joining vendor rejecting an already-active embargo
  // Per Vultron protocol (working_with_others.md lines 112-115):
  // "The inviting Participant SHOULD NOT share the vulnerability report with the newly invited
  // Participant unless the new Participant has accepted the existing embargo."
  // If late joiner rejects, they cannot fully participate (may need to be removed from case)
  const isLateJoiner = vendor.embargoProposedToParticipant && (state.emState === 'ACTIVE' || state.emState === 'REVISE')

  let newState = state

  // If late joiner rejects an active embargo, embargo stays ACTIVE but they are excluded
  // If rejecting during initial proposal, embargo goes back to NONE.
  // EM destination computed from the protocol artifact (reject: PROPOSED → NONE).
  if (!isLateJoiner) {
    newState = { ...newState, emState: requireNextState('em', state.emState, 'reject'), phase: 'embargo-rejected' }
  }

  // Update vendor state - clear embargo proposal flag, keep embargoAccepted as false
  newState = updateParticipant(newState, vendorId, {
    embargoProposedToParticipant: false
  })

  const events = []
  let timestampOffset = 0

  // Decision node in rejecting vendor's lane
  events.push({
    id: eventId,
    actor: vendor.name,
    participantId: vendorId,
    label: isLateJoiner ? 'Reject Existing Embargo' : 'Reject Embargo',
    x: nextX,
    lane: vendor.laneIndex,
    type: 'decision' as const,
    timestamp: now,
    consequences: isLateJoiner ? [
      'EmRejectEmbargoActivity created',
      `${vendor.name} rejects existing embargo`,
      'Embargo remains ACTIVE for other participants',
      `${vendor.name} cannot fully participate`,
    ] : [
      'EmRejectEmbargoActivity created',
      `${vendor.name} rejects embargo proposal`,
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
      enablesNext: !isLateJoiner,
      consequences: isLateJoiner ? [
        'EmRejectEmbargoActivity received',
        `${vendor.name} rejected existing embargo`,
        'Embargo remains ACTIVE',
        `${vendor.name} excluded from full participation`,
        'Authoritative ledger updated',
      ] : [
        'EmRejectEmbargoActivity received',
        'Embargo proposal discarded',
        'EM state → NONE',
        'Can repropose with revised terms',
      ],
    })
    timestampOffset++
  }

  // Consequence node in Finder's lane
  if (finder && !finder.hasClosed) {
    events.push({
      id: `${eventId}-finder-consequence`,
      actor: 'Finder',
      participantId: 'finder',
      label: 'Embargo Rejected',
      x: nextX,
      lane: finder.laneIndex,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + timestampOffset,
      consequences: isLateJoiner ? [
        `${vendor.name} rejected existing embargo`,
        'Embargo remains ACTIVE',
        `${vendor.name} cannot fully participate`,
      ] : [
        `${vendor.name} rejected embargo`,
        'EM state → NONE',
        'Awaiting reproposal or continuation',
      ],
    })
    timestampOffset++
  }

  // Consequence nodes in other vendor lanes (not the rejecting vendor)
  const otherVendors = getActiveVendors(newState).filter(v => v.id !== vendorId)

  otherVendors.forEach(otherVendor => {
    events.push({
      id: `${eventId}-${otherVendor.id}-consequence`,
      actor: otherVendor.name,
      participantId: otherVendor.id,
      label: 'Embargo Rejected',
      x: nextX,
      lane: otherVendor.laneIndex,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + timestampOffset,
      consequences: isLateJoiner ? [
        `${vendor.name} rejected existing embargo`,
        'Embargo remains ACTIVE',
        `${vendor.name} excluded from participation`,
      ] : [
        `${vendor.name} rejected embargo`,
        'EM state → NONE',
        'Awaiting reproposal or continuation',
      ],
    })
    timestampOffset++
  })

  newState = addTimelineEvents(newState, events)

  newState = addEventLogEntries(newState, [
    isLateJoiner
      ? `${vendor.name} rejected existing embargo - cannot fully participate`
      : `${vendor.name} rejected embargo proposal`
  ])
  newState = incrementXPosition(newState)

  return newState
}

export function handleNotifyFixReady(state: DemoState, vendorId: string): DemoState {
  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  const vendor = getParticipant(state, vendorId)
  if (!vendor) return state

  const finder = getParticipant(state, 'finder')
  const caseactor = getParticipant(state, 'caseactor')

  let newState = state

  // VFD destination computed from the protocol artifact (fix_is_ready: Vfd → VFd).
  const nextVfdState = requireNextState('vfd', vendor.vfdState, 'fix_is_ready')

  newState = updateParticipant(newState, vendorId, { vfdState: nextVfdState })
  newState = setPhase(newState, 'fix-ready')

  const events = []
  let timestampOffset = 0

  // Decision node in vendor's lane
  events.push({
    id: eventId,
    actor: vendor.name,
    participantId: vendorId,
    label: 'Notify Fix Ready',
    x: nextX,
    lane: vendor.laneIndex,
    type: 'decision' as const,
    timestamp: now,
    consequences: [
      `${vendor.name} VFD state: Vfd → VFd`,
      '✓ M4 REACHED: Fix ready',
      'Fix is ready but not yet deployed',
    ],
  })

  timestampOffset++

  // Consequence node in Finder lane (only if Finder hasn't closed)
  if (finder && !finder.hasClosed) {
    events.push({
      id: `${eventId}-finder-consequence`,
      actor: 'Finder',
      participantId: 'finder',
      label: 'Fix Ready',
      x: nextX,
      lane: finder.laneIndex,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + timestampOffset,
      consequences: [
        'Finder notified: Fix is ready',
        `${vendor.name} VFD → VFd`,
        'Awaiting fix deployment',
      ],
    })
    timestampOffset++
  }

  // Consequence nodes in other vendor lanes (notify all other active vendors)
  const otherVendors = getActiveVendors(newState).filter(v => v.id !== vendorId)

  otherVendors.forEach(otherVendor => {
    events.push({
      id: `${eventId}-${otherVendor.id}-consequence`,
      actor: otherVendor.name,
      participantId: otherVendor.id,
      label: `${vendor.name} Fix Ready`,
      x: nextX,
      lane: otherVendor.laneIndex,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + timestampOffset,
      consequences: [
        `${otherVendor.name} notified: Fix is ready`,
        `${vendor.name} VFD → VFd`,
        'Other vendor has completed fix',
      ],
    })
    timestampOffset++
  })

  // Consequence node in CaseActor lane
  if (caseactor) {
    events.push({
      id: `${eventId}-case-consequence`,
      actor: 'CaseActor',
      participantId: 'caseactor',
      label: 'M4 Tracked',
      x: nextX,
      lane: caseactor.laneIndex,
      type: 'consequence' as const,
      timestamp: now + timestampOffset,
      causedBy: eventId,
      consequences: [
        '✓ M4 REACHED: Fix ready',
        `${vendor.name} participant VFD → VFd`,
        'Authoritative ledger updated',
      ],
    })
  }

  newState = addTimelineEvents(newState, events)

  newState = addEventLogEntries(newState, [`✓ M4 REACHED: ${vendor.name} fix ready`])
  newState = incrementXPosition(newState)

  return newState
}

export function handleNotifyFixDeployed(state: DemoState, vendorId: string): DemoState {
  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  const vendor = getParticipant(state, vendorId)
  const finder = getParticipant(state, 'finder')
  const caseactor = getParticipant(state, 'caseactor')
  if (!vendor) return state

  let newState = state

  // VFD destination computed from the protocol artifact (fix_is_deployed: VFd → VFD).
  const nextVfdState = requireNextState('vfd', vendor.vfdState, 'fix_is_deployed')

  newState = updateParticipant(newState, vendorId, { vfdState: nextVfdState })
  newState = setPhase(newState, 'fix-deployed')

  const events = []
  let timestampOffset = 0

  // Decision node in vendor's lane
  events.push({
    id: eventId,
    actor: vendor.name,
    participantId: vendorId,
    label: 'Notify Fix Deployed',
    x: nextX,
    lane: vendor.laneIndex,
    type: 'decision' as const,
    timestamp: now,
    consequences: [
      `${vendor.name} VFD state: VFd → VFD`,
      '✓ M5 REACHED: Fix deployed',
      'Fix is now available to users',
    ],
  })

  timestampOffset++

  // Consequence node in Finder lane
  if (finder && !finder.hasClosed) {
    events.push({
      id: `${eventId}-finder-consequence`,
      actor: 'Finder',
      participantId: 'finder',
      label: 'Fix Deployed',
      x: nextX,
      lane: finder.laneIndex,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + timestampOffset,
      consequences: [
        'Finder notified: Fix is deployed',
        `${vendor.name} VFD → VFD`,
        'Users can now apply the fix',
      ],
    })
    timestampOffset++
  }

  // Consequence nodes in other vendor lanes
  const otherVendors = getActiveVendors(newState).filter(v => v.id !== vendorId)

  otherVendors.forEach(otherVendor => {
    events.push({
      id: `${eventId}-${otherVendor.id}-consequence`,
      actor: otherVendor.name,
      participantId: otherVendor.id,
      label: `${vendor.name} Fix Deployed`,
      x: nextX,
      lane: otherVendor.laneIndex,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + timestampOffset,
      consequences: [
        `${otherVendor.name} notified: Fix is deployed`,
        `${vendor.name} VFD → VFD`,
        'Other vendor has deployed fix',
      ],
    })
    timestampOffset++
  })

  // Consequence node in CaseActor lane
  if (caseactor) {
    events.push({
      id: `${eventId}-case-consequence`,
      actor: 'CaseActor',
      participantId: 'caseactor',
      label: 'M5 Tracked',
      x: nextX,
      lane: caseactor.laneIndex,
      type: 'consequence' as const,
      timestamp: now + timestampOffset,
      causedBy: eventId,
      consequences: [
        '✓ M5 REACHED: Fix deployed',
        `${vendor.name} participant VFD → VFD`,
        'Authoritative ledger updated',
      ],
    })
  }

  newState = addTimelineEvents(newState, events)

  newState = addEventLogEntries(newState, [`✓ M5 REACHED: ${vendor.name} fix deployed`])
  newState = incrementXPosition(newState)

  return newState
}

export function handleVendorNotifyPublished(state: DemoState, vendorId: string): DemoState {
  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  const vendor = getParticipant(state, vendorId)
  const finder = getParticipant(state, 'finder')
  const caseactor = getParticipant(state, 'caseactor')
  if (!vendor) return state

  let newState = state

  newState = updateParticipant(newState, vendorId, { hasPublished: true })
  newState = setPhase(newState, 'vendor-published')

  // Determine new PXA state. Publication makes the public aware; the destination
  // (Pxa/PXa/PxA/PXA depending on the X/A bits already set) is computed from the
  // protocol artifact (pxa machine, `public_becomes_aware`). The publish action is
  // only offered while not already public, so this transition is always legal.
  const currentPxa = state.pxaState
  const newPxa = requireNextState('pxa', currentPxa, 'public_becomes_aware')

  newState = setPxaState(newState, newPxa)

  // Per Vultron protocol (transitions.md:291-293): when the vuln becomes public,
  // the embargo's fate depends on its state:
  // - Active/Revise embargoes TERMINATE → EXITED (em `terminate`).
  // - A merely PROPOSED embargo was never active, so there is nothing to
  //   terminate; publication implicitly REJECTS the pending proposal → NONE
  //   (em `reject`, the machine's only PROPOSED→NONE path — NOT `terminate`).
  // Both destinations are computed from the protocol artifact.
  const hadActiveEmbargo = state.emState === 'ACTIVE' || state.emState === 'REVISE'
  const hadProposedEmbargo = state.emState === 'PROPOSED'

  if (hadActiveEmbargo) {
    newState = { ...newState, emState: requireNextState('em', state.emState, 'terminate') }
  } else if (hadProposedEmbargo) {
    newState = { ...newState, emState: requireNextState('em', state.emState, 'reject') }
  }

  const events = []
  let timestampOffset = 0

  // Decision node in vendor's lane
  events.push({
    id: eventId,
    actor: vendor.name,
    participantId: vendorId,
    label: 'Notify Published',
    x: nextX,
    lane: vendor.laneIndex,
    type: 'decision' as const,
    timestamp: now,
    consequences: [
      `${vendor.name} publishes vulnerability details`,
      `Case PXA state: ${currentPxa} → ${newPxa}`,
      'Public becomes aware (P)',
      ...(hadActiveEmbargo ? ['Embargo TERMINATED (public awareness)'] : []),
      ...(hadProposedEmbargo ? ['Embargo proposal invalidated (public awareness)'] : []),
      '✓ M6 REACHED: Public disclosure',
    ],
  })

  timestampOffset++

  // Consequence node in Finder lane
  if (finder && !finder.hasClosed) {
    events.push({
      id: `${eventId}-finder-consequence`,
      actor: 'Finder',
      participantId: 'finder',
      label: 'Publication Noted',
      x: nextX,
      lane: finder.laneIndex,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + timestampOffset,
      consequences: [
        'Finder notified: Vulnerability published',
        `Case PXA state: ${newPxa}`,
        'Public disclosure (P) is now active',
        ...(hadActiveEmbargo ? ['Embargo TERMINATED'] : []),
        ...(hadProposedEmbargo ? ['Embargo proposal invalidated'] : []),
      ],
    })
    timestampOffset++
  }

  // Consequence nodes in other vendor lanes
  const otherVendors = getActiveVendors(newState).filter(v => v.id !== vendorId)

  otherVendors.forEach(otherVendor => {
    events.push({
      id: `${eventId}-${otherVendor.id}-consequence`,
      actor: otherVendor.name,
      participantId: otherVendor.id,
      label: `${vendor.name} Published`,
      x: nextX,
      lane: otherVendor.laneIndex,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + timestampOffset,
      consequences: [
        `${otherVendor.name} notified: Published`,
        `Case PXA state: ${newPxa}`,
        'Public disclosure (P) is now active',
        ...(hadActiveEmbargo ? ['Embargo TERMINATED'] : []),
        ...(hadProposedEmbargo ? ['Embargo proposal invalidated'] : []),
      ],
    })
    timestampOffset++
  })

  // Consequence node in CaseActor lane
  if (caseactor) {
    events.push({
      id: `${eventId}-case-consequence`,
      actor: 'CaseActor',
      participantId: 'caseactor',
      label: 'Publication Tracked',
      x: nextX,
      lane: caseactor.laneIndex,
      type: 'consequence' as const,
      timestamp: now + timestampOffset,
      causedBy: eventId,
      consequences: [
        '✓ M6 REACHED: Public disclosure',
        `Case PXA state: ${newPxa}`,
        ...(hadActiveEmbargo ? ['Embargo TERMINATED (EM → EXITED)'] : []),
        ...(hadProposedEmbargo ? ['Embargo proposal invalidated (EM → NONE)'] : []),
        'Authoritative ledger updated',
        'All participants notified',
      ],
    })
  }

  newState = addTimelineEvents(newState, events)

  newState = addEventLogEntries(newState, [`${vendor.name} published vulnerability (PXA → ${newPxa})`])
  newState = incrementXPosition(newState)

  return newState
}

export function handleVendorReplyNote(state: DemoState, vendorId: string): DemoState {
  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  const vendor = getParticipant(state, vendorId)
  const finder = getParticipant(state, 'finder')
  const caseactor = getParticipant(state, 'caseactor')
  if (!vendor) return state

  let newState = state

  // Mark this vendor as having replied to the current note
  // Per Vultron protocol: each vendor can independently reply to notes
  newState = updateParticipant(newState, vendorId, { hasRepliedToCurrentNote: true })

  // Only this vendor is marked as having replied; the case-level
  // hasPendingFinderNote flag stays true so the other participants keep their
  // reply option until they each reply (or the Finder asks a new question).
  // Phase is intentionally left unchanged.

  const events = []
  let timestampOffset = 0

  // Decision node in replying vendor's lane
  events.push({
    id: eventId,
    actor: vendor.name,
    participantId: vendorId,
    label: 'Reply to Question',
    x: nextX,
    lane: vendor.laneIndex,
    type: 'decision' as const,
    timestamp: now,
    consequences: [
      'Note created: "Vendor Response"',
      'Content: "Yes, disable the network stack component"',
      'inReplyTo: previous note',
      'Add(Note, target=Case) activity created',
      'Activity sent via Vendor\'s outbox',
      'Triggers delivery to participants',
    ],
  })

  timestampOffset++

  // Consequence node in Finder lane
  if (finder && !finder.hasClosed) {
    events.push({
      id: `${eventId}-finder-consequence`,
      actor: 'Finder',
      participantId: 'finder',
      label: 'Reply Received',
      x: nextX,
      lane: finder.laneIndex,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + timestampOffset,
      consequences: [
        'Add(Note) received in inbox',
        'Reply delivered to Finder\'s DataLayer',
        'Finder can now see workaround',
        '✓ M3 REACHED: Notes exchanged',
      ],
    })
    timestampOffset++
  }

  // Consequence nodes in other vendor lanes (not the replying vendor).
  // (This fork drops the obsolete `!== 'DECLINED'` filter — see CLAUDE.md §9.)
  const otherVendors = getActiveVendors(newState).filter(v => v.id !== vendorId)

  otherVendors.forEach(otherVendor => {
    events.push({
      id: `${eventId}-${otherVendor.id}-consequence`,
      actor: otherVendor.name,
      participantId: otherVendor.id,
      label: 'Reply Received',
      x: nextX,
      lane: otherVendor.laneIndex,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + timestampOffset,
      consequences: [
        `${vendor.name} replied to question`,
        `Reply delivered to ${otherVendor.name}'s DataLayer`,
        'Can see vendor response',
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
      label: 'Reply Tracked',
      x: nextX,
      lane: caseactor.laneIndex,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + timestampOffset,
      consequences: [
        'Reply note tracked by Case Actor',
        'Note thread updated in case history',
        'Authoritative ledger updated',
      ],
    })
  }

  newState = addTimelineEvents(newState, events)

  newState = addEventLogEntries(newState, [`${vendor.name} replied to question`])
  newState = incrementXPosition(newState)

  return newState
}

export function handleVendorCloseCase(state: DemoState, vendorId: string): DemoState {
  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  const vendor = getParticipant(state, vendorId)
  const finder = getParticipant(state, 'finder')
  const caseactor = getParticipant(state, 'caseactor')
  if (!vendor) return state

  let newState = state

  // RM destination computed from the protocol artifact. `close` is legal from
  // ACCEPTED, INVALID, and DEFERRED (all → CLOSED); the demo surfaces the close
  // action from each of those. `hasClosed` is a demo-only flag with no machine slot.
  const nextRmState = requireNextState('rm', vendor.rmState, 'close')

  newState = updateParticipant(newState, vendorId, { rmState: nextRmState, hasClosed: true })
  // Don't change phase - in multi-vendor scenarios, one vendor closing doesn't affect others
  // Per Vultron protocol: RM state (including CLOSED) is participant-specific
  // The case continues as long as other participants are active

  const events = []
  let timestampOffset = 0

  // Decision node in closing vendor's lane
  events.push({
    id: eventId,
    actor: vendor.name,
    participantId: vendorId,
    label: 'Close Case',
    x: nextX,
    lane: vendor.laneIndex,
    type: 'decision' as const,
    timestamp: now,
    consequences: [
      `${vendor.name} RM state: → CLOSED`,
      `${vendor.name} leaves the case (ActivityPub: Leave)`,
      `No further actions available for ${vendor.name}`,
      'Other participants can still continue',
    ],
  })

  timestampOffset++

  // Consequence node in Finder lane
  if (finder && !finder.hasClosed) {
    events.push({
      id: `${eventId}-finder-consequence`,
      actor: 'Finder',
      participantId: 'finder',
      label: `${vendor.name} Closed`,
      x: nextX,
      lane: finder.laneIndex,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + timestampOffset,
      consequences: [
        `Finder notified: ${vendor.name} closed`,
        `${vendor.name} participant RM → CLOSED`,
        'Finder can still continue work',
      ],
    })
    timestampOffset++
  }

  // Consequence nodes in other vendor lanes (not the closing vendor).
  // (This fork drops the obsolete `!== 'DECLINED'` filter — see CLAUDE.md §9.)
  const otherVendors = getActiveVendors(newState).filter(v => v.id !== vendorId)

  otherVendors.forEach(otherVendor => {
    events.push({
      id: `${eventId}-${otherVendor.id}-consequence`,
      actor: otherVendor.name,
      participantId: otherVendor.id,
      label: `${vendor.name} Closed`,
      x: nextX,
      lane: otherVendor.laneIndex,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + timestampOffset,
      consequences: [
        `${vendor.name} closed their participation`,
        `${vendor.name} participant RM → CLOSED`,
        `${otherVendor.name} can still continue work`,
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
      label: `${vendor.name} Closed`,
      x: nextX,
      lane: caseactor.laneIndex,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + timestampOffset,
      consequences: [
        `${vendor.name} participant RM → CLOSED`,
        'Leave activity tracked',
        'Authoritative ledger updated',
        'Case remains open for other participants',
      ],
    })
  }

  newState = addTimelineEvents(newState, events)

  newState = addEventLogEntries(newState, [`${vendor.name} closed their participation in the case`])
  newState = incrementXPosition(newState)

  return newState
}

export function handleVendorProposeRevision(state: DemoState, vendorId: string): DemoState {
  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  const vendor = getParticipant(state, vendorId)
  if (!vendor) return state

  const finder = getParticipant(state, 'finder')
  const caseactor = getParticipant(state, 'caseactor')

  let newState = state

  // Per Vultron protocol: A → pR (Active → propose → Revise)
  // EM destination computed from the protocol artifact (propose: ACTIVE → REVISE).
  newState = setEmState(newState, requireNextState('em', state.emState, 'propose'))
  newState = { ...newState, embargoProposerId: vendorId }  // Track who proposed this revision

  // Reset the CaseActor's response flag so they can accept/reject this new revision
  // (mirrors the per-participant resets below). UI-only flag — see actionFilters.
  newState = updateParticipant(newState, 'caseactor', { embargoAccepted: false })

  const events = []
  let timestampOffset = 0

  // Decision node in Vendor's lane
  events.push({
    id: eventId,
    actor: vendor.name,
    participantId: vendorId,
    label: 'Propose Embargo Revision',
    x: nextX,
    lane: vendor.laneIndex,
    type: 'decision' as const,
    timestamp: now,
    consequences: [
      `${vendor.name} proposed embargo revision`,
      'EmProposeEmbargoActivity created (revision)',
      'Existing embargo remains active',
      'EM state → REVISE',
    ],
  })
  timestampOffset++

  // Consequence node in Finder's lane (Finder is always involved in embargo negotiation)
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
        `Finder sees ${vendor.name}'s proposed revision`,
        'Current embargo still active',
      ],
    })
    timestampOffset++
  }

  // Consequence nodes for ALL other vendors (including those who previously rejected)
  // Per Vultron protocol: embargo revision is a new proposal that ALL participants can accept/reject
  const otherVendors = getVendors(newState).filter((v) => v.id !== vendorId && v.visible && !v.hasClosed)
  for (const otherVendor of otherVendors) {
    const wasParticipating = otherVendor.embargoAccepted

    // Reset embargoAccepted for ALL vendors - they need to accept the revision
    // Only set embargoProposedToParticipant for vendors who were NOT participating
    newState = updateParticipant(newState, otherVendor.id, {
      embargoAccepted: false,
      embargoProposedToParticipant: !wasParticipating
    })

    events.push({
      id: `${eventId}-${otherVendor.id}-consequence`,
      actor: otherVendor.name,
      participantId: otherVendor.id,
      label: 'Revision Proposal Received',
      x: nextX,
      lane: otherVendor.laneIndex,
      type: 'consequence' as const,
      timestamp: now + timestampOffset,
      causedBy: eventId,
      enablesNext: true,
      consequences: [
        'EmProposeEmbargoActivity received (revision)',
        `${otherVendor.name} sees revision proposal`,
        'Current embargo still active',
      ],
    })
    timestampOffset++
  }

  // Proposing vendor implicitly accepts their own proposal
  newState = updateParticipant(newState, vendorId, {
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
        `CaseActor sees ${vendor.name}'s proposed revision`,
      ],
    })
  }

  newState = addTimelineEvents(newState, events)
  newState = addEventLogEntries(newState, [`${vendor.name} proposed embargo revision`])
  newState = incrementXPosition(newState)

  return newState
}

export function handleVendorAcceptRevision(state: DemoState, vendorId: string): DemoState {
  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  const vendor = getParticipant(state, vendorId)
  if (!vendor) return state

  const finder = getParticipant(state, 'finder')

  let newState = state

  // Mark vendor as having accepted the embargo (this applies even if they rejected before)
  newState = updateParticipant(newState, vendorId, {
    embargoAccepted: true,
    embargoProposedToParticipant: false  // Clear the proposal flag
  })

  // Per Vultron protocol: R → aA (Revise → accept → Active)
  // But ONLY if ALL participants have now accepted
  const allParticipantsAccepted = (finder?.embargoAccepted || false) &&
    getActiveVendors(newState).every((v) => v.embargoAccepted)

  if (allParticipantsAccepted) {
    // EM destination computed from the protocol artifact (accept: REVISE → ACTIVE).
    newState = setEmState(newState, requireNextState('em', state.emState, 'accept'))
    newState = { ...newState, embargoProposerId: undefined }  // Clear proposer when revision is accepted
  }
  // Otherwise, stay in REVISE state

  const caseactor = getParticipant(newState, 'caseactor')
  const events = []
  let timestampOffset = 0

  // Decision node in vendor's lane
  events.push({
    id: eventId,
    actor: vendor.name,
    participantId: vendorId,
    label: 'Accept Revision',
    x: nextX,
    lane: vendor.laneIndex,
    type: 'decision' as const,
    timestamp: now,
    consequences: [
      `${vendor.name} accepted embargo revision`,
      'EmAcceptEmbargoActivity created',
      allParticipantsAccepted ? 'Revised embargo terms now active' : 'Awaiting other participants',
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
      label: allParticipantsAccepted ? 'Revision Accepted' : 'Vendor Accepted',
      x: nextX,
      lane: finder.laneIndex,
      type: 'consequence' as const,
      timestamp: now + timestampOffset,
      causedBy: eventId,
      enablesNext: true,
      consequences: [
        `${vendor.name} accepted revision`,
        allParticipantsAccepted ? 'All participants accepted - EM → ACTIVE' : 'Awaiting other participants',
      ],
    })
    timestampOffset++
  }

  // Consequence nodes for other vendors
  const otherVendors = getVendors(newState).filter((v) => v.id !== vendorId && v.visible && !v.hasClosed)
  for (const otherVendor of otherVendors) {
    events.push({
      id: `${eventId}-${otherVendor.id}-consequence`,
      actor: otherVendor.name,
      participantId: otherVendor.id,
      label: allParticipantsAccepted ? 'Revision Accepted' : `${vendor.name} Accepted`,
      x: nextX,
      lane: otherVendor.laneIndex,
      type: 'consequence' as const,
      timestamp: now + timestampOffset,
      causedBy: eventId,
      enablesNext: true,
      consequences: [
        `${vendor.name} accepted revision`,
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
      label: allParticipantsAccepted ? 'Revision Accepted' : `${vendor.name} Accepted`,
      x: nextX,
      lane: caseactor.laneIndex,
      type: 'consequence' as const,
      timestamp: now + timestampOffset,
      causedBy: eventId,
      consequences: [
        `${vendor.name} accepted revision`,
        allParticipantsAccepted ? 'All participants accepted - EM → ACTIVE' : 'Awaiting other participants',
        'Authoritative ledger updated',
      ],
    })
  }

  newState = addTimelineEvents(newState, events)
  newState = addEventLogEntries(newState, [`${vendor.name} accepted embargo revision`])
  newState = incrementXPosition(newState)

  return newState
}

export function handleVendorRejectRevision(state: DemoState, vendorId: string): DemoState {
  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  const vendor = getParticipant(state, vendorId)
  if (!vendor) return state

  const finder = getParticipant(state, 'finder')
  const caseactor = getParticipant(state, 'caseactor')

  let newState = state

  // Per Vultron protocol: R → rA (Revise → reject → Active)
  // Revision rejected - restore original embargo state.
  // EM destination computed from the protocol artifact (reject: REVISE → ACTIVE).
  newState = setEmState(newState, requireNextState('em', state.emState, 'reject'))
  newState = { ...newState, embargoProposerId: undefined }  // Clear proposer when revision is rejected

  // Restore embargoAccepted for Finder (was participating)
  if (finder) {
    newState = updateParticipant(newState, 'finder', {
      embargoAccepted: true
    })
  }

  // Restore embargoAccepted for vendors who were participating
  // Clear embargoProposedToParticipant for vendors who were excluded (revision opportunity passed)
  for (const otherVendor of getVendors(newState).filter((v) => v.visible && !v.hasClosed)) {
    if (otherVendor.embargoProposedToParticipant) {
      // Was excluded, offered revision, rejected/didn't accept - clear the flag
      newState = updateParticipant(newState, otherVendor.id, {
        embargoProposedToParticipant: false
      })
    } else {
      // Was participating - restore embargoAccepted
      newState = updateParticipant(newState, otherVendor.id, {
        embargoAccepted: true
      })
    }
  }

  const events = []
  let timestampOffset = 0

  // Decision node in vendor's lane
  events.push({
    id: eventId,
    actor: vendor.name,
    participantId: vendorId,
    label: 'Reject Revision',
    x: nextX,
    lane: vendor.laneIndex,
    type: 'decision' as const,
    timestamp: now,
    consequences: [
      `${vendor.name} rejected embargo revision`,
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
        `${vendor.name} rejected revision`,
        'Original embargo terms remain',
      ],
    })
    timestampOffset++
  }

  // Consequence nodes for other vendors
  const otherVendors = getVendors(newState).filter((v) => v.id !== vendorId && v.visible && !v.hasClosed)
  for (const otherVendor of otherVendors) {
    events.push({
      id: `${eventId}-${otherVendor.id}-consequence`,
      actor: otherVendor.name,
      participantId: otherVendor.id,
      label: 'Revision Rejected',
      x: nextX,
      lane: otherVendor.laneIndex,
      type: 'consequence' as const,
      timestamp: now + timestampOffset,
      causedBy: eventId,
      enablesNext: true,
      consequences: [
        `${vendor.name} rejected revision`,
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
        `${vendor.name} rejected revision`,
        'Original embargo terms remain',
      ],
    })
  }

  newState = addTimelineEvents(newState, events)
  newState = addEventLogEntries(newState, [`${vendor.name} rejected embargo revision - original terms remain`])
  newState = incrementXPosition(newState)

  return newState
}
