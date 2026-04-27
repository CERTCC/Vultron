# Duration Specification

## Overview

Requirements for a canonical representation of **time durations independent
of start/end timestamps**. Applicable wherever a duration must be exchanged
in JSON (e.g., embargo policy records, embargo initialization at case
creation).

**Source**: `wip_notes/duration-spec.md`
**Cross-references**: `specs/embargo-policy.md` (EP-01-002, EP-01-003),
`specs/code-style.md` CS-13-005 (datetime wire format)

---

## Representation Format

- `DUR-01-001` (MUST) Durations MUST be represented as ISO 8601 duration
  strings using the `P[n]DT[n]H[n]M[n]S` format
  - Example: `"P90D"` for ninety days
- `DUR-01-002` (MUST) Duration strings MUST be serialized as JSON strings,
  not as numbers
- `DUR-01-003` (MUST) Durations represent **absolute elapsed time**, not
  calendar-relative intervals; `P1D` means exactly 86400 seconds, with no
  DST or calendar adjustment implied

---

## Allowed Grammar (Restricted ISO 8601 Subset)

To eliminate ambiguity, Vultron constrains ISO 8601 durations as follows.

### Allowed Units

- `DUR-02-001` (MUST) Only the following units are permitted in duration
  strings:
  - `D` — Days
  - `H` — Hours (time component)
  - `M` — Minutes (time component only — not the date-part month designator)
  - `S` — Seconds
- `DUR-02-002` (MUST NOT) The following units MUST NOT appear in Vultron
  duration strings because they introduce calendar ambiguity:
  - `Y` (years) ❌
  - `M` as a date-part (months) ❌
  - `W` (weeks) ❌

### Formal Grammar (EBNF)

```ebnf
duration  = "P" ( date-part [ "T" time-part ] | "T" time-part )

date-part = days
time-part = ( hours | minutes | seconds ) { time-component }

days      = integer "D"
hours     = integer "H"
minutes   = integer "M"
seconds   = number  "S"

integer   = DIGIT { DIGIT }
number    = integer [ "." DIGIT { DIGIT } ]
```

Valid examples: `P90D`, `PT2160H`, `P1DT12H`, `PT30M`, `PT45.5S`

Invalid examples: `P1M` (ambiguous month) ❌, `P1Y` ❌, `P2W` ❌,
`P1DT` (empty time part) ❌

---

## Canonical Form

- `DUR-03-001` (SHOULD) Duration strings SHOULD be normalized to a canonical
  form: prefer the largest unit without remainder
  - `PT2160H` → `P90D`
  - `PT3600S` → `PT1H`
  - `PT90M` → `PT1H30M`
  - Canonicalization is RECOMMENDED but not REQUIRED for interoperability
- `DUR-03-002` (SHOULD) Embargo policy durations SHOULD use only integer day
  units when possible; mixed day/time representations SHOULD be avoided
- `DUR-03-003` (SHOULD NOT) `P0D` SHOULD NOT be used to express a
  zero-length duration; prefer `PT0S` for explicitness

---

## Validation Requirements

- `DUR-04-001` (MUST) Implementations MUST reject duration strings containing
  disallowed units: `Y`, date-part `M`, `W`
- `DUR-04-002` (MUST) Implementations MUST reject malformed ISO 8601 duration
  strings
- `DUR-04-003` (MUST) Implementations MUST reject empty duration strings
  (`"P"` or `"PT"`)
- `DUR-04-004` (MUST) A valid duration MUST contain at least one component

---

## Python / Pydantic v2 Mapping

- `DUR-05-001` (SHOULD) Duration fields SHOULD use `datetime.timedelta` as
  the internal Python representation
- `DUR-05-002` (MUST) Duration fields MUST serialize to ISO 8601 duration
  strings at the JSON wire layer; the internal `timedelta` MUST NOT be
  serialized as a plain number

Reference implementation using `isodate`:

```python
from datetime import timedelta
from pydantic import BaseModel, field_validator, field_serializer
import isodate


class VultronDurationModel(BaseModel):
    duration: timedelta

    @field_validator("duration", mode="before")
    @classmethod
    def parse_duration(cls, v):
        if isinstance(v, str):
            parsed = isodate.parse_duration(v)
            if not isinstance(parsed, timedelta):
                raise ValueError("Duration must not include years or months")
            return parsed
        return v

    @field_serializer("duration")
    def serialize_duration(self, v: timedelta):
        return isodate.duration_isoformat(v)
```

---

## Interval Composition

Durations may be combined with RFC 3339 timestamps to form intervals.

- `DUR-06-001` A duration-only embargo policy field MUST be interpreted as a
  relative offset from a context-specific anchor (typically case creation
  time)
- `DUR-06-002` When combined with a start timestamp, the end time is
  `end = start + duration`
- `DUR-06-003` Timestamps used in interval composition MUST conform to RFC
  3339 (UTC recommended); local timezone arithmetic is NOT RECOMMENDED

---

## Embargo Duration Semantics

- `DUR-07-001` Specific embargo end times on cases MUST be declared as
  event intervals with unambiguous start and end timestamps, not as
  durations alone
- `DUR-07-002` At case creation (RM.RECEIVED), if no embargo end time is
  established, the case creation process SHOULD apply the actor's default
  embargo duration (from the actor profile) to the case creation timestamp
  to establish the initial embargo end time
  - Per ADR-0015, case creation occurs at `Offer(Report)` receipt
    (RM.RECEIVED), not at validation (RM.VALID)
  - DUR-07-002 is-refined-by CM-12-004
- `DUR-07-003` When a default embargo duration is applied at case creation,
  this application MUST be logged at INFO level to ensure visibility in logs.
  The resulting `CaseStatus.em_state` MUST be `EM.ACTIVE` (not `EM.PROPOSED`);
  see `specs/embargo-policy.md` EP-04-001.
- `DUR-07-004` An embargo end time MUST be established before the case
  transitions to RM.VALID
  - If the default embargo was not initialized at receipt (DUR-07-002),
    the validate-report process MUST ensure an embargo exists via an
    `EnsureEmbargoExists` check before completing validation
  - DUR-07-004 depends-on DUR-07-002
  - DUR-07-004 is-implemented-by CM-12-004

---

## Verification

### DUR-01-001, DUR-01-002, DUR-01-003 Verification

- Unit test: `P90D` parses to `timedelta(days=90)` (exactly 86400×90 s)
- Unit test: Serialized form is `"P90D"` string, not a number

### DUR-02-001, DUR-02-002 Verification

- Unit test: `P1Y` raises `ValueError`
- Unit test: `P1M` (date-part month) raises `ValueError`
- Unit test: `P2W` raises `ValueError`
- Unit test: `P1DT12H` validates successfully

### DUR-04-001 through DUR-04-004 Verification

- Unit test: Empty string raises `ValueError`
- Unit test: `"P"` and `"PT"` raise `ValueError`
- Unit test: Malformed string (e.g., `"90D"`) raises `ValueError`

### DUR-05-001, DUR-05-002 Verification

- Unit test: Round-trip `timedelta(days=90)` → `"P90D"` → `timedelta(days=90)`
- Unit test: JSON serialization produces string, not integer

---

## Related

- **Embargo Policy**: `specs/embargo-policy.md` (uses duration fields)
- **Datetime Format**: `specs/code-style.md` CS-13-005 (RFC 3339 wire format)
- **Technology Stack**: `specs/tech-stack.md` IMPLTS-02-003 (isodate library)
