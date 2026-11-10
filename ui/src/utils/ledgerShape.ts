/**
 * Run-time shape check of one case-ledger line, against the definitions in
 * `../data/ledgerTypes.ts` (generated from the Python models by
 * `uv run export-demo-ledger-types`).
 *
 * The line itself must be a `CaseLedgerEntry` as the CASE_MANAGER writes it:
 * every field the model always writes, the right kind of value in each, and no
 * key the model does not declare. Inside its `payloadSnapshot`, which is the
 * body as received, every object whose `type` names an exported model
 * (`ParticipantStatus`, `CaseStatus`) is checked the way the parse edge reads
 * it: only the fields the model cannot go without are required, and a key the
 * model does not declare is not a fault, since the parse edge sets such a key
 * aside (MV-11-003).
 *
 * The check reports every problem it finds, so a line is judged whole. It never
 * repairs a line: what to do with a line that has problems is the caller's call
 * (`parseCaseLedger` sets it aside as a rejected line, shown to the user).
 */

import {
  LEDGER_SHAPES,
  type FieldShape,
  type LedgerTypeName,
} from '../data/ledgerTypes'

const TYPE_NAMES: ReadonlySet<string> = new Set(Object.keys(LEDGER_SHAPES))

function isLedgerTypeName(value: unknown): value is LedgerTypeName {
  return typeof value === 'string' && TYPE_NAMES.has(value)
}

/**
 * An ISO 8601 duration as Pydantic writes a `timedelta` (`P1DT2H3.5S`, `-PT5S`):
 * at least one component, and a time part only when it holds one.
 */
/**
 * An ISO 8601 date-time as Pydantic writes a `datetime`
 * (`2026-01-01T00:00:00Z`, `2026-01-01T00:00:00.5+00:00`). `Date.parse` alone
 * is not the check: it also takes `"1"` or `"March 7"`.
 */
const ISO_DATETIME = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?$/

const ISO_DURATION = /^-?P(?!$)(\d+(\.\d+)?Y)?(\d+(\.\d+)?M)?(\d+(\.\d+)?W)?(\d+(\.\d+)?D)?(T(?=\d)(\d+(\.\d+)?H)?(\d+(\.\d+)?M)?(\d+(\.\d+)?S)?)?$/

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/** A short description of a value's JSON kind, for a problem message. */
function describe(value: unknown): string {
  if (value === null) return 'null'
  if (Array.isArray(value)) return 'an array'
  if (typeof value === 'string') return JSON.stringify(value)
  if (typeof value === 'object') return 'an object'
  return `${typeof value} ${String(value)}`
}

function join(path: string, key: string | number): string {
  if (typeof key === 'number') return `${path}[${key}]`
  return path ? `${path}.${key}` : key
}

/** Checks values against shapes, remembering which objects it has checked. */
class ShapeChecker {
  readonly problems: string[] = []
  private readonly checked = new WeakSet<object>()

  /** Check `value` as one exported model, then each of its fields. */
  checkObject(value: unknown, typeName: LedgerTypeName, path: string): void {
    if (!isRecord(value)) {
      this.problems.push(`${path || 'line'}: expected a ${typeName} object, got ${describe(value)}`)
      return
    }
    this.checked.add(value)
    const definition = LEDGER_SHAPES[typeName]
    const declared = new Set<string>()
    for (const field of definition.fields) {
      declared.add(field.key)
      const fieldPath = join(path, field.key)
      if (!(field.key in value)) {
        if (field.required) this.problems.push(`${fieldPath}: missing (${typeName} requires it)`)
        continue
      }
      const fieldValue = value[field.key]
      if (fieldValue === null) {
        if (!field.nullable) this.problems.push(`${fieldPath}: null is not allowed`)
        continue
      }
      this.checkValue(fieldValue, field.shape, fieldPath)
    }
    if (definition.closed) {
      for (const key of Object.keys(value)) {
        if (!declared.has(key)) {
          this.problems.push(`${join(path, key)}: ${typeName} declares no such key`)
        }
      }
    }
  }

  checkValue(value: unknown, shape: FieldShape, path: string): void {
    const problem = this.valueProblem(value, shape, path)
    if (problem !== null) this.problems.push(`${path}: ${problem}`)
  }

