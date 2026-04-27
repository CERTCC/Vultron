You are reviewing this codebase for adherence to the architecture described in
`notes/architecture-ports-and-adapters.md`, as refined in
`specs/architecture.yaml`. Additional notes from a previous review are found
in `archived_notes/architecture-review.md`. Read those document in full
before examining any code. Use it as your ground truth throughout.

### Context to hold in mind

This project has a specific layering challenge worth understanding before you
start:

The case management domain was designed first. Activity Streams 2.0 was later
adopted as the wire format because it has a 1:1 semantic match with the domain
vocabulary. This means AS2 concepts and domain concepts look very similar — they
use the same words for the same things. The prototype may have allowed this
similarity to blur the boundary between the wire layer and the domain. Your job
is to find where that blurring has occurred.

The architecture defines three distinct concerns that must not be mixed:

1. **Structural AS2 parsing** — is this valid AS2 JSON? Lives in `wire/as2/`.
2. **Semantic extraction** — what does this AS2 message mean in domain terms?
   Also lives in `wire/as2/extractor.py`, and only there.
3. **Domain logic** — what do we do about it? Lives in `core/`. Operates on
   domain types only, with no awareness of AS2.

### What to look for

Source code is in `vultron/`. Note that `vultron/core`, `vultron/wire`, and  
`vultron/adapters` are partially populated, so you will first need to identify
how existing files will map in to the new structure.

**In `core/` files:**

- Any import from `wire/`, `pyld`, `rdflib`, or any AS2/JSON-LD library. This is
  a hard violation — the domain must have zero wire format awareness.
- Any import from adapter frameworks: `fastapi`, `typer`, `mcp`, `httpx`,
  `celery`, `nats`.
- Functions that accept raw dicts, AS2 types, or JSON strings instead of domain
  Pydantic models.
- Direct instantiation of DB connections, HTTP clients, or queue clients (these
  should come in via injected port implementations).
- AS2 vocabulary appearing in logic — checking `activity.type == "Offer"` or
  similar inside a service function. That check belongs in the extractor, not
  the domain.
- `MessageSemantics` being defined outside `core/models/events.py`.

**In `wire/as2/` files:**

- Domain logic appearing here — case handling, participant authorization,
  journal sequencing. If the wire layer is making decisions about what to *do*
  with a message, that logic belongs in the core.
- AS2-to-domain vocabulary mapping scattered across multiple files. The mapping
  must be consolidated in `extractor.py`. If you find `activity.type` being
  inspected anywhere else in the wire layer, flag it.
- The serializer constructing domain objects rather than translating them — the
  domain should produce events, the serializer converts them to AS2.

**In `adapters/driving/` (especially the HTTP inbox):**

- AS2 parsing or semantic extraction happening inline inside the endpoint
  handler, mixed with dispatch logic. These should be separate stages: parse →
  extract → dispatch.
- Domain logic appearing in the endpoint handler.
- The endpoint inspecting AS2 activity fields to decide what to do — that's the
  extractor's job.

**In `adapters/connectors/`:**

- Case handling logic, authorization decisions, or journal management inside a
  connector plugin. Connectors must only translate between tracker events and
  domain events.
- Connectors being imported directly by core rather than discovered via entry
  points.

**In tests:**

- Core tests that instantiate HTTP clients, parse AS2 JSON, or invoke FastAPI
  endpoints. Core tests should call service functions directly with domain
  Pydantic objects.
- Wire tests that invoke domain services — wire tests should stop at the
  extractor output.
- Tests that are impossible to run without a real database or queue (indicates
  port injection isn't being used).

### The specific thing to locate

There is likely a place in the codebase — probably in or near the inbox
handler — where AS2 parsing, semantic matching, and handler dispatch are mixed
together. The architecture calls for these to be three distinct stages. Find
that code, describe exactly what is mixed, and specify how it should be
separated.

### Output format

Output your findings into `archived_notes/architecture-review.md`, updating the
existing content to reflect your current findings. You can remove prior
findings that have been addressed, but do not remove prior findings that are
not yet addressed in the code. Produce your findings in three sections:

#### 1. Violations

For each violation:

- File and function/line
- Which rule it breaks (by number, from
  `notes/architecture-ports-and-adapters.md` and `specs/architecture.yaml`)
- Severity: Critical (core depends on wire format or framework), Major (logic in
  wrong layer), Minor (convention or organisation)
- One sentence explaining why it is a violation

#### 2. Remediation Plan

For each Critical or Major violation:

- What moves where
- Any new abstraction needed (new file, new interface, new type)
- Rough sketch of corrected code if helpful
- Dependencies between remediations — if B requires A first, say so explicitly

#### 3. What Is Already Clean

Note code that already follows the architecture correctly. Establishes which
patterns to replicate and confirms the review is balanced.

### Tone

Be specific. "The core has too much responsibility" is not useful. "Line 47 of
`adapters/driving/http_inbox.py` inspects `activity.type` to select a handler,
which is Rule 4 violation" is useful. If something is ambiguous — genuinely
unclear whether it belongs in the wire layer or the domain — say so and explain
the ambiguity rather than guessing.

DO NOT MODIFY ANY CODE. This is a review, not a refactor. Your job is to
identify what's wrong, not to fix it.
