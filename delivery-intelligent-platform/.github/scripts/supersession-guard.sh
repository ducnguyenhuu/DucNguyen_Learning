#!/usr/bin/env bash
#
# Safe-checkpoint cancellation (research R9): a delivery job that is no longer building the tip
# of main cancels its own run instead of delivering an older commit over a newer one. Runs as
# the first step of a job, never mid-deploy.
#
# Needs: GITHUB_SHA, GITHUB_REPOSITORY, GITHUB_RUN_ID, GITHUB_STEP_SUMMARY, GH_TOKEN (actions: write)
set -euo pipefail

TIP=$(gh api "repos/${GITHUB_REPOSITORY}/commits/main" --jq .sha)

if [ "${TIP}" = "${GITHUB_SHA}" ]; then
    echo "Building the tip of main (${GITHUB_SHA:0:7}); continuing."
    exit 0
fi

echo "⚪ Superseded by ${TIP:0:7} — this run is cancelled." >>"${GITHUB_STEP_SUMMARY}"
gh run cancel "${GITHUB_RUN_ID}"
# The cancel is asynchronous; wait so no later step runs before it lands.
sleep 60
exit 1
