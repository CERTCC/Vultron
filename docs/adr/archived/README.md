---
stakeholder_type: [project-contributor]
---

# Archived ADRs

Retired decision records live here — those whose status is `deprecated` or
`superseded` (+ `superseded_by:` field). They are moved out of the parent `docs/adr/` directory
so that agents loading context (`deepen-context` reads `docs/adr/index.md`
and the live `docs/adr/` set) do **not** encounter outdated
decisions in the default sweep. Finding an archived decision requires
deliberately looking here.

Each archived ADR:

- keeps its original filename;
- carries `status: superseded` with a `superseded_by:` field (or `deprecated` with a
  rationale) in its frontmatter;
- is listed in `docs/adr/index.md` under **Superseded / Archived ADRs** with a
  forward link to its replacement.

See ADR-0043 and `notes/specs-vs-adrs.md` for the status vocabulary and the
`decision-audit` skill for how retirement decisions are made.

Do not restate the contents of this directory here — a count or a "currently
empty" claim goes stale the moment an ADR is retired (MS-16-001). The directory
listing is the record. `docs/adr/index.md` § **Superseded / Archived ADRs** is
the index.
