---
source: NOTES-docker-build--delivered-build-observations
timestamp: '2026-09-17T17:21:04.252238+00:00'
title: Delivered Docker build observations (scoping, caching, multi-stage)
type: note
---

**Archived:** 2026-09-17
**Reason:** (a) delivered; docker/Dockerfile + docker/.dockerignore match prescribed scoping/caching/multi-stage
**Superseded by:** docker/Dockerfile; docker/.dockerignore

---

## Image Content Scoping

- The `api-dev` and `demo` images do **not** need the documentation tree
  (`docs/`). Excluding it from the build context and/or via `.dockerignore`
  reduces context size and avoids unnecessary layer invalidation.
- The `docs` image **does** require the source code: MkDocs uses `mkdocstrings`
  and executes Python code at build time to generate reference documentation
  from docstrings.
- None of the current images require `plan/`, `prompts/`, `specs/`, or `notes/`
  directories. These should be excluded via `.dockerignore`.

### Dependency Installation Layer Caching

Copy `pyproject.toml` and `uv.lock` first, run `uv sync --frozen`, then copy
the rest of the source. This allows Docker to reuse the dependency layer on
rebuilds that only change source files.

Use BuildKit cache mounts for the uv/pip cache to speed up repeated installs.
Use a consistent `id` across all stages so they share one backing store:

```dockerfile
RUN --mount=type=cache,id=uv-cache,target=/root/.cache/uv \
    uv sync --frozen
```

When a stage runs as a non-root user (e.g. `vscode`, uid=1000), add
`uid=NNN,gid=NNN` so that user can read the cache populated by root stages.
The `target` path should be the non-root user's cache location:

```dockerfile
RUN --mount=type=cache,uid=1000,gid=1000,id=uv-cache,target=/home/vscode/.cache/uv \
    uv sync --frozen --dev
```

The `id` is what links the mounts — BuildKit serves the same backing store
regardless of which `target` path each stage mounts it at.

### Multi-Stage Build

Consider splitting the Dockerfile into a `dependencies` stage and a `runtime`
stage. The `dependencies` stage installs all packages; the `runtime` stage
copies from it. This avoids re-running dependency installs when only
application code changes.
