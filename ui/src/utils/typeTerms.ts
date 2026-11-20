/**
 * The type names an AS2 `type` value carries, for Log Replay readers.
 *
 * A Vultron extension type is sent as a list of its own type and the AS2
 * type it refines (`["EmbargoEvent", "Event"]`, `["Refuse", "Reject"]`;
 * VM-03-005, ADR-0196, ADR-0201), and a payload snapshot keeps the body as
 * sent. So a reader asks whether a value *names* a type, never compares it
 * with a string. The mirror of `vultron/core/models/type_terms.py`.
 */

/** The non-blank type names `value` carries, in order. */
export function typeTerms(value: unknown): string[] {
  const items = typeof value === 'string' ? [value] : Array.isArray(value) ? value : []
  return items.filter((t): t is string => typeof t === 'string' && t.trim() !== '')
}

/** Whether `value`, a `type` value, names `type`. */
export function namesType(value: unknown, type: string): boolean {
  return typeTerms(value).includes(type)
}

/** The type `value` names first: a sender writes its own type first. */
export function ownType(value: unknown): string | undefined {
  return typeTerms(value)[0]
}
