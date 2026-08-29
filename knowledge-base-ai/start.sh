#!/usr/bin/env bash
# ============================================================
# Knowledge Base AI — Local Development Startup Script
# ============================================================
# Usage:
#   ./start.sh           Start all services (Ollama, Backend, Frontend)
#   ./start.sh stop      Stop all services
#   ./start.sh status    Check service status
#   ./start.sh setup     One-time setup (install deps, pull models, run migrations)
# ============================================================

set -euo pipefail

PROJ_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$PROJ_DIR/backend"
FRONTEND_DIR="$PROJ_DIR/frontend"
VENV_DIR="$PROJ_DIR/.venv"
PID_DIR="$PROJ_DIR/.pids"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log()   { echo -e "${BLUE}[INFO]${NC}  $1"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
err()   { echo -e "${RED}[ERROR]${NC} $1"; }

# ── Helpers ──────────────────────────────────────────────────

ensure_pid_dir() {
    mkdir -p "$PID_DIR"
}

is_running() {
    local pidfile="$PID_DIR/$1.pid"
    if [[ -f "$pidfile" ]]; then
        local pid
        pid=$(cat "$pidfile")
        if kill -0 "$pid" 2>/dev/null; then
            return 0
        fi
    fi
    return 1
}

wait_for_url() {
    local url="$1" max_wait="${2:-30}" waited=0
    while ! curl -sf "$url" > /dev/null 2>&1; do
        sleep 1
        waited=$((waited + 1))
        if [[ $waited -ge $max_wait ]]; then
            return 1
        fi
    done
    return 0
}

# ── Setup (one-time) ────────────────────────────────────────

cmd_setup() {
    log "Running one-time setup..."

    # 1. Python venv
    if [[ ! -d "$VENV_DIR" ]]; then
        log "Creating Python virtual environment..."
        python3 -m venv "$VENV_DIR"
    fi
    source "$VENV_DIR/bin/activate"

    # 2. Backend dependencies
    log "Installing backend dependencies..."
    pip install -r "$BACKEND_DIR/requirements.txt" -q

    # 3. Database migrations
    log "Running database migrations..."
    mkdir -p "$BACKEND_DIR/data"
    (cd "$BACKEND_DIR" && alembic upgrade head)

    # 4. Ollama models
    log "Pulling Ollama models (this may take a few minutes)..."
    if command -v ollama &>/dev/null; then
        ollama pull phi3.5:3.8b-mini-instruct-q4_K_M
        ollama pull nomic-embed-text
    else
        err "Ollama not installed. Install it first: brew install ollama"
        exit 1
    fi

    # 5. Frontend dependencies
    log "Installing frontend dependencies..."
    (cd "$FRONTEND_DIR" && npm install)

    echo ""
    ok "Setup complete! Run ./start.sh to start all services."
}

# ── Start ────────────────────────────────────────────────────

cmd_start() {
    ensure_pid_dir

    echo ""
    echo "========================================="
    echo "  Knowledge Base AI — Starting Services  "
    echo "========================================="
    echo ""

    # 1. Ollama
    if pgrep -x "ollama" > /dev/null 2>&1; then
        ok "Ollama already running"
    else
        log "Starting Ollama..."
        ollama serve > "$PROJ_DIR/.pids/ollama.log" 2>&1 &
        echo $! > "$PID_DIR/ollama.pid"
        if wait_for_url "http://localhost:11434" 15; then
            ok "Ollama started (http://localhost:11434)"
        else
            err "Ollama failed to start. Check .pids/ollama.log"
            exit 1
        fi
    fi

    # 2. Backend
    if is_running "backend"; then
        ok "Backend already running"
    else
        log "Starting Backend..."
        source "$VENV_DIR/bin/activate"
        (cd "$BACKEND_DIR" && uvicorn app.main:app \
            --host 127.0.0.1 --port 8000 --reload \
            > "$PID_DIR/backend.log" 2>&1) &
        echo $! > "$PID_DIR/backend.pid"
        if wait_for_url "http://127.0.0.1:8000/api/v1/health" 20; then
            ok "Backend started (http://127.0.0.1:8000)"
        else
            err "Backend failed to start. Check .pids/backend.log"
            exit 1
        fi
    fi

    # 3. Frontend
    if is_running "frontend"; then
        ok "Frontend already running"
    else
        log "Starting Frontend..."
        (cd "$FRONTEND_DIR" && npm run dev > "$PID_DIR/frontend.log" 2>&1) &
        echo $! > "$PID_DIR/frontend.pid"
        sleep 3
        ok "Frontend started (http://localhost:5173)"
    fi

    echo ""
    echo "========================================="
    echo "  All services running!                  "
    echo "========================================="
    echo ""
    echo "  Frontend:  http://localhost:5173"
    echo "  Backend:   http://127.0.0.1:8000"
    echo "  API Docs:  http://127.0.0.1:8000/docs"
    echo "  Ollama:    http://localhost:11434"
    echo ""
    echo "  Stop with: ./start.sh stop"
    echo "========================================="
}

# ── Stop ─────────────────────────────────────────────────────

cmd_stop() {
    ensure_pid_dir

    echo ""
    log "Stopping services..."

    # Stop frontend
    if is_running "frontend"; then
        kill "$(cat "$PID_DIR/frontend.pid")" 2>/dev/null && ok "Frontend stopped" || warn "Frontend already stopped"
    fi

    # Stop backend
    if is_running "backend"; then
        kill "$(cat "$PID_DIR/backend.pid")" 2>/dev/null && ok "Backend stopped" || warn "Backend already stopped"
    fi

    # Stop Ollama
    if [[ -f "$PID_DIR/ollama.pid" ]] && is_running "ollama"; then
        kill "$(cat "$PID_DIR/ollama.pid")" 2>/dev/null && ok "Ollama stopped" || warn "Ollama already stopped"
    elif pgrep -x "ollama" > /dev/null 2>&1; then
        pkill -x "ollama" && ok "Ollama stopped" || warn "Ollama already stopped"
    fi

    # Clean up PID files
    rm -f "$PID_DIR"/*.pid

    echo ""
    ok "All services stopped."
}

# ── Status ───────────────────────────────────────────────────

cmd_status() {
    echo ""
    echo "Service Status:"
    echo "───────────────────────────────────"

    # Ollama
    if pgrep -x "ollama" > /dev/null 2>&1; then
        ok "Ollama     — running (http://localhost:11434)"
    else
        err "Ollama     — stopped"
    fi

    # Backend
    if curl -sf http://127.0.0.1:8000/api/v1/health > /dev/null 2>&1; then
        ok "Backend    — running (http://127.0.0.1:8000)"
    else
        err "Backend    — stopped"
    fi

    # Frontend
    if curl -sf http://localhost:5173 > /dev/null 2>&1; then
        ok "Frontend   — running (http://localhost:5173)"
    else
        err "Frontend   — stopped"
    fi

    echo "───────────────────────────────────"
    echo ""
}

# ── Main ─────────────────────────────────────────────────────

case "${1:-start}" in
    start)  cmd_start  ;;
    stop)   cmd_stop   ;;
    status) cmd_status ;;
    setup)  cmd_setup  ;;
    *)
        echo "Usage: ./start.sh [start|stop|status|setup]"
        exit 1
        ;;
esac
