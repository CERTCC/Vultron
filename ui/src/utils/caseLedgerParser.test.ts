/**
 * Unit tests of the Log Replay parser's lane mapping (`actorUrlToLaneId`).
 *
 * The lane ids are plain strings compared all through the mapper and the
 * replay view, so the type checker cannot catch a missed rename; these pin the
 * ids each actor URL shape resolves to.
 */

import { describe, expect, it } from 'vitest'

import { actorUrlToLaneId } from './caseLedgerParser'

describe('actorUrlToLaneId', () => {
  it.each([
    // The fixed cast (DEMOCI-11-020) and the dedicated case-actor container.
    ['http://actor0:7999/api/v2/actors/actor0', 'reporter'],
    ['http://actor1:7999/api/v2/actors/actor1', 'vendor-1'],
    ['http://actor2:7999/api/v2/actors/actor2', 'coordinator'],
    ['http://actor3:7999/api/v2/actors/actor3', 'vendor-2'],
    ['http://actor4:7999/api/v2/actors/actor4', 'vendor-3'],
    ['http://case-actor:7999/api/v2/actors/case-actor', 'casemanager'],
    // Pre-cast hosts, kept for older logs.
    ['http://reporter:7999/api/v2/actors/reporter', 'reporter'],
    ['http://finder:7999/api/v2/actors/finder', 'reporter'],
    ['http://coordinator:7999/api/v2/actors/coordinator', 'coordinator'],
    ['http://vendor:7999/api/v2/actors/vendor', 'vendor-1'],
    ['http://vendor2:7999/api/v2/actors/vendor2', 'vendor-2'],
    ['http://actor5:7999/api/v2/actors/actor5', 'vendor-2'],
    ['http://actor6:7999/api/v2/actors/actor6', 'vendor-3'],
  ] as const)('maps %s to the %s lane', (url, lane) => {
    expect(actorUrlToLaneId(url)).toBe(lane)
  })

  it('maps a case-actor sub-actor to the casemanager lane, not its host lane', () => {
    expect(
      actorUrlToLaneId('http://vendor:7999/api/v2/actors/case-actor-aaaa1111-0000-4000-8000-000000000001'),
    ).toBe('casemanager')
    expect(actorUrlToLaneId('http://coordinator:7999/api/v2/actors/case-actor-x')).toBe('casemanager')
  })

  it.each([undefined, null, '', 'http://elsewhere:7999/api/v2/actors/someone'])(
    'maps %s to unknown',
    (url) => {
      expect(actorUrlToLaneId(url)).toBe('unknown')
    },
  )
})
