#!/usr/bin/env bash
#
# run-if-changed.sh — run a command only if its relevant inputs changed since
# the last successful run. Lets black/flake8/mypy/pyright be invoked from
# several places (format-code, run-linters, the pre-commit hook) without
# re-doing identical whole-tree work when nothing relevant changed.
#
# Usage:
#   run-if-changed.sh <key> <input-path>... -- <command>...
#
#   <key>          Cache label. Invocations sharing a key + input set share a
#                  cache entry, so a run in one skill satisfies the next.
#   <input-path>   Files/dirs whose contents form the fingerprint (source
#                  roots plus the tool's own config and uv.lock). Directories
#                  are expanded to their tracked + untracked-non-ignored files
#                  via git, so build artifacts and .venv never count.
#   <command>...   The command to run (everything after `--`).
#
# The command runs when the fingerprint differs from the last success (or when
# the fingerprint can't be computed — e.g. outside a git repo). On success the
# post-run fingerprint is stored, so mutating tools like black stabilize after
# one run. Cache lives in .git/ (per-worktree, never committed).

set -uo pipefail

key="${1:?usage: run-if-changed.sh <key> <input-path>... -- <command>...}"
shift

inputs=()
while [ $# -gt 0 ] && [ "$1" != "--" ]; do
  inputs+=("$1")
  shift
done
[ "${1:-}" = "--" ] && shift
if [ $# -eq 0 ]; then
  echo "run-if-changed: no command given after --" >&2
  exit 2
fi

git_dir="$(git rev-parse --git-dir 2>/dev/null)" || git_dir=""

# Fingerprint = hash of (path + content) over every tracked or
# untracked-non-ignored file under the inputs. Additions, deletions, renames
# and edits all change it; ignored artifacts never do.
fingerprint() {
  [ -n "$git_dir" ] || return 1
  git ls-files -z --cached --others --exclude-standard -- "${inputs[@]}" 2>/dev/null \
    | sort -z \
    | xargs -0 -r sha1sum 2>/dev/null \
    | sha1sum | awk '{print $1}'
}

# No git / no fingerprint: run unconditionally, don't cache.
if [ -z "$git_dir" ]; then
  exec "$@"
fi

cache_dir="$git_dir/lint-cache"
cache_file="$cache_dir/$key"

current="$(fingerprint)"
if [ -n "$current" ] && [ -f "$cache_file" ] && [ "$(cat "$cache_file")" = "$current" ]; then
  echo "run-if-changed: '$key' inputs unchanged since last success — skipping"
  exit 0
fi

"$@"
status=$?

if [ "$status" -eq 0 ]; then
  # Recompute after the run so mutating tools (black) store their result state.
  post="$(fingerprint)"
  if [ -n "$post" ]; then
    mkdir -p "$cache_dir"
    printf '%s\n' "$post" > "$cache_file"
  fi
fi

exit "$status"
