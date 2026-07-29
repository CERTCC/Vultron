# Decision Audit — Reference

Scoring rubric, commands, and the adversarial re-derivation prompt for the
`decision-audit` skill. Load this in Phase 1.

---

## The inventory helper

Phase 1 is computed by a helper so the ranking is deterministic rather than
hand-run:

```bash
uv run python -m vultron.metadata.adr.decision_audit_inventory
uv run python -m vultron.metadata.adr.decision_audit_inventory --top 20
uv run python -m vultron.metadata.adr.decision_audit_inventory --kind spec --json
```

It scores **ADRs and spec groups** together and prints a risk-ranked table.
The manual commands below are the fallback if the helper is unavailable, and
document what each signal means.

## Landmine risk score

Risk = **(blast radius + 1) × weighted confidence deficit**. Neither factor
alone is a landmine: a low-confidence decision nobody depends on is cheap to
fix later; a rock-solid decision with 20 dependents is not a problem. The
danger is a shaky decision that many things quietly build on.

The deficit is a **weighted sum of the signals that fired**, not a raw count —
a signal a prior investigation already tied to real rework (a requirement whose
source ADR moved; an ADR whose prose contradicts its status) weighs 3; a
not-accepted status or an unverified-assertion cluster weighs 2; a bare mention
in learnings weighs 1. The `+1` blast-radius floor keeps a strong-signal
candidate with no measured dependents above pure noise. A candidate with no
deficit signal scores 0.

### ADR confidence-deficit tiers (highest risk first)

1. **Contradicted** — `status: accepted` but prose carries provisional markers,
   OR index section disagrees with frontmatter, OR the code demonstrably
   violates a layer/invariant the ADR asserts. The presentation actively lies
   about how settled the decision is. *Highest risk — agents trust it fully.*
2. **Unsettled-but-presented-as-live** — `status` blank or `proposed`, yet the
   ADR is referenced by many specs/notes as though decided.
3. **Amended-after-acceptance** — the decision already needed one correction;
   treat remaining claims as suspect until re-derived.
4. **Named in correction history** — a learning entry or revert already
   flagged this decision or a dependent.
5. **Clean** — `accepted`, no contradictions, few or well-scoped dependents.
   Skip unless the user asks for an exhaustive pass.

### Spec-group confidence-deficit signals

Same model, applied to a requirement group. These were validated to
*discriminate* on the real corpus (each fires on a handful of groups, not most):

1. **Derives from a non-accepted ADR** (weight 3) — a requirement's `adr:` edge
   points at an ADR whose status is not plain `accepted`. The premise the group
   was built on has moved. *Independently rediscovers CM-15 (the ISSUE-1272
   landmine) and the LST-\* group (all deriving from `proposed` ADR-0033).*
2. **`testable: false` cluster** (weight 2) — ≥2 non-testable requirements with
   no behavioral steps: assertions agents take on faith, unverifiable in code.
3. **Cites a superseded/archived ADR or note** (weight 2) in rationale.
4. **Purely prototype-scoped** (weight 1) group that production code depends on.
5. **Named near a problem word** (weight 1) in learnings/history.

### Rejected signals (do not use — they don't discriminate)

- **"No `@pytest.mark.spec` coverage"** — only ~15 of ~2200 spec items carry the
  marker, so this fires on ~99% of groups. It flags everything, i.e. nothing.
  If per-requirement test-coverage tracking ever becomes widespread, revisit.

---

## Commands

### Blast radius (reference count per ADR)

```bash
grep -rioE 'ADR-00[0-9]{2}' specs/ notes/ \
  | sed -E 's/.*(ADR-00[0-9]{2}).*/\1/' | sort | uniq -c | sort -rn
```

### Status vs. provisional-prose contradiction

```bash
for f in docs/adr/0*.md; do
  st=$(awk -F': ' '/^status:/{print $2; exit}' "$f")
  prov=$(grep -iEc 'formed in sand|not concrete|provisional|forward-looking|will converge|expected to converge|SHOULD refine|status will advance' "$f")
  flag=""
  { [ "$st" = "accepted" ] && [ "$prov" -gt 0 ]; } && flag="  <<< ACCEPTED-BUT-PROVISIONAL"
  { [ -z "$st" ] || [ "$st" = "proposed" ]; } && flag="$flag  <<< NOT-ACCEPTED"
  printf '%-52s status=%-12s prov=%s%s\n' "$(basename "$f")" "$st" "$prov" "$flag"
done
```

