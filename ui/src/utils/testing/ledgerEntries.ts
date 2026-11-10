/**
 * Hand-built ledger entries for the Log Replay unit tests, and a reader of a
 * replay's states (imported only by `*.test.ts`). A test states only the
 * payload it is about; the envelope fields every `CaseLedgerEntry` carries are
 * filled in here.
 */

import type { EmState, RmState } from '../../data/ledgerTypes'
import type { DemoState } from '../../types'
import type { As2Activity, CaseLedgerEntry } from '../caseLedgerParser'
import type { CaseRole } from '../replayLanes'

/** Actor ids for the hand-built ledgers: a cast with no meaning in its hosts. */
export const ACTORS = {
  manager: 'https://example.org/actors/manager',
  reporter: 'https://example.org/actors/r',
  vendor: 'https://example.org/actors/v',
  coordinator: 'https://example.org/actors/c1',
  coordinator2: 'https://example.org/actors/c2',
} as const

const CASE = 'urn:uuid:aaaa1111-0000-4000-8000-00000000cafe'

/** One ledger entry at `logIndex` with `semanticType` and `payloadSnapshot`. */
export function ledgerEntry(logIndex: number, semanticType: string, payloadSnapshot: As2Activity): CaseLedgerEntry {
  return {
    id: `${CASE}/log/${logIndex}`,
    type: 'CaseLedgerEntry',
    published: '2026-01-01T00:00:00Z',
    caseId: CASE,
    logIndex,
    logObjectId: `${CASE}/activity/${logIndex}`,
    semanticType,
    payloadSnapshot,
    prevLogHash: '0'.repeat(64),
    entryHash: `${logIndex}`.padStart(64, '0'),
    receivedAt: `2026-01-01T00:00:${String(logIndex).padStart(2, '0')}Z`,
  }
}

/** A `create_case_participant` entry recording `actor` with `caseRoles`. */
export function participantEntry(logIndex: number, actor: string, caseRoles: CaseRole[]): CaseLedgerEntry {
  return ledgerEntry(logIndex, 'create_case_participant', {
    type: 'Create',
    actor: ACTORS.manager,
    object: { type: 'CaseParticipant', attributedTo: actor, caseRoles },
  })
}

/**
 * A `create_case` entry whose roster is `roster` (each actor with its roles),
 * recorded by the CASE_MANAGER, with the case status at EM `emState`.
 */
export function createCaseEntry(roster: Record<string, CaseRole[]>, emState: EmState = 'ACTIVE'): CaseLedgerEntry {
  const caseParticipants = Object.entries(roster).map(([actor, caseRoles]) => ({
    type: 'CaseParticipant' as const,
    attributedTo: actor,
    caseRoles,
  }))
  return ledgerEntry(0, 'create_case', {
    type: 'Create',
    actor: ACTORS.manager,
    object: {
      type: 'VulnerabilityCase',
      actorParticipantIndex: Object.fromEntries(Object.keys(roster).map((actor, i) => [actor, `urn:p:${i}`])),
      caseStatuses: [{ type: 'CaseStatus', emState, pxaState: 'pxa' }],
      caseParticipants,
    },
  })
}

/** An `add_participant_status_to_participant` entry for `subject`, recorded by `recorder`. */
export function statusEntry(logIndex: number, recorder: string, subject: string, rmState: RmState): CaseLedgerEntry {
  return ledgerEntry(logIndex, 'add_participant_status_to_participant', {
    type: 'Add',
    actor: recorder,
    object: { type: 'ParticipantStatus', attributedTo: subject, rmState },
  })
}

/** The distinct states a lane's `machine` passes through in a replay, in step order. */
export function statePath(state: DemoState, machine: 'rm' | 'vfd', laneId: string): string[] {
  const path: string[] = []
  for (const snapshot of state.stepSnapshots ?? []) {
    const value = snapshot[machine][laneId]
    if (value !== undefined && path[path.length - 1] !== value) path.push(value)
  }
  return path
}
