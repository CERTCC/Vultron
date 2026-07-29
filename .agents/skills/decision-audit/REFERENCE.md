# Decision Audit — Reference

Scoring rubric, commands, and the adversarial re-derivation prompt for the
`decision-audit` skill. Load this in Phase 1.

---

## Landmine risk score

Risk = **blast radius** × **confidence deficit**. Neither factor alone is a
landmine: a low-confidence decision nobody depends on is cheap to fix later; a
rock-solid decision with 20 dependents is not a problem. The danger is a shaky
decision that many things quietly build on.

Compute an ordinal score per ADR. There is no need for false precision — sort
by blast radius within confidence-deficit tiers.

### Confidence-deficit tiers (highest risk first)

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
