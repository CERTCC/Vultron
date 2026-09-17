---
title: Docker Build Notes
status: active
description: >
  Observations and guidance for Vultron Docker image optimization and docker-
  compose configuration.
related_notes:
  - notes/devcontainer-tooling.md
---

# Docker Build Notes

## Project-Specific Build Context Observations

These observations apply specifically to the Vultron Docker images and should
guide any optimization work on `docker/Dockerfile` and
`docker/docker-compose.yml`.

### Base Image Pinning

Pin the base image to a specific digest
(e.g., `python:3.13-slim-bookworm@sha256:...`) to prevent cache misses caused
by upstream image updates during CI runs.

---

## General Build Performance Checklist

When profiling slow Docker builds, address items in this order:

1. **Build context size** — Add a `.dockerignore` excluding `.git`,
   `node_modules`, `.venv`, `build`, large test/data directories, and the
   directories listed above.
2. **Layer cache reuse** — Ensure dependency files are copied before source
   and that dependency install runs before `COPY . /app`.
3. **BuildKit cache mounts** — Use `--mount=type=cache` for package caches.
4. **CI layer cache** — Use `--cache-to`/`--cache-from` with a registry
   backend in CI to persist cache across jobs.
5. **Stage targeting** — Build only the needed stage during iterative work
   with `--target`.
6. **Slim base images** — Prefer `python:X.Y-slim` over full images; combine
   `apt-get` installs and cleanup in a single `RUN`.
7. **No tests in build** — Run tests in a separate CI job, not inside the
   Docker build itself.

---

## Cross-References

- `docker/Dockerfile` — current Dockerfile
- `docker/docker-compose.yml` — Compose service definitions
- `docker/.dockerignore` — current ignore rules (verify coverage matches
  recommendations above)
- `AGENTS.md` "Docker Health Check Coordination" — health check pitfalls
