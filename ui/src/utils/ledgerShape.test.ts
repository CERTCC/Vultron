/**
 * Unit tests of the run-time ledger-line shape check (`ledgerLineProblems`) and
 * of how `parseCaseLedger` treats a line that fails it.
 *
 * The definitions come from the generated `../data/ledgerTypes.ts`, so these
 * tests build each malformed line from a well-formed one and change one thing.
 */

import { describe, expect, it } from 'vitest'

import { LEDGER_SHAPES } from '../data/ledgerTypes'
import { parseCaseLedger } from './caseLedgerParser'
import { ledgerLineProblems, valueProblems } from './ledgerShape'

const LEDGERS = import.meta.glob<string>(
  ['../recordings/*/case-actor.jsonl', '../synthetic-ledgers/*.jsonl'],
  { query: '?raw', import: 'default', eager: true },
)

const CASE = 'urn:uuid:aaaa1111-0000-4000-8000-000000000001'

function caseStatus(): Record<string, unknown> {
  return {
    id: `${CASE}/status/1`,
    type: 'CaseStatus',
    context: CASE,
    published: '2026-01-01T00:00:00.000000+00:00',
    emState: 'ACTIVE',
    pxaState: 'pxa',
  }
}

function participantStatus(): Record<string, unknown> {
  return {
    id: `${CASE}/participant-status/1`,
    type: 'ParticipantStatus',
    context: CASE,
    attributedTo: 'http://actor1:7999/api/v2/actors/actor1',
    rmState: 'ACCEPTED',
    vfState: 'Vf',
    caseEngagement: true,
    cvdRole: ['VENDOR'],
  }
}

/** A well-formed `add_participant_status_to_participant` line. */
function entry(object: unknown = participantStatus()): Record<string, unknown> {
  return {
    '@context': ['https://www.w3.org/ns/activitystreams'],
    id: `${CASE}/log/1`,
    type: 'CaseLedgerEntry',
    published: '2026-01-01T00:00:01.000000+00:00',
    caseId: CASE,
    logIndex: 1,
    logObjectId: `${CASE}/activity/1`,
    semanticType: 'add_participant_status_to_participant',
    payloadSnapshot: {
      type: 'Add',
      actor: 'http://actor1:7999/api/v2/actors/actor1',
      object,
    },
    prevLogHash: 'a'.repeat(64),
    entryHash: 'b'.repeat(64),
    receivedAt: '2026-01-01T00:00:01.000000+00:00',
  }
}