### Index-vs-frontmatter drift

Read `docs/adr/index.md` section headers (Accepted / Proposed / Rejected /
Superseded) and compare each ADR's placement against its own `status:` field.
Any mismatch is a Contradicted-tier signal.

### Amended-after-acceptance

```bash
# For a candidate ADR, list commits after its accept date touched the file
git log --follow --format='%ad %h %s' --date=short -- docs/adr/NNNN-*.md
```

### Correction history

```bash
grep -riEl 'ADR-NNNN|<decision keyword>' \
  plan/history/*/learning/ plan/incoming/learnings/ 2>/dev/null
```

### Layer-boundary friction (example probe)

If an ADR/spec describes a construct that should live in a specific layer,
confirm where it actually lives:

```bash
# Does core reference or subclass something the ADR implies is core,
# when it actually lives in demo?
grep -rn 'shape base class\|CallOutPoint\|agent shape' docs/adr notes/ specs/
grep -rn 'class .*CallOutPoint' vultron/core vultron/demo
```

---

## Adversarial re-derivation prompt (Phase 3)

Spawn an `Explore` or `Plan` agent with a prompt shaped like this. The framing
is deliberately skeptical — the agent's job is to build the case *against* the
decision, so the interview does not start from confirmation bias.

> You are auditing architectural decision **ADR-NNNN / spec group XX-NN** in the
> repo at `<path>`. Do **not** assume it is correct. Your job is to argue the
> **counter-case**: given the *current* state of the code and specs, would we
> make this same decision today, and where does the decision's stated premise
> fail to match reality?
>
> Read: the full ADR/spec, every spec whose rationale or edges cite it, the
> dependent notes, and the code that implements it. Then report, with file:line
> citations:
>
> 1. **Premise check** — what does the decision claim as fact? For each claim,
>    is it still true in the code today? Quote the contradicting code/spec.
> 2. **Layer/invariant check** — does the decision assert a boundary or
>    invariant that the implementation violates or that a dependent spec
>    contradicts?
> 3. **Dependents at risk** — which specs/notes/code inherited this premise and
>    would be wrong or misleading if the premise is wrong?
> 4. **Drift** — has the decision been amended before? Do the amendments
>    suggest the remaining claims are also shaky?
> 5. **Verdict hypothesis** — your best guess: still-correct / imprecisely-
>    stated / stale / wrong-from-start, with the single strongest piece of
>    evidence for it.
>
> Report findings only. Do not propose or make edits — a human adjudicates.

**For a spec-group candidate, add these checks:**

> 1. **Code conformance** — does the implementation actually satisfy each
>    requirement in the group, or has the code diverged from what the spec
>    says? Quote the divergence.
> 2. **Internal consistency** — do any two requirements in the group (or a
>    requirement and its source ADR) contradict each other? (This is the
>    CM-15-001 / DEMOMA-07-003 failure mode: a spec step that duplicates or
>    conflicts with what another layer already does.)
> 3. **Moved premise** — if the group derives from an ADR whose status is no
>    longer `accepted`, does the requirement still hold under the ADR's current
>    (or successor) decision?

---

## Verdict → action map (Phase 4/5)

| Verdict | Typical action |
|---|---|
| **(a) still correct** | Status/confidence tidy only; record so it doesn't resurface. |
| **(b) imprecisely stated** | Correct the prose (e.g. pin the layer); amend misleading dependents. |
| **(c) stale / superseded** | `status: superseded` + `superseded_by:` field, move to `docs/adr/archived/`, update dependents, write replacement decision if needed. |
| **(d) wrong from start** | Correct or retire the ADR; fix every dependent that inherited the premise; strongly consider a Concern if the correct decision isn't yet clear. |

Default disposition for (b)/(c) and settled (d): **fix now** in a docs-only PR.
File a `type:Concern` only when real uncertainty about the *correct* decision
remains.
