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
import { getParticipant, getActiveParticipants } from '../state/participantHelpers'

export function handleValidateReport(state: DemoState, vendorId: string): DemoState {
  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  const vendor = getParticipant(state, vendorId)
  if (!vendor) return state

  let newState = state

  newState = updateParticipant(newState, vendorId, { rmState: 'VALID' })
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

export function handleInvalidateReport(state: DemoState, vendorId: string): DemoState {
  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  const vendor = getParticipant(state, vendorId)
  if (!vendor) return state

  let newState = state

  newState = updateParticipant(newState, vendorId, { rmState: 'INVALID' })
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
      lane: caseactor?.laneIndex ?? 2,
      type: 'consequence' as const,
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
      lane: finder?.laneIndex ?? 0,
      type: 'consequence' as const,
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

  const finder = getParticipant(state, 'finder')
  const vendor1 = getParticipant(state, 'vendor-1')
  const vendor2 = getParticipant(state, 'vendor-2')
  const caseactor = getParticipant(state, 'caseactor')

  let newState = state

  newState = { ...newState, emState: 'NONE', phase: 'embargo-rejected' }

  const events = []
  let timestampOffset = 0

  // Decision node in rejecting vendor's lane
  events.push({
    id: eventId,
    actor: vendor.name,
    participantId: vendorId,
    label: 'Reject Embargo',
    x: nextX,
    lane: vendor.laneIndex,
    type: 'decision' as const,
    timestamp: now,
    consequences: [
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

  // Consequence node in Finder's lane
  if (finder) {
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
      consequences: [
        `${vendor.name} rejected embargo`,
        'EM state → NONE',
        'Awaiting reproposal or continuation',
      ],
    })
    timestampOffset++
  }

  // Consequence nodes in other vendor lanes (not the rejecting vendor)
  if (vendor1 && vendor1.visible && !vendor1.hasClosed && vendorId !== 'vendor-1') {
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
        `${vendor.name} rejected embargo`,
        'EM state → NONE',
        'Awaiting reproposal or continuation',
      ],
    })
    timestampOffset++
  }

  if (vendor2 && vendor2.visible && !vendor2.hasClosed && vendorId !== 'vendor-2') {
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
        `${vendor.name} rejected embargo`,
        'EM state → NONE',
        'Awaiting reproposal or continuation',
      ],
    })
  }

  newState = addTimelineEvents(newState, events)

  newState = addEventLogEntries(newState, [`${vendor.name} rejected embargo proposal`])
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

  // Get other vendors to notify them
  const vendor1 = getParticipant(state, 'vendor-1')
  const vendor2 = getParticipant(state, 'vendor-2')

  let newState = state

  newState = updateParticipant(newState, vendorId, { vfdState: 'VFd' })
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

  // Consequence node in Finder lane
  if (finder) {
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
  if (vendor1 && vendor1.visible && !vendor1.hasClosed && vendorId !== 'vendor-1') {
    events.push({
      id: `${eventId}-vendor1-consequence`,
      actor: 'Vendor',
      participantId: 'vendor-1',
      label: `${vendor.name} Fix Ready`,
      x: nextX,
      lane: vendor1.laneIndex,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + timestampOffset,
      consequences: [
        `${vendor.name} notified: Fix is ready`,
        `${vendor.name} VFD → VFd`,
        'Other vendor has completed fix',
      ],
    })
    timestampOffset++
  }

  if (vendor2 && vendor2.visible && !vendor2.hasClosed && vendorId !== 'vendor-2') {
    events.push({
      id: `${eventId}-vendor2-consequence`,
      actor: 'Vendor 2',
      participantId: 'vendor-2',
      label: `${vendor.name} Fix Ready`,
      x: nextX,
      lane: vendor2.laneIndex,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + timestampOffset,
      consequences: [
        `${vendor.name} notified: Fix is ready`,
        `${vendor.name} VFD → VFd`,
        'Other vendor has completed fix',
      ],
    })
    timestampOffset++
  }

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
  const vendor1 = getParticipant(state, 'vendor-1')
  const vendor2 = getParticipant(state, 'vendor-2')
  if (!vendor) return state

  let newState = state

  newState = updateParticipant(newState, vendorId, { vfdState: 'VFD' })
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
  if (finder) {
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
  if (vendor1 && vendor1.visible && !vendor1.hasClosed && vendorId !== 'vendor-1') {
    events.push({
      id: `${eventId}-vendor1-consequence`,
      actor: 'Vendor',
      participantId: 'vendor-1',
      label: `${vendor.name} Fix Deployed`,
      x: nextX,
      lane: vendor1.laneIndex,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + timestampOffset,
      consequences: [
        `${vendor.name} notified: Fix is deployed`,
        `${vendor.name} VFD → VFD`,
        'Other vendor has deployed fix',
      ],
    })
    timestampOffset++
  }

  if (vendor2 && vendor2.visible && !vendor2.hasClosed && vendorId !== 'vendor-2') {
    events.push({
      id: `${eventId}-vendor2-consequence`,
      actor: 'Vendor 2',
      participantId: 'vendor-2',
      label: `${vendor.name} Fix Deployed`,
      x: nextX,
      lane: vendor2.laneIndex,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + timestampOffset,
      consequences: [
        `${vendor.name} notified: Fix is deployed`,
        `${vendor.name} VFD → VFD`,
        'Other vendor has deployed fix',
      ],
    })
    timestampOffset++
  }

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
  const vendor1 = getParticipant(state, 'vendor-1')
  const vendor2 = getParticipant(state, 'vendor-2')
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
      '✓ M6 REACHED: Public disclosure',
    ],
  })

  timestampOffset++

  // Consequence node in Finder lane
  if (finder) {
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
      ],
    })
    timestampOffset++
  }

  // Consequence nodes in other vendor lanes
  if (vendor1 && vendor1.visible && !vendor1.hasClosed && vendorId !== 'vendor-1') {
    events.push({
      id: `${eventId}-vendor1-consequence`,
      actor: 'Vendor',
      participantId: 'vendor-1',
      label: `${vendor.name} Published`,
      x: nextX,
      lane: vendor1.laneIndex,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + timestampOffset,
      consequences: [
        `${vendor.name} notified: Published`,
        `Case PXA state: ${newPxa}`,
        'Public disclosure (P) is now active',
      ],
    })
    timestampOffset++
  }

  if (vendor2 && vendor2.visible && !vendor2.hasClosed && vendorId !== 'vendor-2') {
    events.push({
      id: `${eventId}-vendor2-consequence`,
      actor: 'Vendor 2',
      participantId: 'vendor-2',
      label: `${vendor.name} Published`,
      x: nextX,
      lane: vendor2.laneIndex,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + timestampOffset,
      consequences: [
        `${vendor.name} notified: Published`,
        `Case PXA state: ${newPxa}`,
        'Public disclosure (P) is now active',
      ],
    })
    timestampOffset++
  }

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
  const vendor1 = getParticipant(state, 'vendor-1')
  const vendor2 = getParticipant(state, 'vendor-2')
  const caseactor = getParticipant(state, 'caseactor')
  if (!vendor) return state

  let newState = state

  // Mark this vendor as having replied to the current note
  // Per Vultron protocol: each vendor can independently reply to notes
  newState = updateParticipant(newState, vendorId, { hasRepliedToCurrentNote: true })

  // Don't change phase - keep it as 'finder-asked' so other vendors can still reply
  // Phase will change when Finder asks another question or case progresses for other reasons

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
  if (finder) {
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

  // Consequence nodes in other vendor lanes (not the replying vendor)
  if (vendor1 && vendor1.visible && !vendor1.hasClosed && vendor1.rmState !== 'DECLINED' && vendorId !== 'vendor-1') {
    events.push({
      id: `${eventId}-vendor1-consequence`,
      actor: 'Vendor',
      participantId: 'vendor-1',
      label: 'Reply Received',
      x: nextX,
      lane: vendor1.laneIndex,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + timestampOffset,
      consequences: [
        `${vendor.name} replied to question`,
        'Reply delivered to Vendor\'s DataLayer',
        'Can see vendor response',
      ],
    })
    timestampOffset++
  }

  if (vendor2 && vendor2.visible && !vendor2.hasClosed && vendor2.rmState !== 'DECLINED' && vendorId !== 'vendor-2') {
    events.push({
      id: `${eventId}-vendor2-consequence`,
      actor: 'Vendor 2',
      participantId: 'vendor-2',
      label: 'Reply Received',
      x: nextX,
      lane: vendor2.laneIndex,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + timestampOffset,
      consequences: [
        `${vendor.name} replied to question`,
        'Reply delivered to Vendor 2\'s DataLayer',
        'Can see vendor response',
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
  const vendor1 = getParticipant(state, 'vendor-1')
  const vendor2 = getParticipant(state, 'vendor-2')
  const caseactor = getParticipant(state, 'caseactor')
  if (!vendor) return state

  let newState = state

  newState = updateParticipant(newState, vendorId, { rmState: 'CLOSED', hasClosed: true })
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
  if (finder) {
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

  // Consequence nodes in other vendor lanes (not the closing vendor)
  if (vendor1 && vendor1.visible && !vendor1.hasClosed && vendor1.rmState !== 'DECLINED' && vendorId !== 'vendor-1') {
    events.push({
      id: `${eventId}-vendor1-consequence`,
      actor: 'Vendor',
      participantId: 'vendor-1',
      label: `${vendor.name} Closed`,
      x: nextX,
      lane: vendor1.laneIndex,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + timestampOffset,
      consequences: [
        `${vendor.name} closed their participation`,
        `${vendor.name} participant RM → CLOSED`,
        'Vendor can still continue work',
      ],
    })
    timestampOffset++
  }

  if (vendor2 && vendor2.visible && !vendor2.hasClosed && vendor2.rmState !== 'DECLINED' && vendorId !== 'vendor-2') {
    events.push({
      id: `${eventId}-vendor2-consequence`,
      actor: 'Vendor 2',
      participantId: 'vendor-2',
      label: `${vendor.name} Closed`,
      x: nextX,
      lane: vendor2.laneIndex,
      type: 'consequence' as const,
      causedBy: eventId,
      timestamp: now + timestampOffset,
      consequences: [
        `${vendor.name} closed their participation`,
        `${vendor.name} participant RM → CLOSED`,
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
