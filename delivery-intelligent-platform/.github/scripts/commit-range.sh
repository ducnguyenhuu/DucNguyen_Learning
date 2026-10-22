#!/usr/bin/env bash
#
# Emits the commit range this run is responsible for as `base=` and `head=` outputs
# (specs/006-ci-cd/contracts/commit-message.md → Which commits are checked).
#   pull_request:        merge base with the target branch .. PR head
#   push / dispatch:     previous tip .. new tip (the parent when there is no previous tip)
#
# Needs: a checkout with full history, and the usual GITHUB_* variables.
set -euo pipefail

if [ "${GITHUB_EVENT_NAME}" = "pull_request" ]; then
    head="${PR_HEAD_SHA}"
    base=$(git merge-base "${PR_BASE_SHA}" "${head}")
else
    head="${GITHUB_SHA}"
    base="${PUSH_BEFORE_SHA:-}"
    if [ -z "${base}" ] || [ "${base}" = "0000000000000000000000000000000000000000" ]; then
        base=$(git rev-parse "${head}~1")
    fi
fi

echo "range ${base}..${head}"
{
    echo "base=${base}"
    echo "head=${head}"
} >>"${GITHUB_OUTPUT}"
