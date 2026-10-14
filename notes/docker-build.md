---
title: Docker Build Notes
status: active
kind: guidance
description: >
  Rules for changing the Vultron Docker images and docker-compose files: which
  `.dockerignore` applies, how to keep paths out of runtime stages without
  stripping them from the devcontainer, and the order to work through when a
  build is slow.
related_notes:
  - notes/devcontainer-tooling.md
  - notes/codebase-structure.md
---

# Docker Build Notes

## The Root `.dockerignore` Governs Every Stage

Both compose files build with `context: ..`, the repository root, so the root
`.dockerignore` applies to every stage of `docker/Dockerfile`, including the
`dev` stage behind the devcontainer. `docker/.dockerignore` is not read: Docker
only looks for `.dockerignore` at the context root, or for
`Dockerfile.dockerignore` beside the Dockerfile.

List in the root file only paths that **no** stage needs. A path that runtime
images should skip but the `dev` stage needs goes in a per-stage
`COPY --exclude=` instead; excluding it in `.dockerignore` silently strips it from
the devcontainer. The root file's header comment states the full rule.

## Slow-Build Checklist

Work through these in order:

1. **Build context size**: exclude `.git`, `.venv`, `node_modules`, `build` and
   large data directories (within the rule above).
2. **Layer cache reuse**: copy dependency files and install dependencies before
   `COPY`ing the source, as the `dep-layer` stage does.
3. **BuildKit cache mounts**: `--mount=type=cache` for package caches (the
   `uv-cache` mounts).
4. **CI layer cache**: `--cache-to`/`--cache-from` with a registry backend.
5. **Stage targeting**: build only the needed stage with `--target`.
6. **Slim base images**: `python:X.Y-slim`; combine `apt-get` install and cleanup
   in one `RUN`.
7. **No tests in the build**: run tests in a separate CI job.

Health-check coordination between demo containers is in
[notes/codebase-structure.md](codebase-structure.md) § "Docker Health Check
Coordination".
