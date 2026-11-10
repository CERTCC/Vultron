/**
 * Guards the Wire Activity notation the demo UI shows (Annex C,
 * `docs/reference/vultron-spec/_annex-c.md`).
 *
 * The expected forms come from the committed registry artifact
 * (`data/semantic_registry.json`, generated from Python's `SEMANTIC_REGISTRY`),
 * whose `wire` values are the `send:` lines of the occasions. So these tests
 * follow a regenerated artifact without an edit. Two checks:
 *
 * - every Wire Activity written in a `ui/src` module is one the registry lists,
 *   which rejects the pre-Annex-C forms (`Accept(Report)`, `Add(Note, target=Case)`);
 * - every Log Replay node built from a committed recording names the wire form
 *   of its own entry's semantic type, which rejects a form copied from the wrong
 *   occasion.
 */

import { describe, expect, it } from 'vitest'

import semanticRegistry from './data/semantic_registry.json'
import { buildTimelineFromCaseLedger } from './utils/caseLedgerMapper'
import { normalizeLedger, parseCaseLedger } from './utils/caseLedgerParser'

const WIRE_BY_TYPE: ReadonlyMap<string, string> = new Map(
  semanticRegistry.entries.flatMap((entry) =>
    entry.wire === null ? [] : [[entry.semanticType, entry.wire] as const]
  )
)

const REGISTRY_FORMS: ReadonlySet<string> = new Set(WIRE_BY_TYPE.values())

/**
 * Forms the UI may show that the registry does not list. `Create(Note)` is the
 * retired `create_note` verb (#4707), still rendered when an older uploaded log
 * carries it.
 */
const LEGACY_FORMS: ReadonlySet<string> = new Set(['Create(Note)'])

/**
 * A node that names the act an entry follows rather than the entry's own. The
 * `add_report_to_case` entry is drawn as the Reporter's "Submit Report" node, so
 * it names the Reporter's `Offer(VulnerabilityReport)`, not the CASE_MANAGER's
 * `Add(VulnerabilityReport)[target=VulnerabilityCase]`.
 */
const ANTECEDENT_FORMS: ReadonlyMap<string, string> = new Map([
  ['add_report_to_case', 'Offer(VulnerabilityReport)'],
])

/** The AS2 verbs the registry uses: a `Verb(` with one of these starts a form. */
const VERBS: readonly string[] = [
  ...new Set([...REGISTRY_FORMS].map((form) => form.slice(0, form.indexOf('(')))),
]

const FORM_START = new RegExp(`\\b(?:${VERBS.join('|')})\\(`, 'g')

/** Read one form from `start`: balanced parentheses, then any bracketed fields. */
function readForm(text: string, start: number): string {
  let i = text.indexOf('(', start)
  let depth = 0
  for (; i < text.length; i++) {
    if (text[i] === '(' || text[i] === '[') depth++
    else if (text[i] === ')' || text[i] === ']') depth--
    if (depth === 0) break
  }
  i++
  while (text[i] === '[') {
    const close = text.indexOf(']', i)
    if (close < 0) break
    i = close + 1
  }
  return text.slice(start, i)
}

/** Every outermost Wire Activity written in `text` (a nested one is part of it). */
function wireForms(text: string): string[] {
  const forms: string[] = []
  let end = 0
  for (const match of text.matchAll(FORM_START)) {
    if (match.index < end) continue
    const form = readForm(text, match.index)
    forms.push(form)
    end = match.index + form.length
  }
  return forms
}

const SOURCES = import.meta.glob<string>(['./**/*.{ts,tsx}', '!./**/*.test.ts'], {
  query: '?raw',
  import: 'default',
  eager: true,
})

const RECORDINGS = import.meta.glob<string>('./recordings/*/case-actor.jsonl', {
  query: '?raw',
  import: 'default',
  eager: true,
})

describe('Wire Activity notation in ui/src', () => {
  it('finds the registry verbs and the sources to scan', () => {
    expect(VERBS).toContain('Offer')
    expect(Object.keys(SOURCES).length).toBeGreaterThan(0)
  })

  it('writes every Wire Activity as a form the registry lists', () => {
    const scanned: string[] = []
    const unknown: string[] = []
    for (const [path, text] of Object.entries(SOURCES)) {
      for (const form of wireForms(text)) {
        scanned.push(form)
        if (!REGISTRY_FORMS.has(form) && !LEGACY_FORMS.has(form)) unknown.push(`${path}: ${form}`)
      }
    }
    expect(scanned.length).toBeGreaterThan(0)
    expect(unknown).toEqual([])
  })

  it('rejects the pre-Annex-C forms', () => {
    for (const old of ['Accept(Report)', 'Add(Note, target=Case)', 'Offer(Actor, Case)', 'Reject(Offer)']) {
      expect(wireForms(`'${old} activity created'`)).toEqual([old])
      expect(REGISTRY_FORMS.has(old)).toBe(false)
    }
  })
})

describe('Log Replay nodes over the committed recordings', () => {
  it('name the wire form of their own entry', () => {
    const checked = new Set<string>()
    const mismatched: string[] = []
    for (const [path, raw] of Object.entries(RECORDINGS)) {
      const entries = normalizeLedger(parseCaseLedger(raw, path).entries)
      const { timelineEvents } = buildTimelineFromCaseLedger(entries)
      for (const entry of entries) {
        const expected = WIRE_BY_TYPE.get(entry.semanticType)
        if (expected === undefined) continue
        for (const event of timelineEvents.filter((e) => e.id.startsWith(`${entry.id}-`))) {
          for (const form of event.consequences.flatMap(wireForms)) {
            checked.add(entry.semanticType)
            if (form !== expected && form !== ANTECEDENT_FORMS.get(entry.semanticType)) {
              mismatched.push(`${path} ${entry.semanticType}: ${form} (expected ${expected})`)
            }
          }
        }
      }
    }
    expect(checked.size).toBeGreaterThan(0)
    expect(mismatched).toEqual([])
  })
})
