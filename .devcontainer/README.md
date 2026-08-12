# Dev Container Setup

This project uses a custom Docker-based dev environment driven by `start-dev.sh`.
There is no VS Code devcontainer.json — the script handles everything.

## Prerequisites

- macOS with Docker Desktop installed and running
- AWS credentials with Bedrock access (for Claude Code)
- A GitHub token, only if you plan to push/PR from inside the container — see [GitHub authentication](#github-authentication) below

## First-time setup

From the repo root, run:

```sh
./start-dev.sh <slot>
```

Replace `<slot>` with any name you like — it's personal to you and not stored in the repo.
On first run the script will prompt you for AWS credentials and write them to
`.devcontainer/devcontainer.env` (git-ignored).

The script will:

1. Build the Docker image (cached on subsequent runs)
2. Create a container named `<repo-name>_<slot>`
3. Run one-time setup inside the container (`postcreate.sh`)
4. Drop you into a zsh shell at `/app`

## How it works

Every slot container is ephemeral — it is destroyed when you exit the shell.
The source code lives at `/app` inside the container, baked into the image at
build time. On every startup, `poststart.sh` runs `git pull --ff-only` to bring
`/app` up to date with `origin/main`.

Because containers are destroyed on exit, any uncommitted work in `/app` is
lost. **Push your work before exiting.**

All slots are identical. There is no "main" slot, and no git worktrees are
involved — each slot is just a separate container over the same baked `/app`.

## Command reference

```sh
# Start (or attach to) a named slot
./start-dev.sh <slot>

# Rebuild the Docker image from scratch, then start
./start-dev.sh <slot> --rebuild
```

These are the only two forms. `start-dev.sh` rejects any other `--flag`.

## What persists across container restarts

Containers are ephemeral — `/app` is rebuilt from the image each time.
Two mechanisms carry data across restarts: one named Docker volume, and a
set of host bind mounts.

### Named volume

| Volume | Mount in container | Purpose |
|---|---|---|
| `<repo-name>-data` | `/home/vscode/.data` | Claude Code config and shell history — shared across all slots |

`postcreate.sh` symlinks into this volume, so the real storage lives in Docker,
**not** in your Mac's home directory:

- `~/.claude` → `~/.data/claude` (config, sessions, settings)
- `~/.claude.json` → `~/.data/claude/claude.json`
- `$HISTFILE` → `~/.data/shell-history/` (both zsh and bash)

The volume survives `--rebuild`, which removes only the container and image.
To discard Claude config and history you must remove the volume explicitly:
`docker volume rm <repo-name>-data`.

### Bind mounts

| Host path | Mount in container | Access | Purpose |
|---|---|---|---|
| `.devcontainer/` (repo root) | `/app/.devcontainer` | read-write | Withheld from the build context by `.dockerignore`, so it is mounted instead; without it these tracked files show up as phantom deletions in `git status` |
| `wip_notes/` (repo root) | `/app/wip_notes` (`$WIP_NOTES`) | read-only | Drop context files here on the host; agents can read them |
| `wip_outputs/<slot>/` (repo root) | `/app/wip_outputs` (`$WIP_OUTPUTS`) | read-write | Agents write outputs here; each slot sees only its own subdirectory |
| `~/dev/graphify-out/<slot>/` | `/app/graphify-out` | read-write | Per-slot graph data from `/graphify`; expensive to regenerate |
| `~/.gitconfig` | `/home/vscode/.gitconfig` | read-only | Commits use your real git identity |
| `~/.agents/skills/` | `/home/vscode/.agents/skills` | read-only | User-level skills; mounted only if the directory exists |

`start-dev.sh` creates `wip_notes/`, `wip_outputs/`, and
`~/dev/graphify-out/<slot>/` automatically on first use.

## GitHub authentication

Running `gh auth login` on your Mac does **not** carry into the container —
there is no `~/.config/gh` mount. Container `gh` authenticates from a
`GH_TOKEN` entry in `.devcontainer/devcontainer.env`:

```sh
GH_TOKEN=ghp_your_token_here
```

`setup.sh` does not prompt for this, so add the line yourself if you need it.
`devcontainer.env` is git-ignored; keep the token out of tracked files.

Your host `~/.gitconfig` is mounted read-only, so if its `credential.helper`
points at a Homebrew `gh` path the container makes that path resolve to the
apt-installed binary via symlink. Pushing works without further setup.

SSH remotes do not work inside a slot: `start-dev.sh` forwards the SSH agent
socket when present, but `openssh-client` is not installed in the image, so
`ssh` is not on `PATH`. Use HTTPS remotes.

## Skills

Claude Code loads skills from two places simultaneously:

- **Project skills** — `.claude/skills/` in the repo (auto-discovered)
- **User skills** — `~/.claude/skills/`, symlinked to the read-only `~/.agents/skills` mount if that directory exists on your Mac
