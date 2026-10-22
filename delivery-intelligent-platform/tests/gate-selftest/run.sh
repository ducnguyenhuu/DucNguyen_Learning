#!/usr/bin/env bash
#
# Negative proofs for the pipeline's gates (specs/006-ci-cd/research.md R11). A gate that passes
# is indistinguishable from a gate that does nothing, so for each rejection category this script
# plants one violation in a scratch copy and asserts the gate FAILS with the expected message.
# The script itself exits non-zero if any gate failed to fail.
#
# Usage: tests/gate-selftest/run.sh [architecture|secret|dependency|commit]   (default: all four)
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRATCH="$(mktemp -d)"
trap 'rm -rf "${SCRATCH}"' EXIT

failed=0

# expect_rejected <gate> <expected-text> <command...>: the command must exit non-zero and its
# output must contain the expected text — a failure for the wrong reason does not count.
expect_rejected() {
    local gate="$1" expected="$2"
    shift 2
    local output status
    output=$("$@" 2>&1)
    status=$?
    if [ "${status}" -eq 0 ]; then
        echo "FAIL ${gate}: the gate accepted a planted violation"
        failed=1
    elif ! grep -qiF -- "${expected}" <<<"${output}"; then
        echo "FAIL ${gate}: rejected, but not for the expected reason (wanted \"${expected}\")"
        echo "${output}" | tail -15
        failed=1
    else
        echo "PASS ${gate}: rejected with \"${expected}\""
    fi
}

git_scratch() {
    local dir="$1"
    mkdir -p "${dir}"
    git -C "${dir}" init -q
    git -C "${dir}" config user.email selftest@example.invalid
    git -C "${dir}" config user.name selftest
}

gate_architecture() {
    # Tenancy.Domain taking on an ORM dependency breaks the layering rule.
    local copy="${SCRATCH}/architecture"
    mkdir -p "${copy}"
    rsync -a --exclude=.git --exclude=bin --exclude=obj "${REPO_ROOT}/" "${copy}/"
    sed -i.bak 's#</Project>#  <ItemGroup><PackageReference Include="Microsoft.EntityFrameworkCore" /></ItemGroup>\n</Project>#' \
        "${copy}/src/Tenancy/Tenancy.Domain/Tenancy.Domain.csproj"
    expect_rejected architecture "Tenancy.Domain must not depend" \
        dotnet run --project "${copy}/tests/ArchitectureTests"
}

gate_secret() {
    local repo="${SCRATCH}/secret"
    git_scratch "${repo}"
    openssl genrsa -out "${repo}/leaked.pem" 2048 2>/dev/null
    git -C "${repo}" add . && git -C "${repo}" commit -q -m "chore: add key"
    expect_rejected secret "leaked.pem" gitleaks git --redact -v "${repo}"
}

gate_dependency() {
    expect_rejected dependency "NU1903" \
        dotnet restore "${REPO_ROOT}/tests/gate-selftest/dependency-canary/Canary.csproj" --force-evaluate
}

gate_commit() {
    local repo="${SCRATCH}/commit"
    git_scratch "${repo}"
    git -C "${repo}" commit -q --allow-empty -m "chore: baseline"
    git -C "${repo}" commit -q --allow-empty -m "fixed stuff"
    expect_rejected commit "fixed stuff" \
        bash -c "cd '${repo}' && '${REPO_ROOT}/infrastructure/scripts/validate-commit-messages.sh' HEAD~1 HEAD"
}

gates=("$@")
[ ${#gates[@]} -eq 0 ] && gates=(architecture secret dependency commit)

for gate in "${gates[@]}"; do
    case "${gate}" in
        architecture|secret|dependency|commit) "gate_${gate}" ;;
        *) echo "unknown gate: ${gate}" >&2; exit 2 ;;
    esac
done

exit "${failed}"
