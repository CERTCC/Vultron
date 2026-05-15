# Project Report — Reference

## Report Structure

```markdown
# Vultron Project — <Period> Work Sponsor Report

## Executive Summary

2–4 sentences covering:
- Overall productivity characterization
- The 2–4 major themes of the period
- Any notable caveats (work in progress, issues discovered post-period)

---

## <Theme 1 Heading>

...

## <Theme 2 Heading>

...

[4–7 theme sections total]

---

*Report covers: <start> through <end> |
Repository: [CERTCC/Vultron](https://github.com/CERTCC/Vultron)*
```

---

## Tone Guidelines

**Audience**: work sponsors who are not familiar with the internal
codebase. They care about:

- What the system can do **now** that it couldn't before
- What is working more reliably or efficiently
- What is still in progress or has caveats
- General health of the project (test coverage, dependency hygiene)

**Do**:

- Lead with capabilities and user-visible outcomes
- Use plain language; briefly explain any necessary technical term
- Note when something is "in progress" or "partially complete"
- Be accurate about caveats — do not oversell

**Don't**:

- Reference internal module names, class names, or file paths
- Use unexplained acronyms (BT, EM, RM, AS2, etc.) without a brief gloss
- Claim something is fully functional if issues were found post-close
- Include every commit; focus on the 5–10 most significant changes

---

## Theme Grouping Heuristics

Group changes by **what improved for users or developers**, not by
internal code location. Common groupings for Vultron:

| Theme label | What belongs here |
|---|---|
| Protocol automation | Behavior Tree automation, reduced manual steps |
| Multi-actor scenarios | Demo reliability, new scenarios, integration tests |
| API / architecture | New ports, facades, cleaned boundaries |
| Specification infrastructure | Spec format, lint, CI, machine-readability |
| Developer tooling / agents | Skills, history management, agentic workflow |
| Configuration | Config format, YAML migration, settings |
| Bug fixes | Reliability fixes, error handling |
| Documentation | Docs site, versioning, reference fixes |
| Dependencies | Automated dependency bumps (keep brief) |

---

## PR Link Format

Always link significant PRs inline:

```markdown
See [PR #NNN](https://github.com/CERTCC/Vultron/pull/NNN).
```

For dependency bumps, a single aggregate sentence is sufficient:

> 20+ automated dependency bumps were merged cleanly during the period,
> including updates to `pydantic`, `fastapi`, `uvicorn`, and `mypy`.

---

## Output Path and Filename

Reports live in `plan/history/<YYMM>/report/` where `YYMM` is derived from
the **end date** of the period (capped at today for open-ended periods):

```text
plan/history/<YYMM>/report/project-report-<YYYYMMDD>-<YYYYMMDD>.md
```

Examples:

├── implementation/         # Completed implementation tasks
├── priority/               # Completed priority groups
├── idea/                   # Ingested ideas
└── learning/               # Bug fixes, lessons learned, code reviews

`idea/` entries rarely need individual mention unless they drove major work.
