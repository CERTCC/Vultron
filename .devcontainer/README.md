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
build time. When the container is created, `poststart.sh` fetches and then
force-resets `/app` to `origin/main` — so every slot starts from the same known
state, on `main`, regardless of which branch your Mac's checkout is on. It does
not run again when you re-attach to a running container.

The image carries `main` and nothing else. The build strips the local branches,
stashes and reflog copied in from your Mac's `.git`, so there is no stale local
branch for an agent to check out by mistake. Branches you have not pushed are
not reachable from inside a slot — push first if you need one there.

Because containers are destroyed on exit, any uncommitted work in `/app` is
lost. **Push your work before exiting.**

`.devcontainer/` is baked into the image like any other tracked directory. Edits
you make to it on your Mac do not appear inside a running container; you get them
on the next `./start-dev.sh <slot>`, which rebuilds because the file changed.

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
