---
status: accepted
status_override: >-
  Decided by the maintainer in the planning interview for #5964 on 2026-11-13.
date: 2026-11-13
created: 2026-11-13
updated: 2026-11-13
revision: 1
deciders: Allen D. Householder
consulted: Vultron maintainers
informed: Vultron implementers
stakeholder_type: [project-contributor]
# CaseReading and CaseReader are named before the port Task (#6358) builds them.
lint_suppress: [phantom_symbol_ref]
---

# A Case Reading Reports Its Inferences and What Its Source Cannot Observe

## Context and Problem Statement

A `CaseReader` adapter returns an outside system's case as a core case ledger, together with the facts it could not translate ([ADR-0191](0191-an-outside-system-reaches-the-core-through-a-read-only-case-reader-port.md)).
That record leaves the ledger unmarked: a translated ledger cannot be told from a native one by looking at it.

Mapping VINCE onto Vultron (#5964) showed that an outside system rarely states the steps Vultron's state machines need.
VINCE says a vendor is "Affected" and never says the vendor accepted the report.
VINCE sets a planned publication date and has no concept of embargo consent at all.
A translation that writes only what the source states leaves most participant states at their start values, and the analysis then has nothing to say.
A translation that writes the implied states as plain ledger facts lets the analysis present an inference as certain.

A second gap is quieter.
Some facts an outside system never exposes for any case: VINCE's API has no fix-ready, fix-deployed, notification or viewed events.
An analysis that reads "no such entry in the ledger" as "it did not happen" scores a case on data its source could never supply.

What does a reader return, so that the analysis can tell a stated fact from an inferred one, and an absent fact from an unobservable one?

## Decision Drivers

- The projection and the measures read a translated ledger exactly as a native one (ADR-0191, points 3 and 4), so the ledger itself stays unmarked.
- An analyst must be able to see, for every state the analysis shows, whether the source stated it or the translation inferred it.
- An absence the source could never fill must read as unknown, not false.
- Each outside system has different gaps, so the rule is the port's, not one adapter's.

## Considered Options

- Inferred states written as plain ledger facts
- Inferred facts never written: everything implied is returned untranslated
- Inferred states written, and the reading lists each inference and each unobservable fact beside the ledger

## Decision Outcome

Chosen option: "Inferred states written, and the reading lists each inference and each unobservable fact beside the ledger", because it keeps the ledger native-shaped while letting the analysis and its reader see where each state came from.

1. **A case reading has five parts.** A reader returns, for one outside case:
    1. the translated case ledger, unmarked;
    2. a citation per entry, naming the outside-system record it came from, kept beside the entry;
    3. the inferences: each entry whose state the source implied rather than stated, with the mapping rule that produced it and a caveat in words;
    4. the untranslated facts: each fact the reader saw and did not translate, with a reason;
    5. the unobservable facts: what the source system never exposes, for any case.
2. **An inference is a written rule, not a guess.** A person decides each mapping rule before an adapter applies it, and the rule has a stable identifier the inference names.
3. **Unobservable is the adapter's declaration.** An adapter declares once what its source cannot observe. Each reading copies that declaration, so a consumer needs nothing but the reading.
4. **Untranslated is per case, with a reason.** A fact the source holds for this case but the adapter could not turn into an entry carries why: an unknown value, no counterpart, a contradiction between the rule's inputs, or no time to place it at.
5. **Absent and unobservable read as unknown.** A consumer reads a state dimension or event the reading declares unobservable as unknown, never as false.
6. **A translated entry's times are the source's own.** Both the commit stamp and the claimed publication time of a translated entry come from the outside-system record. An act whose record states no time takes a time the source does state, named by the adapter's mapping rule (for VINCE, the case's creation time), and is listed as an inference. A reader never reads a clock to fill one ([ADR-0176](0176-an-act-reads-the-clock-once-at-its-edge.md)).

### Consequences

- Good, because the dashboard can print "Accepted (inferred from Affected)" and link the rule that produced it.
- Good, because a missing fix in a VINCE case reads as "VINCE cannot say", not as "no fix exists".
- Good, because the ledger stays the shape the projection and the measures already read, so ADR-0191's single path holds.
- Bad, because a reading is a larger object than a ledger and a list, and every adapter must declare its blind spots.
- Neutral, because an entry's receipt timestamp holds the outside system's time in a reading, not a time a Vultron node generated. That is safe for the same reason ADR-0191 gives: a reading is not stored and does not enter a protocol path.

## Validation

`specs/case-reader.yaml` states the checkable rules, each citing this record.
A conformance test over every registered `CaseReader` adapter checks each part of the reading.

## Pros and Cons of the Options

### Inferred states written as plain ledger facts

- Good, because it is the simplest result: a ledger and a list of untranslated facts, as ADR-0191 already says.
- Bad, because no consumer can tell an inferred state from a stated one, so an inference is shown as certain.
- Bad, because the rule that produced a state is not traceable from the result.

### Inferred facts never written

- Good, because every ledger fact is one the source stated.
- Bad, because for VINCE most participant states stay at their start values, and the analysis says little about any case.

### Inferred states written, with inferences and unobservable facts listed

- Good, because the analysis has states to reason over and the reader can see which are inferred.
- Good, because blind spots are declared, so absence is not scored as fact.
- Bad, because each adapter carries a declaration and a set of named rules to keep in step with its mapping.

## More Information

Planned in #5964, with the maintainer, on 2026-11-13.
Extends ADR-0191, whose point 5 (nothing untranslatable is dropped) this record refines, and whose consequence that a translated ledger cannot be told from a native one this record answers without marking the ledger.
The VINCE rules are in the VINCE crosswalk (`docs/reference/vince_crosswalk.md`).

Generated spec requirements: `case-reader.yaml` CRD-02, CRD-03.
