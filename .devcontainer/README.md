# Dev Container Setup

This project uses a custom Docker-based dev environment driven by `start.sh`.
There is no VS Code devcontainer.json — the script handles everything.

## Prerequisites

- macOS with Docker Desktop installed and running
- AWS credentials with Bedrock access (for Claude Code)
- GitHub CLI auth (`gh auth login`) — only needed if you plan to push/PR from inside the container

## First-time setup

From the repo root, run:

```sh
./start.sh <slot>
```

Replace `<slot>` with any name you like — it's personal to you and not stored in the repo.
On first run the script will prompt you for AWS credentials and write them to
`.devcontainer/devcontainer.env` (git-ignored).

The script will:

1. Build the Docker image (cached on subsequent runs)
2. Create a git worktree at `../<repo-name>_<slot>/` (sibling to this checkout)
3. Create a container named `<repo-name>_<slot>` mounting that worktree
4. Run one-time setup inside the container (`postcreate.sh`)
5. Drop you into a zsh shell

## Slot names

A slot is just a name for a parallel dev environment. Each slot gets its own:

- git worktree (`../<repo-name>_<slot>/`) — persists across container restarts
- Docker container (`<repo-name>_<slot>`)

All slots share one persistent data volume for Claude config and shell history.

Choose names freely. The worktrees are siblings to the main checkout wherever
it lives on your filesystem — no hardcoded paths.

## Command reference

```sh
# Start (or attach to) a named slot
./start.sh <slot>

# Attach to the main checkout (no worktree)
./start.sh main

# Nuke the slot's worktree and recreate it from main, then start
./start.sh <slot> --reset

# Rebuild the Docker image from scratch, then start
./start.sh <slot> --rebuild

# Combine: full clean slate
./start.sh <slot> --reset --rebuild
```

## What persists

A named Docker volume (`<repo-name>-data`) is shared across all slots and survives
container removal. It holds:

- `~/.claude/` — Claude Code config, sessions, settings
- `~/.zsh_history` and `~/.bash_history`

Running `--reset` or `--rebuild` removes the container but never the volume.
Your Claude sessions and shell history survive.

## Skills

Claude Code loads skills from two places simultaneously:

- **Project skills** — `.claude/skills/` in the repo (auto-discovered)
- **User skills** — `~/.claude/skills/`, symlinked to `~/.agents/skills` on your Mac

If you have user-level skills at `~/.agents/skills/` on your Mac, they are
mounted read-only into every container automatically.
