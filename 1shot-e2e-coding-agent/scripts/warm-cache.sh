#!/usr/bin/env bash
# scripts/warm-cache.sh — Pre-warm script (T047)
#
# Builds the repo map and embeddings index for a target workspace so the
# semantic_search and repo_map context tools have cached data available
# before the agent runs.
#
# Usage:
#   ./scripts/warm-cache.sh [WORKSPACE_PATH] [INDEX_PATH]
#
# Arguments:
#   WORKSPACE_PATH  Absolute path to the target repository. Default: $PWD
#   INDEX_PATH      Absolute path for the vectra index directory.
#                   Default: <WORKSPACE_PATH>/.index
#
# Examples:
#   ./scripts/warm-cache.sh /workspace/my-repo
#   ./scripts/warm-cache.sh /workspace/my-repo /workspace/my-repo/.index
#
# Environment variables (optional):
#   EMBEDDING_MODEL   Xenova model name. Default: Xenova/all-MiniLM-L6-v2
#   REPO_MAP_TOKENS   Max tokens for repo map output. Default: 5000

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

WORKSPACE_PATH="${1:-$PWD}"
INDEX_PATH="${2:-$WORKSPACE_PATH/.index}"

echo "=== warm-cache: starting pre-warm ==="
echo "  workspace : $WORKSPACE_PATH"
echo "  index     : $INDEX_PATH"

exec node --import tsx/esm "$SCRIPT_DIR/warm-cache.ts" \
  --workspace "$WORKSPACE_PATH" \
  --index    "$INDEX_PATH"
