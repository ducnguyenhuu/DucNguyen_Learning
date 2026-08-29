#!/usr/bin/env bash
# agent.sh — One-shot coding agent runner
#
# Usage:
#   ./agent.sh "Add email validation to the signup endpoint"
#   ./agent.sh "Fix the failing login test" --dry-run
#
# Setup (one-time):
#   1. Copy .env.example to .env and fill in your keys
#   2. Run init in your target repo: ./agent.sh --init ~/projects/my-app

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"

# ─── Load .env ────────────────────────────────────────────────────────────────

if [[ ! -f "$ENV_FILE" ]]; then
  echo ""
  echo "❌  Missing .env file. Run this to create one:"
  echo ""
  echo "    cp $SCRIPT_DIR/.env.example $SCRIPT_DIR/.env"
  echo "    # Then edit .env with your API keys and REPO_URL"
  echo ""
  exit 1
fi

# shellcheck source=/dev/null
set -a && source "$ENV_FILE" && set +a

# ─── --init mode ──────────────────────────────────────────────────────────────

if [[ "${1:-}" == "--init" ]]; then
  TARGET="${2:-$(pwd)}"
  echo ""
  echo "🔧  Initializing agent config in: $TARGET"
  echo ""
  cd "$TARGET"
  npx tsx "$SCRIPT_DIR/src/cli.ts" init
  echo ""
  echo "✅  Done. Next steps:"
  echo "    1. Review $TARGET/pi-agent.config.ts  (test/lint commands are auto-detected)"
  echo "    2. Edit $TARGET/AGENTS.md            (add your team's coding conventions)"
  echo "    3. Commit both files: git add pi-agent.config.ts AGENTS.md && git commit -m 'chore: add pi-agent config' && git push"
  echo "    4. Run a task:  ./agent.sh \"Your task description\""
  echo ""
  exit 0
fi

# ─── Validate required env vars ───────────────────────────────────────────────

if [[ -z "${REPO_URL:-}" ]]; then
  echo "❌  REPO_URL is not set in .env"
  echo "    Example: REPO_URL=https://github.com/you/my-app.git"
  exit 1
fi

if [[ -z "${ANTHROPIC_API_KEY:-}" && -z "${OPENAI_API_KEY:-}" ]]; then
  echo "❌  No LLM API key set in .env"
  echo "    Set ANTHROPIC_API_KEY or OPENAI_API_KEY"
  exit 1
fi

if [[ -z "${1:-}" ]]; then
  echo ""
  echo "Usage: ./agent.sh \"Your task description\" [--dry-run]"
  echo ""
  echo "Examples:"
  echo "  ./agent.sh \"Add email validation to the signup endpoint\""
  echo "  ./agent.sh \"Fix the failing login test\" --dry-run"
  echo "  ./agent.sh --init ~/projects/my-app"
  echo ""
  exit 1
fi

TASK="$1"
shift
EXTRA_ARGS=("$@")   # e.g. --dry-run, --provider openai

# ─── Build image (cached — fast on second run) ────────────────────────────────

echo ""
echo "🐳  Building Docker image  (first time: ~5 min, subsequent: ~10 sec)"
echo "    Repo: $REPO_URL  branch: ${REPO_BRANCH:-main}"
echo ""

cd "$SCRIPT_DIR"
docker compose build devbox

# ─── Run task ─────────────────────────────────────────────────────────────────

echo ""
echo "🤖  Running task: $TASK"
echo ""

docker compose run --rm devbox \
  run "$TASK" \
  --config /workspace/pi-agent.config.ts \
  "${EXTRA_ARGS[@]}"

echo ""
echo "✅  Done. Check runs/ for artifacts, then open GitHub to create a PR."
echo ""