describe('ledgerLineProblems', () => {
  it('passes a well-formed line', () => {
    expect(ledgerLineProblems(entry())).toEqual([])
  })

  it.each(Object.entries(LEDGERS))('passes every line of %s', (path, raw) => {
    const { entries, rejected } = parseCaseLedger(raw, path)
    expect(rejected).toEqual([])
    expect(entries.length).toBeGreaterThan(0)
  })

  it('refuses a line that is not an object', () => {
    expect(ledgerLineProblems([1, 2])).toEqual(['line: expected a CaseLedgerEntry object, got an array'])
  })

  it('names each envelope field the CASE_MANAGER always writes when it is missing', () => {
    const line = entry()
    delete line.logIndex
    delete line.entryHash
    expect(ledgerLineProblems(line)).toEqual([
      'logIndex: missing (CaseLedgerEntry requires it)',
      'entryHash: missing (CaseLedgerEntry requires it)',
    ])
  })

  it('refuses an undeclared envelope key, such as the retired eventType', () => {
    expect(ledgerLineProblems({ ...entry(), eventType: 'create_case' })).toEqual([
      'eventType: CaseLedgerEntry declares no such key',
    ])
  })

  it('refuses a value of the wrong kind, an empty required id and a null where none is allowed', () => {
    expect(ledgerLineProblems({ ...entry(), logIndex: '1', id: ' ', receivedAt: null })).toEqual([
      'id: must not be empty',
      'logIndex: expected an integer, got "1"',
      'receivedAt: null is not allowed',
    ])
  })

  it('refuses a duration or a payload of the wrong kind', () => {
    expect(ledgerLineProblems({ ...entry(), duration: 5, payloadSnapshot: [] })).toEqual([
      'duration: expected a duration string, got number 5',
      'payloadSnapshot: expected an object, got an array',
    ])
  })

  it('accepts an ISO 8601 duration and refuses any other string', () => {
    expect(ledgerLineProblems({ ...entry(), duration: 'P1DT2H3.5S' })).toEqual([])
    expect(ledgerLineProblems({ ...entry(), duration: '-PT5S' })).toEqual([])
    expect(ledgerLineProblems({ ...entry(), duration: 'banana' })).toEqual([
      'duration: "banana" is not an ISO 8601 duration',
    ])
    expect(ledgerLineProblems({ ...entry(), duration: 'PT' })).toEqual(['duration: "PT" is not an ISO 8601 duration'])
  })

  it('accepts a language map and refuses a blank tag or text in one', () => {
    const contentMap = { en: 'A summary', fr: 'Un résumé' }
    expect(ledgerLineProblems({ ...entry(), contentMap })).toEqual([])
    expect(ledgerLineProblems({ ...entry(), nameMap: { ' ': 'x', de: '' } })).toEqual([
      'nameMap: key " " must not be empty',
      'nameMap.de: must not be empty',
    ])
    expect(ledgerLineProblems({ ...entry(), contentMap: null })).toEqual([])
    expect(ledgerLineProblems({ ...entry(), summaryMap: 'en' })).toEqual([
      'summaryMap: expected an object, got "en"',
    ])
  })

  it('refuses a logIndex below the model\'s minimum', () => {
    expect(ledgerLineProblems({ ...entry(), logIndex: -1 })).toEqual([])
    expect(ledgerLineProblems({ ...entry(), logIndex: -5 })).toEqual(['logIndex: number -5 is below the minimum -1'])
  })

  it('names the array member that fails a union, and an empty @context list', () => {
    expect(ledgerLineProblems({ ...entry(), '@context': ['a', 5] })).toEqual([
      '@context: matches none of its forms (expected a string, got an array; ' +
        '[1]: expected a string, got number 5)',
    ])
    expect(ledgerLineProblems({ ...entry(), '@context': [] })).toEqual([
      '@context: matches none of its forms (expected a string, got an array; must hold at least 1 item(s))',
    ])
  })

  it('refuses a timestamp that is not an ISO 8601 date-time', () => {
    expect(ledgerLineProblems({ ...entry(), published: 'yesterday' })).toEqual([
      'published: "yesterday" is not an ISO 8601 date-time',
    ])
    // Date.parse takes both of these; the model's serializer writes neither.
    expect(ledgerLineProblems({ ...entry(), published: '1' })).toEqual([
      'published: "1" is not an ISO 8601 date-time',
    ])
    expect(ledgerLineProblems({ ...entry(), published: 'March 7, 2026' })).toEqual([
      'published: "March 7, 2026" is not an ISO 8601 date-time',
    ])
    // Shaped right, but no such date.
    expect(ledgerLineProblems({ ...entry(), published: '2026-13-40T00:00:00Z' })).toEqual([
      'published: "2026-13-40T00:00:00Z" is not an ISO 8601 date-time',
    ])
  })

  it('accepts each date-time form the model writes', () => {
    for (const published of ['2026-01-01T00:00:00Z', '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00.123456-05:00']) {
      expect(ledgerLineProblems({ ...entry(), published })).toEqual([])
    }
  })

  it('accepts either form of the JSON-LD @context and refuses any other', () => {
    expect(ledgerLineProblems({ ...entry(), '@context': 'https://www.w3.org/ns/activitystreams' })).toEqual([])
    const [problem] = ledgerLineProblems({ ...entry(), '@context': 7 })
    expect(problem).toMatch(/^@context: matches none of its forms/)
  })

  it('checks a payload status against the generated enum values', () => {
    const status = { ...participantStatus(), vfState: 'VFD', cvdRole: ['VENDOR', 'FINDER'] }
    expect(ledgerLineProblems(entry(status))).toEqual([
      'payloadSnapshot.object.vfState: "VFD" is not a VfState (vf, Vf, VF)',
      'payloadSnapshot.object.cvdRole[1]: "FINDER" is not a CvdRole (' +
        'REPORTER, VENDOR, DEPLOYER, COORDINATOR, OBSERVER, CASE_OWNER, CASE_MANAGER, ' +
        'CVE_NUMBERING_AUTHORITY)',
    ])
  })

  it('refuses a wrong boolean, a wrong type literal and a non-object status', () => {
    expect(ledgerLineProblems(entry({ ...participantStatus(), caseEngagement: 'yes' }))).toEqual([
      'payloadSnapshot.object.caseEngagement: expected a boolean, got "yes"',
    ])
    expect(ledgerLineProblems({ ...entry(), type: 'Activity' })).toEqual([
      'type: expected "CaseLedgerEntry", got "Activity"',
    ])
    expect(ledgerLineProblems(entry({ ...participantStatus(), caseStatus: 'x' }))).toEqual([
      'payloadSnapshot.object.caseStatus: expected a CaseStatus object, got "x"',
    ])
  })

  it('tolerates an undeclared key on a payload status, as the parse edge sets it aside', () => {
    expect(ledgerLineProblems(entry({ ...participantStatus(), vfdState: 'Vfd' }))).toEqual([])
  })

  it('requires on a payload status only what the model cannot go without', () => {
    const status = participantStatus()
    delete status.context
    delete status.caseEngagement
    expect(ledgerLineProblems(entry(status))).toEqual([
      'payloadSnapshot.object.context: missing (ParticipantStatus requires it)',
    ])
  })

  it('requires the sender time of a received CaseStatus', () => {
    const status = caseStatus()
    delete status.published
    expect(ledgerLineProblems(entry(status))).toEqual([
      'payloadSnapshot.object.published: missing (CaseStatus requires it)',
    ])
  })

  it('reports a nested CaseStatus once, through the field that holds it', () => {
    const nested = { ...caseStatus(), emState: 'OPEN' }
    expect(ledgerLineProblems(entry({ ...participantStatus(), caseStatus: nested }))).toEqual([
      'payloadSnapshot.object.caseStatus.emState: "OPEN" is not a EmState (NONE, PROPOSED, ACTIVE, REVISE, EXITED)',
    ])
  })

  it('finds a status at any depth of the payload, such as a participant list', () => {
    const target = {
      type: 'CaseParticipant',
      participantStatuses: [participantStatus(), { ...participantStatus(), rmState: 'DONE' }],
    }
    const line = entry()
    line.payloadSnapshot = { type: 'Add', object: participantStatus(), target }
    expect(ledgerLineProblems(line)).toEqual([
      'payloadSnapshot.target.participantStatuses[1].rmState: "DONE" is not a RmState ' +
        '(START, RECEIVED, INVALID, VALID, DEFERRED, ACCEPTED, CLOSED)',
    ])
  })

  it('checks a participant record\'s roles and consent rows against the generated definitions', () => {
    const record = {
      type: 'CaseParticipant',
      attributedTo: 'http://actor1:7999/api/v2/actors/actor1',
      caseRoles: ['vendor', 'VENDOR'],
      embargoConsents: [{ type: 'EmbargoConsent', state: 'AGREED' }],
    }
    const line = entry()
    line.payloadSnapshot = { type: 'Create', object: record }
    expect(ledgerLineProblems(line)).toEqual([
      'payloadSnapshot.object.caseRoles[1]: "VENDOR" is not a CaseRoles ' +
        '(reporter, vendor, deployer, coordinator, observer, case_owner, case_manager, cve_numbering_authority)',
      'payloadSnapshot.object.embargoConsents[0].embargoId: missing (EmbargoConsent requires it)',
    ])
  })

  it('reports every problem of a line, not only the first', () => {
    const line = { ...entry({ ...participantStatus(), rmState: 1 }), logIndex: -0.5, caseId: 3 }
    expect(ledgerLineProblems(line)).toHaveLength(3)
  })
})

