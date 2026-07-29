# Archived ADRs

Retired decision records live here — those whose status is `deprecated` or
`superseded by <link>`. They are moved out of the parent `docs/adr/` directory
so that agents loading context (`orient-agent` reads `docs/adr/index.md`;
`deepen-context` reads the live `docs/adr/` set) do **not** encounter outdated
decisions in the default sweep. Finding an archived decision requires
deliberately looking here.

Each archived ADR:

- keeps its original filename;
- carries `status: superseded by <link-to-replacement>` (or `deprecated` with a
  rationale) in its frontmatter;
- is listed in `docs/adr/index.md` under **Superseded / Archived ADRs** with a
  forward link to its replacement.

See ADR-0041 and `notes/specs-vs-adrs.md` for the status vocabulary and the
`decision-audit` skill for how retirement decisions are made. This directory is
currently empty apart from this README — no ADR has yet been retired.
