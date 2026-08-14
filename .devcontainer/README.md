# Dev Container Setup

This project uses a custom Docker-based dev environment driven by `start-dev.sh`.
There is no VS Code devcontainer.json — the script handles everything.

## Prerequisites

- macOS with Docker Desktop installed and running
- AWS credentials with Bedrock access (for Claude Code)
- GitHub CLI auth (`gh auth login`) — only needed if you plan to push/PR from
  inside the container

## First-time setup

From the repo root, run:

```sh
./start-dev.sh <slot>
```

Replace `<slot>` with any name you like — it's personal to you and not stored
in the repo. On first run the script will prompt you for AWS credentials and
write them to `.devcontainer/devcontainer.env` (git-ignored).

The script will:

1. Build the Docker image (cached on subsequent runs)
2. Create a container named `<repo-name>_<slot>`
3. Run one-time setup inside the container (`postcreate.sh`)
4. Drop you into a zsh shell at `/app`

## How it works

Every slot container is ephemeral — it is destroyed when you exit the shell.
The source code lives at `/app` inside the container, baked into the image at
build time. On every startup, `poststart.sh` runs `git pull` to bring `/app`
up to date with `origin/main`.

Because containers are destroyed on exit, any uncommitted work in `/app` is
lost. **Push your work before exiting.**

All slots are identical. There is no "main" slot.

## Command reference

```sh
# Start (or attach to) a named slot
./start-dev.sh <slot>

# Rebuild the Docker image from scratch, then start
./start-dev.sh <slot> --rebuild
```

## What persists across container restarts

Containers are ephemeral — `/app` is rebuilt from the image each time.
Three host directories are bind-mounted into every container to persist
data across restarts:

| Host path | Mount in container | Access | Purpose |
|---|---|---|---|
| `~/.claude` | `/home/vscode/.claude` | read-write | Claude Code config, sessions, memory — shared across all slots |
| `wip_notes/` (repo root) | `/app/wip_notes` (`$WIP_NOTES`) | read-only | Drop context files here on the host; agents can read them |
| `wip_outputs/<slot>/` (repo root) | `/app/wip_outputs` (`$WIP_OUTPUTS`) | read-write | Agents write outputs here; each slot sees only its own subdirectory |
| `~/dev/graphify-out/<slot>/` | `/app/graphify-out` | read-write | Per-slot graph data from `/graphify`; expensive to regenerate |

`start-dev.sh` creates `wip_notes/`, `wip_outputs/`, and
`~/dev/graphify-out/<slot>/` automatically on first use.

## Skills

Claude Code loads skills from two places simultaneously:

- **Project skills** — `.claude/skills/` in the repo (auto-discovered)
- **User skills** — `~/.claude/skills/`, symlinked from `~/.agents/skills` on
  your Mac if present
