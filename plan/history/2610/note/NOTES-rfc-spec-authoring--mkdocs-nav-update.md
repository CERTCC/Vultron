---
source: NOTES-rfc-spec-authoring--mkdocs-nav-update
timestamp: '2026-10-01T19:34:46.487029+00:00'
title: 'rfc-spec-authoring: Nav instructions for publishing the spec'
type: note
---

**Archiving reason**: Superseded by delivered work: mkdocs.yml carries the Protocol Specification nav entry and draft-vultron-spec.md is deleted. The paginated nav is described in notes/rfc-spec-authoring.md § "Page Map" (#4059).

**Superseding pointer**: notes/rfc-spec-authoring.md; docs/reference/vultron-spec/

---

## MkDocs Nav Update

When the spec is ready for publication, replace:

```yaml
- Draft Protocol Specification: 'reference/draft-vultron-spec.md'
```

with:

```yaml
- Protocol Specification: 'reference/vultron-spec/index.md'
```

and delete `docs/reference/draft-vultron-spec.md`. Also add the
`includes/` subdirectory to `not_in_nav` if it is created:

```yaml
not_in_nav: |
  ...
  reference/vultron-spec/includes/*
```
