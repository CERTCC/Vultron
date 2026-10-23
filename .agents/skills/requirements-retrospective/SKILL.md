---
name: requirements-retrospective
description: Analyze specs/ and notes/ git history over a time window to produce a requirements-discovery retrospective — what requirements were discovered, how they were found, and what that reveals about protocol specification completeness. Groups findings by discovery mechanism and conformance layer (L1–L4). Intended for architects and protocol spec authors, not sponsor reporting. Use when the user asks for a requirements retrospective, specification gap analysis, "what did we learn about requirements", or wants to understand what the implementation revealed about the protocol.
---

# Requirements Retrospective

Internal retrospective for architects and protocol authors: what requirements
did the codebase teach us over a given period, and what layer of the conformance
stack did each finding belong to?

## Quick start

```text
/requirements-retrospective          # defaults to two weeks
/requirements-retrospective May 2026 # specific month
/requirements-retrospective 2026-07-01..2026-07-28
```

## Conformance layer reference

Tag each finding with one of these layers before writing the narrative:

| Layer | What it covers | Enforceable via |
|---|---|---|
| **L1 — Syntax** | Well-formed messages, wire format | Spec validator, schema |
| **L2 — Semantic** | Correct state transitions per message | VP + transitions.md |
| **L3 — Behavioral** | Correct observable outputs: right messages emitted, right states reached, given (input state + received event) | RMB / EMB / CSB spec groups |
| **L4 — Process** | Correct internal ordering: effects before persist, preconditions before state write | Reference implementation only |

Most implementation-driven discoveries land at L3 or L4. If a finding is at L1
or L2 it likely represents a *protocol* correction, not just an implementation
gap — flag it explicitly.

## Analysis workflow

### Step 1 — Gather the raw history

```bash
# Determine window bounds
SINCE="2026-07-14"  # adjust to requested window

# New spec items
git log --since="$SINCE" --oneline -- specs/
git log --since="$SINCE" --oneline -- notes/

# What group titles were added (new requirements areas)
OLDEST=$(git log --since="$SINCE" --oneline -- specs/ | tail -1 | cut -d' ' -f1)
git diff ${OLDEST}^..HEAD -- specs/ | grep "^+  title:" | sort -u

# Which notes files were created or grew significantly
git diff --stat ${OLDEST}^ HEAD -- notes/
```

### Step 2 — Read the substantive new content

For notes files with large additions (>100 lines added), read the file to
understand what design decision or failure story it captures. Focus on:

- Problem statement sections (what broke or was missing)
- "Why this matters" / rationale paragraphs
- Named bugs (DR-series) and protocol gaps
- Exceptions and edge cases to stated rules (these are requirements too)

For spec groups, the rationale field is the key — it records what failure
motivated the requirement.

### Step 3 — Classify each finding

For each new spec group or major notes section, determine:

1. **Discovery mechanism** — how was this requirement found?
   - *Running code*: a test or demo produced wrong output
   - *Multi-actor scenario*: only visible at 3+ actor boundary
   - *Formal review*: PR review or spec audit caught it
   - *Architectural audit*: deliberate layer-boundary analysis
   - *Protocol analysis*: reading the spec revealed an ambiguity

2. **Conformance layer** — L1 / L2 / L3 / L4

3. **Was the protocol itself wrong, or just under-specified?**
   - Under-specified: the protocol is consistent; we just hadn't written the requirement
   - Wrong: an existing protocol rule was incorrect or ambiguous at the wire level

### Step 4 — Group and synthesize

Organize findings into thematic clusters (don't force them into the mechanism
taxonomy if a different grouping is more natural). For each cluster:

- State what we now know that we didn't
- Name the discovery mechanism
- Tag the conformance layer
- Note if the finding revealed a protocol-level gap vs. an implementation gap

### Step 5 — Write the narrative

Structure:

1. **What the window covered** (1–2 sentences: what was being built)
2. **Thematic clusters** (one section per cluster, ~1 paragraph each)
3. **Cross-cutting observation** — does the pattern of findings say anything
   about where specification completeness stands? (e.g., "L3/L4 dominates →
   protocol policy is solid, behavioral contracts are not")
4. **Anything that is a protocol finding** (L1/L2, or wire-level ambiguity)
   called out separately — these may warrant ADR updates or upstream spec work

## Triage heuristics

**High signal findings** (always include):

- Any finding that changed a spec group's RFC 2119 level (e.g., MAY → MUST)
- Any finding that introduced an exception to an existing rule
- Any wire-level ambiguity (two messages that are structurally indistinguishable)
- Any finding only discoverable at multi-actor boundary
- Any L4 ordering requirement (effects-before-persist, precondition sequencing)

**Lower signal** (include if they cluster into a pattern, skip individually):

- Spec format / kind classification fixes
- Typo corrections in rationale text
- Notes file splits and reorganizations (structural, not content)
- Renames and relabeling (unless the rename reflects a conceptual correction)

## Notes on the L3/L4 distinction

L3 (behavioral) requirements are *observable from outside*: a conforming
implementation emits the right messages in the right order given a state+event
pair. An independent implementor can test against them with a conformance harness.

L4 (process) requirements are only enforceable via a reference implementation
because they describe internal ordering — e.g., "write effects before persisting
the ledger entry." They show up as bugs when violated, but a black-box test
cannot distinguish correct from incorrect internal ordering if the outputs happen
to match. Call these out explicitly: they represent requirements that cannot be
captured in a conformance spec and must live in documentation + code review.
