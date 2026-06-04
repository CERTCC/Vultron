/**
 * Vendor action handlers (works for vendor-1, vendor-2, etc.)
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

export function handleValidateReport(state: DemoState, vendorId: string): DemoState {
  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  const vendor = getParticipant(state, vendorId)
  if (!vendor) return state

  let newState = state

  newState = updateParticipant(newState, vendorId, { rmState: 'VALID' })
  newState = setPhase(newState, 'report-validated')

  newState = addTimelineEvents(newState, [
    {
      id: eventId,
      actor: vendor.name,
      participantId: vendorId,
      label: 'Validate Report',
      x: nextX,
      lane: vendor.laneIndex,
      type: 'decision',
      timestamp: now,
      consequences: [
        'Accept(Offer) activity created',
        'ValidateReportReceivedUseCase executes',
        `${vendor.name} RM state: RECEIVED → VALID`,
        'Report deemed legitimate',
        'Can proceed with case work',
      ],
    },
    {
      id: `${eventId}-finder-consequence`,
      actor: 'Finder',
      participantId: 'finder',
      label: 'Validation Noted',
      x: nextX,
      lane: 0,
      type: 'consequence',
      timestamp: now + 1,
      causedBy: eventId,
      consequences: [
        'Accept activity received',
        `${vendor.name} has validated the report`,
        'Case work can proceed',
      ],
    },
    {
      id: `${eventId}-case-consequence`,
      actor: 'CaseActor',
      participantId: 'caseactor',
      label: 'Validation Tracked',
      x: nextX,
      lane: 2,
      type: 'consequence',
      timestamp: now + 2,
      causedBy: eventId,
      consequences: [
        `${vendor.name} participant RM → VALID`,
        'Authoritative ledger updated',
      ],
    },
  ])

  newState = addEventLogEntries(newState, [`${vendor.name} validated the report (RM → VALID)`])
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

  newState = updateParticipant(newState, vendorId, { rmState: 'INVALID' })
  newState = setPhase(newState, 'report-invalidated')

  newState = addTimelineEvents(newState, [
    {
      id: eventId,
      actor: vendor.name,
      participantId: vendorId,
      label: 'Invalidate Report',
      x: nextX,
      lane: vendor.laneIndex,
      type: 'decision',
      timestamp: now,
      consequences: [
        'Reject(Offer) activity created',
        `${vendor.name} RM state: RECEIVED → INVALID`,
        'Report deemed invalid',
        'Case held until reconsideration or closure',
      ],
    },
  ])

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
  if (!vendor) return state

  const bothAccepted = finder?.embargoAccepted

  let newState = state

  newState = updateParticipant(newState, vendorId, { embargoAccepted: true })

  if (bothAccepted) {
    newState = { ...newState, emState: 'ACTIVE', phase: 'embargo-accepted' }
  }

  const events = [
    {
      id: eventId,
      actor: vendor.name,
      participantId: vendorId,
      label: 'Accept Embargo',
      x: nextX,
      lane: vendor.laneIndex,
      type: 'decision' as const,
      timestamp: now,
      consequences: [
        'EmAcceptEmbargoActivity created',
        `${vendor.name} accepts 90-day embargo`,
        bothAccepted ? 'Both parties accepted - embargo is now ACTIVE' : 'Awaiting Finder acceptance',
      ],
    },
    // Consequence node in CaseActor lane - always created
    {
      id: `${eventId}-caseactor-consequence`,
      actor: 'CaseActor',
      participantId: 'caseactor',
      label: bothAccepted ? 'M1 REACHED' : `${vendor.name} Accepted`,
      x: nextX,
      lane: 2,
      type: 'consequence',
      causedBy: eventId,
      timestamp: now + 1,
      enablesNext: bothAccepted,
      consequences: bothAccepted ? [
        '✓ M1 REACHED: Case active',
        'Embargo: ACTIVE',
        'EmAcceptEmbargoActivity received from both',
        'ActivateEmbargoActivity processed',
        'Authoritative ledger updated',
      ] : [
        `${vendor.name} EmAcceptEmbargoActivity received`,
        'Awaiting Finder acceptance',
        'EM state remains PROPOSED',
      ],
    },
    // Consequence node in Finder lane - always created
    {
      id: `${eventId}-finder-consequence`,
      actor: 'Finder',
      participantId: 'finder',
      label: bothAccepted ? 'Embargo Active' : `${vendor.name} Accepted`,
      x: nextX,
      lane: 0,
      type: 'consequence',
      causedBy: eventId,
      timestamp: now + 2,
      consequences: bothAccepted ? [
        'AnnounceEmbargoActivity received',
        'Embargo is now ACTIVE',
        'Coordinated disclosure begins',
      ] : [
        `Notified: ${vendor.name} accepted embargo`,
        'Awaiting own acceptance decision',
        'EM state remains PROPOSED',
      ],
    },
  ]

  newState = addTimelineEvents(newState, events)
  newState = addEventLogEntries(newState, [
    `${vendor.name} accepted embargo`,
    ...(bothAccepted ? ['✓ M1 REACHED: Case active with 3 participants, embargo active'] : []),
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

  let newState = state

  newState = { ...newState, emState: 'NONE', phase: 'embargo-rejected' }

  newState = addTimelineEvents(newState, [
    {
      id: eventId,
      actor: vendor.name,
      participantId: vendorId,
      label: 'Reject Embargo',
      x: nextX,
      lane: vendor.laneIndex,
      type: 'decision',
      timestamp: now,
      consequences: [
        'EmRejectEmbargoActivity created',
        `${vendor.name} rejects embargo proposal`,
        'Case proceeds without embargo',
      ],
    },
  ])

  newState = addEventLogEntries(newState, [`${vendor.name} rejected embargo`])
  newState = incrementXPosition(newState)

  return newState
}

export function handleNotifyFixReady(state: DemoState, vendorId: string): DemoState {
  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  const vendor = getParticipant(state, vendorId)
  if (!vendor) return state

  let newState = state

  newState = updateParticipant(newState, vendorId, { vfdState: 'VFd' })
  newState = setPhase(newState, 'fix-ready')

  newState = addTimelineEvents(newState, [
    {
      id: eventId,
      actor: vendor.name,
      participantId: vendorId,
      label: 'Notify Fix Ready',
      x: nextX,
      lane: vendor.laneIndex,
      type: 'decision',
      timestamp: now,
      consequences: [
        `${vendor.name} VFD state: Vfd → VFd`,
        '✓ M4 REACHED: Fix ready',
        'Fix is ready but not yet deployed',
      ],
    },
    {
      id: `${eventId}-case-consequence`,
      actor: 'CaseActor',
      participantId: 'caseactor',
      label: 'M4 Tracked',
      x: nextX,
      lane: 2,
      type: 'consequence',
      timestamp: now + 1,
      causedBy: eventId,
      consequences: [
        '✓ M4 REACHED: Fix ready',
        `${vendor.name} participant VFD → VFd`,
        'Authoritative ledger updated',
      ],
    },
  ])

  newState = addEventLogEntries(newState, [`✓ M4 REACHED: ${vendor.name} fix ready`])
  newState = incrementXPosition(newState)

  return newState
}

export function handleNotifyFixDeployed(state: DemoState, vendorId: string): DemoState {
  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  const vendor = getParticipant(state, vendorId)
  if (!vendor) return state

  let newState = state

  newState = updateParticipant(newState, vendorId, { vfdState: 'VFD' })
  newState = setPhase(newState, 'fix-deployed')

  newState = addTimelineEvents(newState, [
    {
      id: eventId,
      actor: vendor.name,
      participantId: vendorId,
      label: 'Notify Fix Deployed',
      x: nextX,
      lane: vendor.laneIndex,
      type: 'decision',
      timestamp: now,
      consequences: [
        `${vendor.name} VFD state: VFd → VFD`,
        '✓ M5 REACHED: Fix deployed',
        'Fix is now available to users',
      ],
    },
    {
      id: `${eventId}-case-consequence`,
      actor: 'CaseActor',
      participantId: 'caseactor',
      label: 'M5 Tracked',
      x: nextX,
      lane: 2,
      type: 'consequence',
      timestamp: now + 1,
      causedBy: eventId,
      consequences: [
        '✓ M5 REACHED: Fix deployed',
        `${vendor.name} participant VFD → VFD`,
        'Authoritative ledger updated',
      ],
    },
  ])

  newState = addEventLogEntries(newState, [`✓ M5 REACHED: ${vendor.name} fix deployed`])
  newState = incrementXPosition(newState)

  return newState
}

export function handleVendorNotifyPublished(state: DemoState, vendorId: string): DemoState {
  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  const vendor = getParticipant(state, vendorId)
  if (!vendor) return state

  let newState = state

  newState = updateParticipant(newState, vendorId, { hasPublished: true })
  newState = setPhase(newState, 'vendor-published')

  // Determine new PXA state
  const currentPxa = state.pxaState
  let newPxa = currentPxa
  if (currentPxa === 'pxa') {
    newPxa = 'Pxa'
  } else if (currentPxa === 'pXa') {
    newPxa = 'PXa'
  } else if (currentPxa === 'pxA') {
    newPxa = 'PxA'
  } else if (currentPxa === 'pXA') {
    newPxa = 'PXA'
  }

  newState = setPxaState(newState, newPxa)

  newState = addTimelineEvents(newState, [
    {
      id: eventId,
      actor: vendor.name,
      participantId: vendorId,
      label: 'Notify Published',
      x: nextX,
      lane: vendor.laneIndex,
      type: 'decision',
      timestamp: now,
      consequences: [
        `${vendor.name} publishes vulnerability details`,
        `Case PXA state: ${currentPxa} → ${newPxa}`,
        'Public becomes aware (P)',
        '✓ M6 REACHED: Public disclosure',
      ],
    },
    {
      id: `${eventId}-case-consequence`,
      actor: 'CaseActor',
      participantId: 'caseactor',
      label: 'Publication Tracked',
      x: nextX,
      lane: 2,
      type: 'consequence',
      timestamp: now + 1,
      causedBy: eventId,
      consequences: [
        '✓ M6 REACHED: Public disclosure',
        `Case PXA state: ${newPxa}`,
        'Authoritative ledger updated',
        'All participants notified',
      ],
    },
  ])

  newState = addEventLogEntries(newState, [`${vendor.name} published vulnerability (PXA → ${newPxa})`])
  newState = incrementXPosition(newState)

  return newState
}

export function handleVendorReplyNote(state: DemoState, vendorId: string): DemoState {
  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  const vendor = getParticipant(state, vendorId)
  if (!vendor) return state

  let newState = state

  newState = setPhase(newState, 'vendor-replied')

  newState = addTimelineEvents(newState, [
    {
      id: eventId,
      actor: vendor.name,
      participantId: vendorId,
      label: 'Reply to Question',
      x: nextX,
      lane: vendor.laneIndex,
      type: 'decision',
      timestamp: now,
      consequences: [
        'Note added to case',
        `${vendor.name} replied to Finder's question`,
        'E.g., "Workaround: disable feature X until patch is available"',
      ],
    },
  ])

  newState = addEventLogEntries(newState, [`${vendor.name} replied to question`])
  newState = incrementXPosition(newState)

  return newState
}

export function handleVendorCloseCase(state: DemoState, vendorId: string): DemoState {
  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  const vendor = getParticipant(state, vendorId)
  if (!vendor) return state

  let newState = state

  newState = updateParticipant(newState, vendorId, { rmState: 'CLOSED', hasClosed: true })
  newState = setPhase(newState, 'vendor-closed')

  newState = addTimelineEvents(newState, [
    {
      id: eventId,
      actor: vendor.name,
      participantId: vendorId,
      label: 'Close Case',
      x: nextX,
      lane: vendor.laneIndex,
      type: 'decision',
      timestamp: now,
      consequences: [
        `${vendor.name} RM state: → CLOSED`,
        `${vendor.name} leaves the case (ActivityPub: Leave)`,
        `No further actions available for ${vendor.name}`,
        'Other participants can still continue',
      ],
    },
  ])

  newState = addEventLogEntries(newState, [`${vendor.name} closed their participation in the case`])
  newState = incrementXPosition(newState)

  return newState
}
