# shellcheck shell=bash
# retry — run a command, retrying it a bounded number of times on failure.
#
# GitHub's API sometimes answers a call with a server error (an HTTP 5xx, or
# GraphQL "Something went wrong while executing your query") that the same
# call clears a few seconds later. A workflow step that makes the call once
# goes red for no reason in its own diff (#4524). Only wrap a call that is safe
# to repeat: a read, or a write that lands in the same state however many
# times it runs (adding a label, upserting one with --force).
#
# Usage:   source .github/scripts/retry.sh; retry <command> [args...]
# Returns: 0 on the first success; otherwise the command's last exit status.
# Tunables (environment):
#   GH_RETRY_ATTEMPTS  total attempts, including the first (default 4)
#   GH_RETRY_DELAY     seconds before the first retry, doubled after each
#                      (default 5, so the waits are 5, 10, 20 seconds)
retry() {
  local attempts="${GH_RETRY_ATTEMPTS:-4}"
  local delay="${GH_RETRY_DELAY:-5}"
  local attempt=1 status
  while true; do
    if "$@"; then
      return 0
    else
      status=$?
    fi
    if [ "$attempt" -ge "$attempts" ]; then
      echo "::error::'$*' failed $attempt time(s), last with exit $status." >&2
      return "$status"
    fi
    echo "::warning::'$*' failed with exit $status (attempt $attempt of" \
      "$attempts); retrying in ${delay}s." >&2
    sleep "$delay"
    attempt=$((attempt + 1))
    delay=$((delay * 2))
  done
}
