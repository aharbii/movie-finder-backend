#!/usr/bin/env bash
# =============================================================================
# Movie Finder Backend — New Member Setup Script
#
# Automates first-time environment setup for any team member.
# Equivalent to running `make setup` but with more verbose output and checks.
#
# Usage:
#   chmod +x scripts/setup.sh
#   ./scripts/setup.sh
#
# What it does:
#   1. Checks required tools are installed
#   2. Initializes git submodules
#   3. Installs workspace Python packages with dev dependencies
#   4. Installs pre-commit hooks
#   5. Creates .env from .env.example if not present
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
    if command -v "$tool" &>/dev/null; then
        ok "$tool found: $(command -v "$tool")"
    else
        fail "$tool is not installed. $install_hint"
    fi
}

check_tool git  "Install from your system package manager."
check_tool uv   "Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"

# Check Python version via uv
PYTHON_VERSION=$(uv python find 3.13 2>/dev/null || true)
if [ -z "$PYTHON_VERSION" ]; then
    warn "Python 3.13 not found via uv. Installing..."
    uv python install 3.13
    ok "Python 3.13 installed."
else
    ok "Python 3.13 available: $PYTHON_VERSION"
fi

# Docker is optional (needed for docker-up targets)
if command -v docker &>/dev/null; then
    ok "Docker found: $(docker --version | head -1)"
    if ! docker info &>/dev/null 2>&1; then
        warn "Docker is installed but the daemon is not running. Start Docker Desktop or the Docker service."
    fi
else
    warn "Docker not found. You can still run tests without Docker, but 'make docker-up' will not work."
    warn "Install from: https://docs.docker.com/get-docker/"
fi

# ---- Submodules -------------------------------------------------------------

step "Initializing git submodules..."

if [ ! -f .gitmodules ]; then
    fail ".gitmodules not found. Run this script from the backend/ repository root."
fi

git submodule update --init --recursive
ok "Submodules initialized: chain, imdbapi, rag_ingestion"

# ---- Python environment -----------------------------------------------------

step "Installing workspace packages with dev tools..."

info "Running: uv sync --group dev"
uv sync --group dev
ok "Workspace packages installed (chain + imdbapi + dev tools)"

# ---- Pre-commit hooks -------------------------------------------------------

step "Installing pre-commit hooks..."

uv run pre-commit install
ok "Pre-commit hooks installed in .git/hooks/pre-commit"

# ---- Environment file -------------------------------------------------------

step "Setting up environment file..."

if [ -f .env ]; then
    ok ".env already exists — skipping copy."
else
    cp .env.example .env
    ok ".env created from .env.example"
    warn "You MUST fill in API keys in .env before running the application."
    warn "Required keys: ANTHROPIC_API_KEY, OPENAI_API_KEY, IMDB_API_KEY"
    warn "Contact your team lead for the Qdrant credentials (QDRANT_ENDPOINT, QDRANT_API_KEY, QDRANT_COLLECTION)."
fi

# ---- Smoke test -------------------------------------------------------------

step "Running smoke tests..."

info "Testing workspace imports..."
if uv run python -c "from chain import compile_graph; from imdbapi import IMDBAPIClient; print('ok')" &>/dev/null; then
    ok "chain and imdbapi import successfully"
else
    warn "Import check failed. This may be expected if dependencies need network access."
    warn "Try: uv sync --group dev && uv run python -c \"from chain import compile_graph\""
fi

# ---- Done -------------------------------------------------------------------

echo ""
echo -e "${BOLD}${GREEN}Setup complete!${RESET}"
echo ""
echo "Next steps:"
echo ""
echo "  1. Fill in API keys:"
echo "       \$EDITOR .env"
echo ""
echo "  2. Verify everything works:"
echo "       make check"
echo ""
echo "  3. Start the local stack (requires Docker + .env keys):"
echo "       make docker-up"
echo ""
echo "  4. Read the contribution guide:"
echo "       cat CONTRIBUTING.md"
echo ""
echo "  5. Read the integration guide for team workflows:"
echo "       cat INTEGRATION.md"
echo ""
