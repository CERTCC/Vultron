import { describe, expect, it } from 'vitest'

import { namesType, ownType, typeTerms } from './typeTerms'

describe('typeTerms', () => {
  it('reads a string as one term and a list as its string terms', () => {
    expect(typeTerms('EmbargoEvent')).toEqual(['EmbargoEvent'])
    expect(typeTerms(['EmbargoEvent', 'Event', 3, ' '])).toEqual(['EmbargoEvent', 'Event'])
    expect(typeTerms(undefined)).toEqual([])
  })

  it('asks whether a value names a type, in any position', () => {
    expect(namesType(['EmbargoEvent', 'Event'], 'Event')).toBe(true)
    expect(namesType('Note', 'Event')).toBe(false)
  })

  it('reads the own type as the first term', () => {
    expect(ownType(['Refuse', 'Reject'])).toBe('Refuse')
    expect(ownType(null)).toBeUndefined()
  })
})
