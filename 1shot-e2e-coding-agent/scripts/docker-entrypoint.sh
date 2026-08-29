#!/usr/bin/env bash
# scripts/docker-entrypoint.sh — Container entrypoint (T056)
#
# 1. Start tinyproxy in the background to enforce the domain allowlist (FR-020).
# 2. Export HTTP_PROXY / HTTPS_PROXY so all outbound HTTP/S from the agent
#    and any bash-tool commands route through the proxy.
# 3. Delegate to the agent CLI (node dist/src/cli.js) with all args forwarded.

set -euo pipefail

# ─── Start tinyproxy in background ───────────────────────────────────────────
tinyproxy -c /etc/tinyproxy/tinyproxy.conf

# Give tinyproxy a moment to bind to the port before requests arrive.
sleep 0.5

# ─── Route all HTTP/S through the proxy ──────────────────────────────────────
export HTTP_PROXY="http://127.0.0.1:8888"
export HTTPS_PROXY="http://127.0.0.1:8888"
# npm and some tools use lowercase
export http_proxy="http://127.0.0.1:8888"
export https_proxy="http://127.0.0.1:8888"

# ─── Run the agent CLI ───────────────────────────────────────────────────────
exec node /agent/dist/src/cli.js "$@"
