# First day maintainer setup

By the end of this tutorial, we will have a working local maintainer
environment: dependencies installed, baseline tests running, and local docs
available.

## Prerequisites

- Python 3.12+
- `uv`
- Git

## Step 1: clone and enter the repo

Run:

```bash
git clone https://github.com/CERTCC/Vultron.git
cd Vultron
```

Notice that the repository root contains `vultron/`, `test/`, `docs/`,
`notes/`, and `specs/`.

## Step 2: install the dev environment

Run:

```bash
uv sync --dev
```

Notice that `.venv/` is created and synced.

## Step 3: run the baseline maintainer test command

Run:

```bash
uv run pytest --tb=short 2>&1 | tail -5
```

Notice that the final lines report the pytest summary.

## Step 4: run local docs with maintainer pages enabled

Run:

```bash
uv run mkdocs serve --config-file mkdocs.dev.yml
```

Now open <http://127.0.0.1:8000/developer/>.

Notice that the maintainer docs under `docs/developer/` are available locally.

## Step 5: optional Docker docs path

If you prefer containerized docs development, run:

```bash
docker compose -f docker/docker-compose.yml up docs
```

Then open <http://127.0.0.1:8000/developer/>.

## What we accomplished

We now have a local maintainer setup that supports code changes, test runs, and
dev-only maintainer docs.

## Troubleshooting

- If `uv sync --dev` fails, verify Python 3.12+ and rerun `uv sync --dev`.
- If `mkdocs serve` starts but `/developer/` is missing, confirm
  `--config-file mkdocs.dev.yml` was used.
- If Docker docs do not include maintainer pages, ensure you started the
  `docs` service from `docker/docker-compose.yml`.
