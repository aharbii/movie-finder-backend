#!/usr/bin/env bash
# =============================================================================
# Movie Finder Backend — Docker-only setup helper
#
# Purpose:
#   Prepare the backend-owned local development contract from this repo root.
#
# This script intentionally stops at the backend app stack. It does NOT try to
# bootstrap the standalone child-repo workflows for `chain/`, `imdbapi/`, or
# `rag_ingestion/`; those are tracked in their own issues and repos.
#
# Usage:
#   chmod +x scripts/setup.sh
#   ./scripts/setup.sh
#
# What it does:
#   1. Checks required host tools are installed
#   2. Verifies the Docker daemon is running
#   3. Initializes git submodules
#   4. Copies `.env.example` to `.env` if needed
#   5. Runs `make init` to build the backend dev image
# =============================================================================

set -euo pipefail

# ---- Colors -----------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

ok()   { echo -e "${GREEN}  [ok]${RESET}  $*"; }
info() { echo -e "${CYAN}  -->  ${RESET}$*"; }
warn() { echo -e "${YELLOW}  [!]  ${RESET}$*"; }
fail() { echo -e "${RED}  [x]  ${RESET}$*"; exit 1; }
step() { echo -e "\n${BOLD}$*${RESET}"; }

# ---- Prerequisite checks ----------------------------------------------------

step "Checking prerequisites..."

check_tool() {
    local tool=$1
    local install_hint=$2
    if command -v "$tool" >/dev/null 2>&1; then
        ok "$tool found: $(command -v "$tool")"
    else
        fail "$tool is not installed. $install_hint"
    fi
}

check_tool git "Install from your system package manager."
check_tool docker "Install from https://docs.docker.com/get-docker/."
check_tool make "Install your platform's build tools package."

if ! docker info >/dev/null 2>&1; then
    fail "Docker is installed but the daemon is not running."
fi
ok "Docker daemon is running"

# ---- Submodules -------------------------------------------------------------

step "Initializing git submodules..."

if [ ! -f .gitmodules ]; then
    fail ".gitmodules not found. Run this script from the backend/ repository root."
fi

git submodule update --init --recursive
ok "Submodules initialized"

# ---- Environment file -------------------------------------------------------

step "Preparing environment file..."

if [ -f .env ]; then
    ok ".env already exists — skipping copy."
else
    cp .env.example .env
    ok ".env created from .env.example"
    warn "Fill in .env before running make up."
    warn "Minimum backend values: APP_SECRET_KEY, QDRANT_URL, QDRANT_API_KEY_RO, QDRANT_COLLECTION_NAME."
    warn "For chain-backed local flows, also add OPENAI_API_KEY and ANTHROPIC_API_KEY."
fi

# ---- Docker image build -----------------------------------------------------

step "Building the backend development image..."

info "Running: make init"
make init
ok "Docker images are ready"

# ---- Done -------------------------------------------------------------------

echo ""
echo -e "${BOLD}${GREEN}Setup complete.${RESET}"
echo ""
echo "Next steps:"
echo ""
echo "  1. Fill in API keys and secrets:"
echo "       \$EDITOR .env"
echo ""
echo "  2. Start the backend stack:"
echo "       make up"
echo ""
echo "  3. Run quality checks:"
echo "       make lint"
echo "       make typecheck"
echo "       make test"
echo ""
echo "  4. Open the API docs:"
echo "       http://localhost:8000/docs"
echo ""
echo "  5. For VS Code Python debugging/testing, attach to the running"
echo "     \`backend\` container after \`make up\`."
echo ""
