/**
 * Multi-vendor case-ownership transfer handlers (offer / accept).
 *
 * Ownership transfer is a PROCEDURAL protocol act, not a state-machine transition: it
 * moves the CASE_OWNER role between participants and updates the case's `attributedTo`
 * (specs CM-21-001..010, triggers TRIG-11-001/002, routed via the Case Actor per
 * ADR-0053). It has NO representation in `protocol_states.json` (rm/em/vfd/pxa only),
 * so — per ui/CLAUDE.md §9's declarative-vs-procedural boundary — this is a deliberate
 * demo OVERLAY, mirroring those specs rather than deferring to the artifact. It touches
 * NO machine state (rm/em/vfd/pxa); it only moves the demo's `caseOwnerId` pointer.
 *
 * Scope (Phase 2): vendor→vendor transfer. The "only the current owner may offer" rule
 * enforced in actionFilters is a DEMO CONVENTION for teaching clarity — the protocol
 * code imposes no such owner-authority guard on offering.
 */

import type { DemoState, TimelineEvent } from '../types'
import {
  addTimelineEvents,
  addEventLogEntries,
  incrementXPosition,
} from '../state/stateUpdaters'
import { getParticipant, getActiveParticipants } from '../state/participantHelpers'

/**
 * The current owner offers to transfer case ownership to `targetId`. Records the
 * pending offer (`pendingOwnerOfferTo`) and emits an "Offer Case Ownership" decision
 * node in the offerer's lane with consequence nodes in the other active lanes. No
 * ownership actually moves yet — that happens on accept.
 */
export function handleOfferCaseOwnership(
  state: DemoState,
  offererId: string,
  targetId: string
): DemoState {
  const offerer = getParticipant(state, offererId)
  const target = getParticipant(state, targetId)
  if (!offerer || !target) return state

  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  // Record the pending offer (addressed to the target). Preserved by the
  // addTimelineEvents/... pipeline below, which spreads ...state.
  let newState: DemoState = { ...state, pendingOwnerOfferTo: targetId }

  const events: TimelineEvent[] = []
  let offset = 0

  events.push({
    id: eventId,
    actor: offerer.name,
    participantId: offererId,
    label: 'Offer Case Ownership',
    x: nextX,
    lane: offerer.laneIndex,
    type: 'decision',
    timestamp: now + offset,
    consequences: [
      `${offerer.name} offers to transfer case ownership to ${target.name}`,
      'Offer(VulnerabilityCase) → Case Actor, forwarded to the transferee (ADR-0053)',
      `Awaiting ${target.name}'s acceptance`,
    ],
  })
  offset++

  for (const p of getActiveParticipants(newState).filter((p) => p.id !== offererId)) {
    const bullets =
      p.id === targetId
        ? [`${offerer.name} offered you case ownership`, 'Accept to become the new CASE_OWNER']
        : p.id === 'caseactor'
        ? ['Ownership offer routed through the Case Actor', 'Forwarded to the transferee (ADR-0053)']
        : [`${offerer.name} offered case ownership to ${target.name}`]
    events.push({
      id: `${eventId}-${p.id}-consequence`,
      actor: p.name,
      participantId: p.id,
      label: 'Ownership Offered',
      x: nextX,
      lane: p.laneIndex,
      type: 'consequence',
      causedBy: eventId,
      timestamp: now + offset,
      consequences: bullets,
    })
    offset++
  }

  newState = addTimelineEvents(newState, events)
  newState = addEventLogEntries(newState, [
    `${offerer.name} offered case ownership to ${target.name}`,
  ])
  newState = incrementXPosition(newState)
  return newState
}

/**
 * The participant a transfer was offered to accepts it. Moves `caseOwnerId` to the
 * accepter and clears the pending offer, then emits an "Ownership Accepted" decision
 * node in the new owner's lane. The previous owner keeps all its other roles and
 * remains a participant (CM-21-008/009); the CASE_OWNER badge migrates because the
 * label is derived from `caseOwnerId` at render.
 */
export function handleAcceptCaseOwnership(state: DemoState, accepterId: string): DemoState {
  // Defensive: only the addressed participant may accept.
  if (state.pendingOwnerOfferTo !== accepterId) return state
  const accepter = getParticipant(state, accepterId)
  if (!accepter) return state
  const previousOwnerId = state.caseOwnerId
  const previousOwner = previousOwnerId ? getParticipant(state, previousOwnerId) : undefined

  const nextX = state.nextXPosition
  const eventId = `event-${state.timelineEvents.length + 1}`
  const now = Date.now()

  // Move ownership + clear the pending offer. No machine (rm/em/vfd/pxa) change.
  let newState: DemoState = { ...state, caseOwnerId: accepterId, pendingOwnerOfferTo: undefined }

  const events: TimelineEvent[] = []
  let offset = 0

  events.push({
    id: eventId,
    actor: accepter.name,
    participantId: accepterId,
    label: 'Ownership Accepted',
    x: nextX,
    lane: accepter.laneIndex,
    type: 'decision',
    timestamp: now + offset,
    consequences: [
      `${accepter.name} accepted the transfer and is now the CASE_OWNER`,
      'Accept(Offer(VulnerabilityCase)) → Case Actor (ADR-0053)',
      previousOwner ? `${previousOwner.name} keeps its other roles and stays a participant` : 'Ownership moved',
    ],
  })
  offset++

  for (const p of getActiveParticipants(newState).filter((p) => p.id !== accepterId)) {
    const bullets =
      p.id === previousOwnerId
        ? [`CASE_OWNER moved to ${accepter.name}`, 'You retain your other roles (CM-21-008)']
        : p.id === 'caseactor'
        ? ['Case Actor committed the ownership change to the ledger', 'Announce(CaseLedgerEntry) → all participants (CM-21-007)']
        : [`${accepter.name} is now the CASE_OWNER`]
    events.push({
      id: `${eventId}-${p.id}-consequence`,
      actor: p.name,
      participantId: p.id,
      label: 'Ownership Transferred',
      x: nextX,
      lane: p.laneIndex,
      type: 'consequence',
      causedBy: eventId,
      timestamp: now + offset,
      consequences: bullets,
    })
    offset++
  }

  newState = addTimelineEvents(newState, events)
  newState = addEventLogEntries(newState, [
    `${accepter.name} accepted case ownership${previousOwner ? ` from ${previousOwner.name}` : ''}`,
  ])
  newState = incrementXPosition(newState)
  return newState
}
