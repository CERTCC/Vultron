---
title: "An unenforced MUST is invisible to the planning that needs it — the corpus stops looking like it has the rule, so planning re-derives it from scratch"
type: learning
timestamp: "2026-09-22T12:00:00Z"
source: ISSUE-3480
signal: theme-candidate
---

ISSUE-3480's AC-3 asked for "a declared, documented rule" identifying which spec
groups specify a demo scenario. It did the work properly: it enumerated the two
obvious rules, proved each one wrong against the live corpus, and concluded
"**an explicit marker on the group is the likely answer**; if it is, adding one
to every scenario group is part of this AC."

The rule already existed. **MS-13-003**: "A spec group whose items describe a
demo scenario workflow MUST include a `trigger` field with
`type: scenario_start`." **SR-02-018**: "for `scenario_start` triggers, `value`
names the scenario." Together those are exactly the marker AC-3 went looking for
— declared, documented, and in the schema — and the implementation needed no new
field, only `scenario_spec_groups()` to read it.

**Why planning could not see it.** Nothing enforced MS-13-003, so six of the
twelve scenario groups did not carry the marker. A planner reading the corpus for
a pattern therefore saw the marker on half the groups and no rule anywhere:
half-adoption reads as *an inconsistent convention*, which is precisely the thing
you do not build a selector on. The requirement's own text was two files away in
`meta-specifications.yaml`, a file nobody loads when thinking about demo
scenarios.

This is the asymmetry worth naming: **an enforced MUST advertises itself through
100% compliance in the artifacts, and an unenforced one anti-advertises.** A
requirement at 50% adoption is worse than one at 0%, because 0% at least reads as
"not done yet" while 50% reads as "no rule here". The corpus actively misled.

**The second-order cost was nearly a new schema field.** The first design this
session reached for was a purpose-built `scenario:` field on `SpecGroup` — which
would have shipped a *second* spelling of the scenario name alongside
`trigger.value` on the six compliant groups, i.e. the exact drift channel
ADR-0098 exists to close, introduced by the work closing it.

**How to apply.** When an issue asks you to invent a selector, marker, tag, or
naming rule, the compose-before-create search must cover the **meta-spec corpus**
(`spec-registry.yaml`, `meta-specifications.yaml`), not just code and notes:

```bash
PYTHONPATH= uv run python -c "
from pathlib import Path
from vultron.metadata.specs.registry import load_registry
r = load_registry(Path('specs'))
for sid, s in sorted(r.all_specs.items()):
    if sid.startswith(('MS-', 'SR-')) and 'marker' in s.statement.lower():
        print(sid, s.statement[:120])
"
```

Search on the *shape* of the thing ("marker", "trigger", "annotates", "declares
which"), not on the domain word — MS-13-003 never says "registry" or "partition",
so no demo-scenario search finds it.

And when you do find a rule at partial adoption, that is the finding: the gap is
enforcement, not design. Write the check first and let it name the violators,
rather than designing around an inconsistency you have mistaken for an absence.
Adding the marker to all twelve groups here immediately surfaced a *second*
unenforced requirement — MS-13-004's "at least one `BehavioralSpec` with
non-empty `steps`" — which four of those groups also violated. Unenforced
requirements cluster, because whatever left the first one unchecked left its
neighbours unchecked too.

Corroboration needed: one instance. A second witness would be any session whose
issue asks it to design a convention that a `MS-`/`SR-` requirement already
mandates, or that finds a spec requirement at partial adoption with no test.
Suspected siblings: MS-13-001 and MS-13-002 (the BehavioralSpec-vs-StatementSpec
choice) have no ratchet either, so the corpus's format choices are unchecked in
the same way.

Related: [[20260921-3450-a-verification-clause-naming-strict-does-not-verify-a-rendered-link]]
is the nearer queued entry — a requirement whose *verification* clause does not
verify what it names. This one is a requirement with no verification at all, and
the consequence is different in kind: a weak clause lets a defect through, while
a missing clause lets the **requirement itself** disappear from the project's
working knowledge.