describe('the generated definitions', () => {
  it('carry the VFD dimensions as vfState and dState, not the retired keys', () => {
    const keys = LEDGER_SHAPES.ParticipantStatus.fields.map((field) => field.key)
    expect(keys).toEqual(expect.arrayContaining(['rmState', 'vfState', 'dState']))
    expect(keys).not.toContain('vfdState')
    expect(keys).not.toContain('emConsentState')
  })
})

describe('parseCaseLedger', () => {
  const good = JSON.stringify(entry())

  it('returns each well-formed line as an entry', () => {
    const { entries, rejected } = parseCaseLedger(`${good}\n\n${good}\n`)
    expect(entries).toHaveLength(2)
    expect(rejected).toEqual([])
  })

  it('sets aside a line that is not JSON, with its source and line number', () => {
    const { entries, rejected } = parseCaseLedger(`${good}\n{not json\n${good}`, 'upload.jsonl')
    expect(entries).toHaveLength(2)
    expect(rejected).toHaveLength(1)
    expect(rejected[0]).toMatchObject({ source: 'upload.jsonl', lineNumber: 2, text: '{not json' })
    expect(rejected[0].problems).toHaveLength(1)
    expect(rejected[0].problems[0]).toMatch(/^not JSON: /)
  })

  it('sets aside a line of the wrong shape, with every problem, and replays the rest', () => {
    const bad = JSON.stringify({ ...entry(), semanticType: undefined, extra: true })
    const { entries, rejected } = parseCaseLedger(`${bad}\n${good}`, 'mixed.jsonl')
    expect(entries).toHaveLength(1)
    expect(rejected).toEqual([
      {
        source: 'mixed.jsonl',
        lineNumber: 1,
        problems: ['semanticType: missing (CaseLedgerEntry requires it)', 'extra: CaseLedgerEntry declares no such key'],
        text: bad,
      },
    ])
  })
})

describe('valueProblems', () => {
  it('checks both integer bounds the exporter can write', () => {
    const shape = { kind: 'integer', minimum: 0, maximum: 9 } as const
    expect(valueProblems(9, shape)).toEqual([])
    expect(valueProblems(10, shape)).toEqual(['value: number 10 is above the maximum 9'])
    expect(valueProblems(-1, shape)).toEqual(['value: number -1 is below the minimum 0'])
  })

  it('refuses an actor id spelled with a trailing slash where the model does', () => {
    const shape = { kind: 'string', nonEmpty: true, noTrailingSlash: true } as const
    expect(valueProblems('http://actor1:7999/api/v2/actors/actor1', shape)).toEqual([])
    expect(valueProblems('http://actor1:7999/api/v2/actors/actor1/', shape)).toEqual([
      'value: must not end in a trailing slash (an actor id in its canonical spelling)',
    ])
  })
})
