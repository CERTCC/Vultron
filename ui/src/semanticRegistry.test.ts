/**
 * Unit tests of the registry phrasing (`renderPhrase`) and wire forms
 * (`wireForm`) the Log Replay mapper labels its nodes with. The rules are the
 * Python report's (`CaseTimelineEvent.summary`, DRPT-03-002 to DRPT-03-012):
 * the tests read the templates from the committed artifact, so a reworded
 * phrase needs no edit here.
 */

import { describe, expect, it } from 'vitest'

import semanticRegistry from './data/semantic_registry.json'
import { isRegisteredSemanticType, renderPhrase, wireForm } from './semanticRegistry'

const entry = (semanticType: string) => {
  const found = semanticRegistry.entries.find((e) => e.semanticType === semanticType)
  if (!found) throw new Error(`${semanticType} is not in the registry`)
  return found
}

/** A three-slot phrase, so every slot rule shows. */
const THREE_SLOTS = 'offer_case_participant_role'

describe('renderPhrase', () => {
  it('fills every slot it is given', () => {
    expect(entry(THREE_SLOTS).phrase).toBe('{actor} offered {object} role to {target} in the case')
    expect(renderPhrase(THREE_SLOTS, { actor: 'Vendor', object: 'Coordinator', target: 'Reporter' })).toBe(
      'Vendor offered Coordinator role to Reporter in the case'
    )
  })

  it('renders a slot it is not given as an em-dash', () => {
    expect(renderPhrase(THREE_SLOTS, { actor: 'Vendor' })).toBe('Vendor offered — role to — in the case')
  })

  it('drops the leading "— " only when no actor is given', () => {
    expect(renderPhrase('validate_report')).toBe('Validated the report')
    expect(renderPhrase(THREE_SLOTS, { object: 'Coordinator' })).toBe('Offered Coordinator role to — in the case')
  })

  it('capitalizes the first letter, and only it', () => {
    expect(renderPhrase('validate_report', { actor: 'vendor' })).toBe('Vendor validated the report')
    expect(renderPhrase('validate_report', { actor: 'cNA' })).toBe('CNA validated the report')
  })

  it('renders a type the registry does not list as its humanized name', () => {
    expect(isRegisteredSemanticType('frobnicate_the_case')).toBe(false)
    expect(renderPhrase('frobnicate_the_case', { actor: 'Vendor' })).toBe('Frobnicate the case')
    expect(renderPhrase('_')).toBe('Performed an action')
  })

  it('renders every registered phrase with no slot left unfilled', () => {
    for (const { semanticType } of semanticRegistry.entries) {
      const rendered = renderPhrase(semanticType, { actor: 'A', object: 'B', target: 'C' })
      expect(rendered).not.toMatch(/[{}]/)
    }
  })
})

describe('wireForm', () => {
  it('is the registry\'s Wire Activity for a type', () => {
    expect(wireForm('validate_report')).toBe('Accept(Offer(VulnerabilityReport))')
  })

  it('is undefined for a fallback type and for an unregistered one', () => {
    expect(entry('unknown').wire).toBeNull()
    expect(wireForm('unknown')).toBeUndefined()
    expect(wireForm('frobnicate_the_case')).toBeUndefined()
  })
})
