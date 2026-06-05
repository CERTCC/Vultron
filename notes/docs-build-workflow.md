---
title: Docs Build and Link Check Workflow
status: active
---

# Docs Build and Link Check Workflow

Design decisions and implementation guidance for `DOCBW-01` through
`DOCBW-05` (`specs/docs-build-workflow.yaml`). Addresses the gap where
the `linkchecker.yml` workflow ran on any markdown change anywhere in the
repository, causing unnecessary CI runs on changes to `plan/`, `specs/`,
and `notes/` that have no effect on the published MkDocs site.

---

## Decision Table

| Question | Decision | Rationale |
|---|---|---|
| Split into two workflow files or keep as one? | One workflow file | Multiple steps within the same job share the workspace, avoiding artifact upload/download overhead and keeping the build step DRY |
| Should the build step always run? | Yes | Python macro/plugin failures (e.g., `pyproject.toml` or `mkdocs.yml` changes) need to be caught even if no `docs/` content changed |
| When should the link-check step run? | Only when `docs/**` changed (or `workflow_dispatch`) | Link-checking crawls the entire site and is slow; triggering it on every pyproject.toml bump is wasteful |
| How to detect if `docs/` changed? | `git diff --name-only` against the PR base | No third-party action needed; keeps the SHA-pinned `uses:` surface minimal (CISEC-01-001) |
| What paths trigger the workflow at all? | `docs/**`, `mkdocs.yml`, `mkdocs.dev.yml`, `pyproject.toml`, `uv.lock`, workflow file | These are the files that can break the publish build or the dev overlay build |
| Should dev-only docs overlays be validated in CI? | Yes | `mkdocs.dev.yml` changes can break local maintainer docs even when publish docs still build |
| Should `**/*.md` remain as a trigger? | No — remove it | `plan/`, `specs/`, `notes/` changes never affect the built site; the old trigger caused excessive runs |
| Workflow filename | `docs-build-check.yml` | More descriptive than `linkchecker.yml`; the file covers both build and link-check phases |
| Workflow display name | `Docs Build and Link Check` | Matches the two-phase job structure |

---

## Workflow Structure

```yaml
name: Docs Build and Link Check

on:
  pull_request:
    paths:
      - 'docs/**'
      - 'mkdocs.yml'
      - 'mkdocs.dev.yml'
      - 'pyproject.toml'
      - 'uv.lock'
      - '.github/workflows/docs-build-check.yml'
  workflow_dispatch:

permissions:
  contents: read

jobs:
  docs-build-check:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@<SHA> # vX.Y.Z
        with:
          fetch-depth: 0  # needed for git diff against base

      - name: Check if docs/ changed
        id: filter
        run: |
          if [[ "${{ github.event_name }}" == "workflow_dispatch" ]]; then
            echo "docs_changed=true" >> "$GITHUB_OUTPUT"
          elif git diff --name-only origin/${{ github.base_ref }}...HEAD \
               | grep -q '^docs/'; then
            echo "docs_changed=true" >> "$GITHUB_OUTPUT"
          else
            echo "docs_changed=false" >> "$GITHUB_OUTPUT"
          fi

      - name: Set up Python
        uses: actions/setup-python@<SHA> # vX.Y.Z
        with:
          python-version: '3.13'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip uv
          uv sync --dev

      - name: Build Site
        run: |
          uv run mkdocs build --verbose --clean --config-file mkdocs.yml

      - name: Check links
        if: steps.filter.outputs.docs_changed == 'true'
        run: |
          uv run linkchecker site/index.html

      - name: Build Developer Docs Overlay
        run: |
          uv run mkdocs build --verbose --clean --config-file mkdocs.dev.yml
```

### Why `fetch-depth: 0`

The filter step uses `git diff ... origin/${{ github.base_ref }}...HEAD`.
This three-dot diff requires the base ref to be present locally. The
default `fetch-depth: 1` (shallow clone) does not include the base ref,
causing `git diff` to fail. Setting `fetch-depth: 0` fetches the full
history.

### `workflow_dispatch` always runs link check

Manual runs are typically invoked to investigate a link problem or verify
a fix. Always running the link-check step on `workflow_dispatch` avoids
confusion where a manual run skips the check because no `docs/` file was
diff'd.

---

## What Changed and Why

### Before (linkchecker.yml)

```yaml
on:
  pull_request:
    paths:
      - '**/*.md'           # ← too broad: plan/, specs/, notes/ all match
      - .github/workflows/linkchecker.yml
      - pyproject.toml
```

- Ran on any markdown change anywhere — plan/, specs/, notes/ updates all
  triggered an expensive site build + full link crawl.
- The link-check step ran unconditionally, wasting ~5–10 minutes on PRs
  that only touched non-docs markdown.

### After (docs-build-check.yml)

- Trigger narrowed to `docs/**`, `mkdocs.yml`, `mkdocs.dev.yml`,
  `pyproject.toml`,
  `uv.lock`, and the workflow file itself.
- Build Site step still runs on every trigger (guards against plugin
  breakage from `pyproject.toml`/`mkdocs.yml` changes).
- Developer overlay build now runs on every trigger to keep local maintainer
  docs (`docs/developer/`) buildable.
- Link-check step only runs when `docs/` content actually changed.

---

## Relationship to Other Workflows

| Workflow | Purpose | Trigger |
|---|---|---|
| `python-app.yml` | Python tests + linters | `vultron/**`, `test/**`, Python config |
| `docs-build-check.yml` | MkDocs build + link check | `docs/**`, `mkdocs*.yml`, Python config |
| `lint_md_all.yml` | Markdown lint | `**/*.md` |
| `demo-integration.yml` | Docker integration demo | `vultron/**`, `docker/**`, etc. |
| `deploy_site.yml` | Deploy to GitHub Pages | Push to `publish` branch |

Note: `lint_md_all.yml` intentionally retains `**/*.md` as its trigger
because its purpose is to lint all markdown files including `plan/`,
`specs/`, and `notes/`.
