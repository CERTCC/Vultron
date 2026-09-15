---
title: "MV-01-006 says unrecognized activity types dispatch to UNKNOWN, but the parser rejects them with a 422 — the requirement does not say which registry it means"
type: learning
timestamp: "2026-09-14T20:45:00Z"
source: ISSUE-3217
signal: spec-ambiguity
---

Two requirements in the same spec group prescribe opposite handling for what
reads as the same input:

- **MV-01-001** — incoming payloads MUST conform to AS2 structure; verification
  says the inbox handler "rejects payloads missing required AS2 fields (e.g.,
  `type`) with an HTTP 4xx response before dispatch."
- **MV-01-006** — "The activity-type dispatch implementation MUST treat
  unrecognized activity types as dispatching to `UNKNOWN`", with the rationale
  that this "allows the system to log and route unrecognised activities without
  crashing the dispatch pipeline."

Reject at the door, or accept and route to `UNKNOWN`? Both, because **two
different registries are in play and neither requirement names one**:

| Registry | Consulted by | Behaviour on a miss |
|---|---|---|
| AS2 vocabulary (`WIRE_TYPE_MAP`, `VOCABULARY`) | `parse_activity` | `VultronParseUnknownTypeError` → HTTP 422 |
| Semantic pattern registry (`SEMANTIC_REGISTRY`) | `find_matching_semantics` | `MessageSemantics.UNKNOWN` |

`find_matching_semantics`' docstring says it "Returns `MessageSemantics.UNKNOWN`
when the activity type is not registered at all" — using the same phrase,
"activity type is not registered", for the *pattern* registry. But an activity
whose type is absent from the **AS2 vocabulary** never reaches that function:
`parse_activity` rejected it several stages earlier. So MV-01-006 is satisfiable
only under the pattern-registry reading, and is unreachable under the plainer
vocabulary reading a new implementer is more likely to take.

The distinction is not academic. During ISSUE-3217 an activity whose type *was*
vocabulary-recognised (`Accept`) extracted as `unknown` semantics because a
corrupt nested object had been silently downgraded, so the activity matched no
pattern. That is the MV-01-006 path — a recognised type with unmatched semantics
— and it looked exactly like "unrecognized activity type" in the logs. Reading
MV-01-006 as being about the AS2 vocabulary would have pointed the investigation
at the wrong layer entirely.

MV-01-005 and MV-01-007 inherit the same ambiguity: both say "the activity-type
dispatch implementation", and both are `refines` parents of MV-01-006.

**How to apply.** A requirement about an "unrecognized" or "unregistered" type
MUST name the registry it consults. Where a system has more than one lookup on
the same value, the RFC 2119 verb is meaningless without the registry: "reject"
and "route to UNKNOWN" are both correct answers to differently-scoped questions.

Candidate spec work: rewrite MV-01-005/006/007 to say *semantic pattern
registry* explicitly, and add a note to MV-01-001 that vocabulary-level type
resolution is refused at the parse threshold rather than dispatched. Consider
whether `MessageSemantics.UNKNOWN`'s comment ("reserved for activities that
don't fit any of the above semantics") should be quoted in MV-01-006 — it is
already unambiguous where the spec is not.

Related: [[20260903-2824-clp14-15-do-not-name-their-timestamp]] — the same
failure shape, a requirement that constrains one of several similar fields
without naming which.
