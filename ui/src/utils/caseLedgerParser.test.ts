/**
 * Unit tests of the VFD ladder token the Log Replay parser reads from a status
 * (`vfdLadderToken`). The lanes are tested in `replayLanes.test.ts`.
 */

import { describe, expect, it } from 'vitest'

import { vfdLadderToken } from './caseLedgerParser'

describe('vfdLadderToken', () => {
  it.each([
    [{ vfState: 'vf' }, 'vfd'],
    [{ vfState: 'Vf' }, 'Vfd'],
    [{ vfState: 'VF' }, 'VFd'],
    [{ vfState: 'VF', dState: 'd' }, 'VFd'],
    [{ vfState: 'VF', dState: 'D' }, 'VFD'],
  ] as const)('reads %o as %s', (status, token) => {
    expect(vfdLadderToken(status)).toBe(token)
  })

  it('gives no token for a status with no vfState, which is not a Vendor\'s', () => {
    expect(vfdLadderToken({})).toBeUndefined()
    expect(vfdLadderToken({ vfState: null, dState: 'D' })).toBeUndefined()
    expect(vfdLadderToken(undefined)).toBeUndefined()
  })

  it('does not read the retired vfdState key', () => {
    const retired = JSON.parse('{"rmState": "ACCEPTED", "vfdState": "VFD"}') as Parameters<typeof vfdLadderToken>[0]
    expect(vfdLadderToken(retired)).toBeUndefined()
  })
})
