#!/usr/bin/env bash
#
# Checks the subject line of every non-merge commit in <base>..<head> against the
# Conventional Commits grammar in specs/006-ci-cd/contracts/commit-message.md.
# Merge commits are skipped: Git and GitHub author them, not the developer.
#
# Usage: validate-commit-messages.sh <base> <head>
# Exit:  0 all valid, 1 at least one violation, 2 bad arguments
set -euo pipefail

if [ $# -ne 2 ]; then
    echo "usage: validate-commit-messages.sh <base> <head>" >&2
    exit 2
fi

BASE="$1"
HEAD="$2"
PATTERN='^(feat|fix|chore|docs|style|refactor|perf|test|build|ci)(\([a-z0-9-]+\))?!?: [^[:space:]].*$'

if ! git rev-parse --verify --quiet "${BASE}^{commit}" >/dev/null \
    || ! git rev-parse --verify --quiet "${HEAD}^{commit}" >/dev/null; then
    echo "base or head is not a known commit: ${BASE} ${HEAD}" >&2
    exit 2
fi

bad=0
while IFS=$'\t' read -r sha subject; do
    [ -z "${sha}" ] && continue
    if ! [[ "${subject}" =~ ${PATTERN} ]]; then
        bad=$((bad + 1))
        echo "::error title=Commit message::${sha} \"${subject}\" does not follow Conventional Commits"
        echo "  ${sha}  ${subject}" >&2
    fi
done < <(git log --no-merges --format='%h%x09%s' "${BASE}..${HEAD}")

if [ "${bad}" -gt 0 ]; then
    {
        echo "FAIL: ${bad} commit(s) break the commit-message convention."
        echo "Expected: <type>[(<scope>)][!]: <description>"
        echo "Types:    feat fix chore docs style refactor perf test build ci"
        echo "Example:  feat(ci-cd): add supersession guard"
    } >&2
    exit 1
fi

echo "PASS: every non-merge commit in ${BASE}..${HEAD} follows the convention."
