/**
 * Unit tests of the Log Replay lanes (`buildLanes`): a lane is keyed on the
 * participant's actor id and labelled by the CVD roles the ledger records give
 * it, never by its host (#4729 AC-5, #5585).
 */

import { describe, expect, it } from 'vitest'

import { baseLabel, buildLanes, laneKind } from './replayLanes'
import { ACTORS, createCaseEntry, ledgerEntry, participantEntry, statusEntry } from './testing/ledgerEntries'

describe('buildLanes', () => {
  const entries = [
    createCaseEntry({
      [ACTORS.manager]: ['coordinator', 'case_manager'],
      [ACTORS.coordinator]: ['coordinator', 'case_owner'],
      [ACTORS.reporter]: ['reporter'],
    }),
    participantEntry(1, ACTORS.vendor, ['vendor']),
    participantEntry(2, ACTORS.coordinator2, ['coordinator']),
  ]
  const lanes = buildLanes(entries)

  it('keys each lane on the actor id', () => {
    expect(lanes.lanes.map((lane) => lane.id)).toEqual([
      ACTORS.reporter,
      ACTORS.vendor,
      ACTORS.coordinator,
      ACTORS.coordinator2,
      ACTORS.manager,
    ])
  })

  it('labels each lane by its roles and numbers a repeated label from the second', () => {
    expect(lanes.lanes.map((lane) => lane.label)).toEqual([
      'Reporter',
      'Vendor',
      'Coordinator',
      'Coordinator 2',
      'Case Manager',
    ])
    expect(lanes.lanes.map((lane) => lane.index)).toEqual([0, 1, 2, 3, 4])
  })

  it('leaves CASE_OWNER out of a label, as it moves between participants', () => {
    const owner = lanes.get(ACTORS.coordinator)
    expect(owner?.roles).toEqual(['coordinator', 'case_owner'])
    expect(owner?.label).toBe('Coordinator')
    expect(owner?.roleLabel).toBe('COORDINATOR')
  })

  it('labels the CASE_MANAGER by that role alone', () => {
    const manager = lanes.get(ACTORS.manager)
    expect(manager?.kind).toBe('casemanager')
    expect(manager?.roleLabel).toBe('CASE_MANAGER')
    expect(manager?.palette).toBe('casemanager')
  })

  it('gives each Vendor its own palette, numbered in lane order', () => {
    const two = buildLanes([
      participantEntry(0, ACTORS.vendor, ['vendor']),
      participantEntry(1, ACTORS.coordinator2, ['vendor', 'deployer']),
    ])
    const vendors = two.lanes.filter((lane) => lane.kind === 'vendor')
    expect(vendors.map((lane) => [lane.label, lane.palette])).toEqual([
      ['Vendor', 'vendor-1'],
      ['Vendor / Deployer', 'vendor-2'],
    ])
  })

  it('keeps a lane and its label when the roles move in a handoff', () => {
    const handoff = buildLanes([
      ...entries,
      ledgerEntry(3, 'update_case_participant', {
        type: 'Update',
        actor: ACTORS.manager,
        object: { type: 'CaseParticipant', attributedTo: ACTORS.coordinator2, caseRoles: ['coordinator', 'case_owner'] },
      }),
    ])
    expect(handoff.lanes.map((lane) => [lane.id, lane.label])).toEqual(
      lanes.lanes.map((lane) => [lane.id, lane.label])
    )
  })

  it('reads the roles of a status when the ledger holds no participant record', () => {
    const legacy = buildLanes([statusEntry(0, ACTORS.vendor, ACTORS.vendor, 'ACCEPTED')])
    expect(legacy.get(ACTORS.vendor)?.label).toBe('Participant')
    const withRoles = buildLanes([
      ledgerEntry(0, 'add_participant_status_to_participant', {
        type: 'Add',
        actor: ACTORS.vendor,
        object: { type: 'ParticipantStatus', attributedTo: ACTORS.vendor, cvdRole: ['VENDOR', 'DEPLOYER'] },
      }),
    ])
    expect(withRoles.get(ACTORS.vendor)?.roles).toEqual(['vendor', 'deployer'])
  })

  it('prefers the participant records over a status', () => {
    const both = buildLanes([
      participantEntry(0, ACTORS.coordinator, ['coordinator']),
      ledgerEntry(1, 'add_participant_status_to_participant', {
        type: 'Add',
        actor: ACTORS.coordinator,
        object: { type: 'ParticipantStatus', attributedTo: ACTORS.coordinator, cvdRole: ['VENDOR'] },
      }),
    ])
    expect(both.get(ACTORS.coordinator)?.label).toBe('Coordinator')
  })

  it('labels an actor with no roles "Participant", whatever its host says', () => {
    const lanes = buildLanes([
      ledgerEntry(0, 'add_note_to_case', { type: 'Add', actor: 'http://vendor:7999/api/v2/actors/vendor' }),
    ])
    expect(lanes.lanes.map((lane) => [lane.label, lane.kind])).toEqual([['Participant', 'participant']])
  })

  it('looks up no lane for an absent or unknown actor id', () => {
    expect(lanes.get(undefined)).toBeUndefined()
    expect(lanes.get(null)).toBeUndefined()
    expect(lanes.get('https://example.org/actors/nobody')).toBeUndefined()
  })
})

describe('laneKind and baseLabel', () => {
  it.each([
    [['coordinator', 'case_manager'], 'casemanager', 'Case Manager'],
    [['reporter'], 'reporter', 'Reporter'],
    [['vendor', 'case_owner'], 'vendor', 'Vendor'],
    [['coordinator'], 'coordinator', 'Coordinator'],
    [['deployer'], 'participant', 'Deployer'],
    [['case_owner'], 'participant', 'Participant'],
    [[], 'participant', 'Participant'],
  ] as const)('reads %j as a %s lane labelled %s', (roles, kind, label) => {
    expect(laneKind(roles)).toBe(kind)
    expect(baseLabel(roles)).toBe(label)
  })
})
