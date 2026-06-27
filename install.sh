#!/usr/bin/env bash
set -euo pipefail

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

ok()   { echo -e "${GREEN}  ✔${RESET}  $*"; }
info() { echo -e "${CYAN}  →${RESET}  $*"; }
die()  { echo -e "${RED}  ✖  ERROR:${RESET} $*" >&2; exit 1; }

echo ""
echo -e "${CYAN}${BOLD}"
echo "  ██╗      ██████╗  ██████╗ ██╗  ██╗ ██████╗ ██╗   ██╗████████╗"
echo "  ██║     ██╔═══██╗██╔═══██╗██║ ██╔╝██╔═══██╗██║   ██║╚══██╔══╝"
echo "  ██║     ██║   ██║██║   ██║█████╔╝ ██║   ██║██║   ██║   ██║   "
echo "  ██║     ██║   ██║██║   ██║██╔═██╗ ██║   ██║██║   ██║   ██║   "
echo "  ███████╗╚██████╔╝╚██████╔╝██║  ██╗╚██████╔╝╚██████╔╝   ██║   "
echo "  ╚══════╝ ╚═════╝  ╚═════╝ ╚═╝  ╚═╝ ╚═════╝  ╚═════╝    ╚═╝   "
echo -e "${RESET}"
echo -e "  ${BOLD}Self-hosted infrastructure monitoring — Installer${RESET}"
echo ""

# ── Dependency checks ─────────────────────────────────────────────────────────
info "Checking dependencies..."

command -v docker &>/dev/null \
  || die "Docker is not installed. Visit https://docs.docker.com/get-docker/"
ok "docker found ($(docker --version | cut -d' ' -f3 | tr -d ','))"

# Support both 'docker compose' (plugin) and 'docker-compose' (standalone)
if docker compose version &>/dev/null 2>&1; then
  COMPOSE="docker compose"
elif command -v docker-compose &>/dev/null; then
  COMPOSE="docker-compose"
else
  die "Docker Compose is not installed. Visit https://docs.docker.com/compose/install/"
fi
ok "docker compose found"

# ── Environment file ──────────────────────────────────────────────────────────
if [[ ! -f backend/.env ]]; then
  if [[ -f backend/.env.example ]]; then
    cp backend/.env.example backend/.env
    ok "backend/.env created from .env.example"
    echo ""
    echo -e "  ${BOLD}⚠  Review ${CYAN}backend/.env${RESET}${BOLD} and set your secrets before going to production.${RESET}"
    echo ""
  else
    die "backend/.env.example not found. Is your working directory the project root?"
  fi
else
  ok "backend/.env already exists — skipping"
fi

# ── Build & launch ────────────────────────────────────────────────────────────
echo ""
info "Building images and starting the stack (this may take a few minutes)..."
echo ""

$COMPOSE up -d --build

# ── Health wait ───────────────────────────────────────────────────────────────
echo ""
info "Waiting for the backend to become healthy..."
MAX_WAIT=60
ELAPSED=0
until curl -sf http://localhost/api/v1/services/status &>/dev/null; do
  if (( ELAPSED >= MAX_WAIT )); then
    die "Backend did not respond after ${MAX_WAIT}s. Run 'docker compose logs backend' to diagnose."
  fi
  sleep 2
  (( ELAPSED += 2 ))
done

# ── Success banner ────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}"
echo "  ╔══════════════════════════════════════════════════════╗"
echo "  ║                                                      ║"
echo "  ║   🚀  Lookout is up and running!                     ║"
echo "  ║                                                      ║"
echo "  ║   Dashboard  →  http://localhost                     ║"
echo "  ║   API        →  http://localhost/api/v1/services     ║"
echo "  ║   WebSocket  →  ws://localhost/ws/v1/dashboard       ║"
echo "  ║                                                      ║"
echo "  ║   Stop  :  docker compose down                       ║"
echo "  ║   Logs  :  docker compose logs -f                    ║"
echo "  ║                                                      ║"
echo "  ╚══════════════════════════════════════════════════════╝"
echo -e "${RESET}"
