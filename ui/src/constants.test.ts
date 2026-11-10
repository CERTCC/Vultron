/**
 * Unit tests of the node-color lookups in `constants.ts`.
 *
 * Both lookups compare participant ids as plain strings, so the type checker
 * cannot catch an id that no longer matches a palette key; a miss falls back to
 * the reporter's palette without an error. These pin which palette each id gets.
 */

import { describe, expect, it } from 'vitest'

import { NODE_COLORS, getVendorNodeColors, nodeColorsFor, simNodeColorsFor } from './constants'

describe('nodeColorsFor (Log Replay lane palette keys)', () => {
  it.each([
    ['reporter', NODE_COLORS.reporter],
    ['casemanager', NODE_COLORS.casemanager],
    ['coordinator', NODE_COLORS.coordinator],
    ['vendor-1', getVendorNodeColors(1)],
    ['vendor-2', getVendorNodeColors(2)],
  ])('gives the %s lane its own palette', (laneId, palette) => {
    expect(nodeColorsFor(laneId)).toBe(palette)
  })

  it('gives the CASE_MANAGER lane a palette distinct from the reporter fallback', () => {
    expect(nodeColorsFor('casemanager')).not.toBe(NODE_COLORS.reporter)
  })

  it.each(['unknown', 'finder', 'caseactor', ''])('falls back to the reporter palette for %j', (laneId) => {
    expect(nodeColorsFor(laneId)).toBe(NODE_COLORS.reporter)
  })
})

describe('simNodeColorsFor (simulation participant ids)', () => {
  it.each([
    ['finder', NODE_COLORS.reporter],
    ['caseactor', NODE_COLORS.casemanager],
    ['vendor-1', getVendorNodeColors(1)],
    ['vendor-3', getVendorNodeColors(3)],
  ])('maps %s to its palette', (participantId, palette) => {
    expect(simNodeColorsFor(participantId)).toBe(palette)
  })

  it.each(['someone', ''])('falls back to the reporter palette for %j', (participantId) => {
    expect(simNodeColorsFor(participantId)).toBe(NODE_COLORS.reporter)
  })
})
