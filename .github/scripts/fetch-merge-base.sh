#!/usr/bin/env bash
# fetch-merge-base — make `git merge-base origin/<base> HEAD` resolve in a
# shallow checkout, fetching no more history than that needs.
#
# A pull-request check that compares against the merge base (the growth
# guards, the ADR edit checks, the demo base-versus-head run) used to check out
# with `fetch-depth: 0`, which downloads every branch's whole history and every
# tag. That fetch is the largest one the job can make, and when it hangs the
# job's `timeout-minutes` cancels it and the CI gate goes red with no test run
# (#6535, #6390).
#
# Most pull-request jobs need no fetch: their depth-2 checkout is GitHub's
# merge commit, whose first parent is the base, and the `fetch-merge-base`
# action points origin/<base> at it. This script is for the rest: a job that
# checks out the head commit itself (demo-verdict), or one that reads every
# branch commit rather than only the diff (vince-data-check). It fetches the
# base branch one commit deep, then deepens the base and HEAD together until
# the two histories meet, and only unshallows as a last resort.
#
# Each fetch runs under `timeout` and `retry`, so one hung fetch is retried
# inside the job's cap instead of using all of it.
#
# Usage:   fetch-merge-base.sh <base-branch>
# Output:  the merge-base commit on stdout; progress on stderr.
# Tunables (environment):
#   FETCH_TIMEOUT       seconds one fetch may take (default 60)
#   GH_RETRY_ATTEMPTS   attempts per fetch, read by retry.sh (default here 3)
#   GH_RETRY_DELAY      seconds before the first retry, read by retry.sh
#   FETCH_DEEPEN_STEPS  space-separated deepen counts (default "10 100 1000")
#   FETCH_REMOTE        remote to fetch from (default origin)
set -euo pipefail

if [ "$#" -ne 1 ] || [ -z "$1" ]; then
  echo "usage: fetch-merge-base.sh <base-branch>" >&2
  exit 2
fi
base="$1"
remote="${FETCH_REMOTE:-origin}"
export GH_RETRY_ATTEMPTS="${GH_RETRY_ATTEMPTS:-3}"

# shellcheck source=retry.sh
. "$(cd "$(dirname "$0")" && pwd)/retry.sh"

head_sha="$(git rev-parse HEAD)"
base_ref="refs/remotes/${remote}/${base}"
refspec="+refs/heads/${base}:${base_ref}"

fetch() {
  timeout -k 10 "${FETCH_TIMEOUT:-60}" \
    git fetch --no-tags --no-recurse-submodules --quiet "$@" \
    "$remote" "$refspec" "$head_sha"
}

found() {
  git merge-base "$base_ref" HEAD 2>/dev/null
}

# A full clone (a local run, such as the pre-push CI mirror) has nothing to
# deepen, and its HEAD may be a commit the remote does not have yet, so it only
# brings the base branch up to date.
if [ "$(git rev-parse --is-shallow-repository)" != "true" ]; then
  echo "fetch-merge-base: full clone; updating ${base} only" >&2
  retry timeout -k 10 "${FETCH_TIMEOUT:-60}" \
    git fetch --no-tags --no-recurse-submodules --quiet "$remote" "$refspec"
  if ! found; then
    echo "::error::fetch-merge-base: ${base} and HEAD share no history." >&2
    exit 1
  fi
  exit 0
fi

echo "fetch-merge-base: fetching ${base} one commit deep" >&2
retry fetch --depth=1

for step in ${FETCH_DEEPEN_STEPS:-10 100 1000}; do
  if found; then
    exit 0
  fi
  echo "fetch-merge-base: no merge base yet; deepening by ${step}" >&2
  retry fetch --deepen="$step"
done

if found; then
  exit 0
fi

if [ "$(git rev-parse --is-shallow-repository)" = "true" ]; then
  echo "fetch-merge-base: still no merge base; fetching the full history" >&2
  retry fetch --unshallow
fi

if ! found; then
  echo "::error::fetch-merge-base: ${base} and HEAD share no history." >&2
  exit 1
fi
