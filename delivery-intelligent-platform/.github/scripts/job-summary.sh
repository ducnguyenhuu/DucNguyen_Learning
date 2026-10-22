#!/usr/bin/env bash
#
# Last step of every job (`if: always()`): writes a one-line outcome to the job summary and,
# when the job failed, surfaces the first failed step as an ::error:: annotation so the
# reason is visible on the run page without opening any log.
#
# Usage: job-summary.sh <job-name> <job-status>
# Needs: GITHUB_STEP_SUMMARY, GITHUB_REPOSITORY, GITHUB_RUN_ID, GH_TOKEN (actions: read)
set -uo pipefail

JOB="$1"
STATUS="$2"

case "${STATUS}" in
    success)   echo "✅ **${JOB}** passed" >>"${GITHUB_STEP_SUMMARY}" ;;
    cancelled) echo "⚪ **${JOB}** cancelled" >>"${GITHUB_STEP_SUMMARY}" ;;
    *)
        STEP=$(gh api "repos/${GITHUB_REPOSITORY}/actions/runs/${GITHUB_RUN_ID}/jobs" \
            --jq "[.jobs[] | select(.name == \"${JOB}\") | .steps[] | select(.conclusion == \"failure\")][0].name" \
            2>/dev/null || true)
        STEP="${STEP:-unknown step}"
        echo "❌ **${JOB}** failed at: ${STEP}" >>"${GITHUB_STEP_SUMMARY}"
        echo "::error title=${JOB} failed::Step \"${STEP}\" failed — see the job log for the cause."
        ;;
esac