  /** The problem with `value` as `shape`, or null; nested problems are pushed. */
  private valueProblem(value: unknown, shape: FieldShape, path: string): string | null {
    switch (shape.kind) {
      case 'any':
        return null
      case 'string':
        if (typeof value !== 'string') return `expected a string, got ${describe(value)}`
        return shape.nonEmpty && value.trim() === '' ? 'must not be empty' : null
      case 'datetime':
        if (typeof value !== 'string') return `expected a datetime string, got ${describe(value)}`
        return ISO_DATETIME.test(value) && !Number.isNaN(Date.parse(value))
          ? null
          : `${describe(value)} is not an ISO 8601 date-time`
      case 'duration':
        if (typeof value !== 'string') return `expected a duration string, got ${describe(value)}`
        return ISO_DURATION.test(value) ? null : `${describe(value)} is not an ISO 8601 duration`
      case 'integer':
        if (!Number.isInteger(value)) return `expected an integer, got ${describe(value)}`
        if (shape.minimum !== undefined && (value as number) < shape.minimum) {
          return `${describe(value)} is below the minimum ${shape.minimum}`
        }
        if (shape.maximum !== undefined && (value as number) > shape.maximum) {
          return `${describe(value)} is above the maximum ${shape.maximum}`
        }
        return null
      case 'boolean':
        return typeof value === 'boolean' ? null : `expected a boolean, got ${describe(value)}`
      case 'object':
        return isRecord(value) ? null : `expected an object, got ${describe(value)}`
      case 'literal':
        return value === shape.value ? null : `expected ${JSON.stringify(shape.value)}, got ${describe(value)}`
      case 'enum':
        return typeof value === 'string' && shape.values.includes(value)
          ? null
          : `${describe(value)} is not a ${shape.type} (${shape.values.join(', ')})`
      case 'array':
        if (!Array.isArray(value)) return `expected an array, got ${describe(value)}`
        value.forEach((item, i) => this.checkValue(item, shape.items, join(path, i)))
        if (shape.minItems !== undefined && value.length < shape.minItems) {
          return `must hold at least ${shape.minItems} item(s)`
        }
        return null
      case 'ref':
        this.checkObject(value, shape.type, path)
        return null
      case 'union':
        return this.unionProblem(value, shape.of, path)
    }
  }

  /**
   * A union holds when any member does; each member is tried on its own.
   *
   * A trial's checker is thrown away, with the objects it checked, so a `ref`
   * member would be checked again by `walk`. No exported union holds a `ref`;
   * one that does needs the passing trial's objects marked checked here.
   */
  private unionProblem(value: unknown, members: readonly FieldShape[], path: string): string | null {
    const failures: string[] = []
    for (const member of members) {
      const trial = new ShapeChecker()
      trial.checkValue(value, member, path)
      if (trial.problems.length === 0) return null
      // Keep a member's own sub-path (`[1]: …`); drop only the shared prefix.
      failures.push(...trial.problems.map((p) => p.slice(path.length).replace(/^: /, '')))
    }
    return `matches none of its forms (${failures.join('; ')})`
  }

  /**
   * Walk `value` and check every object whose `type` names an exported model
   * and that no field check has covered yet. Parents are visited before their
   * children, so an object a `ref` field already checked is not reported twice.
   */
  walk(value: unknown, path: string): void {
    if (Array.isArray(value)) {
      value.forEach((item, i) => this.walk(item, join(path, i)))
      return
    }
    if (!isRecord(value)) return
    if (!this.checked.has(value) && isLedgerTypeName(value.type)) {
      this.checkObject(value, value.type, path)
    }
    for (const [key, child] of Object.entries(value)) this.walk(child, join(path, key))
  }
}

/**
 * Every shape problem of one parsed ledger line, as `path: problem` strings.
 * An empty list means the line is a well-formed `CaseLedgerEntry`.
 */
export function ledgerLineProblems(line: unknown): string[] {
  const checker = new ShapeChecker()
  checker.checkObject(line, 'CaseLedgerEntry', '')
  if (isRecord(line)) checker.walk(line.payloadSnapshot, 'payloadSnapshot')
  return checker.problems
}

/**
 * Every problem of one value against one field shape. `ledgerLineProblems`
 * reaches only the shapes the exported models use; this checks any shape the
 * exporter can write, such as a bound no exported field has yet.
 */
export function valueProblems(value: unknown, shape: FieldShape, path = 'value'): string[] {
  const checker = new ShapeChecker()
  checker.checkValue(value, shape, path)
  return checker.problems
}
