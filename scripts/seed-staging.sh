#!/usr/bin/env bash
#
# Script: seed-staging.sh
# Description: Seed the staging database with test scenarios (issue #11)
# Usage: ./scripts/seed-staging.sh [--clear] [--dry-run]
#
# Requirements:
#   - Railway CLI installed (https://docs.railway.app/develop/cli)
#   - Logged in to Railway (railway login)
#   - Staging environment selected
#

set -euo pipefail

# ------------------------------------------------------------------
# Colors and formatting
# ------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
log_info() {
    echo -e "${BLUE}ℹ${NC}  $1"
}

log_success() {
    echo -e "${GREEN}✅${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}⚠️${NC}  $1"
}

log_error() {
    echo -e "${RED}❌${NC} $1"
}

log_step() {
    echo -e "\n${BOLD}▶ $1${NC}"
}

# ------------------------------------------------------------------
# Check prerequisites
# ------------------------------------------------------------------
check_prerequisites() {
    log_step "Checking prerequisites"

    # Check Railway CLI
    if ! command -v railway &> /dev/null; then
        log_error "Railway CLI not found. Install it:"
        echo "   npm install -g @railway/cli"
        echo "   or: brew install railway"
        exit 1
    fi
    log_success "Railway CLI found"

    # Check if logged in
    if ! railway whoami &> /dev/null; then
        log_error "Not logged in to Railway. Run:"
        echo "   railway login"
        exit 1
    fi
    log_success "Logged in to Railway"

    # Check if we can access the staging service
    log_info "Checking staging service access..."
    if ! railway status &> /dev/null; then
        log_error "Cannot access Railway project. Make sure you are in the correct directory and have selected the project."
        exit 1
    fi
}

# ------------------------------------------------------------------
# Parse arguments
# ------------------------------------------------------------------
CLEAR_FLAG=""
DRY_RUN_FLAG=""

parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --clear)
                CLEAR_FLAG="--clear"
                shift
                ;;
            --dry-run)
                DRY_RUN_FLAG="--dry-run"
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

show_help() {
    cat << EOF
Usage: ./scripts/seed-staging.sh [OPTIONS]

Seed the staging database with test scenarios.

Options:
    --clear      Clear existing seed data before seeding
    --dry-run    Show what would be created without saving
    -h, --help   Show this help message

Examples:
    ./scripts/seed-staging.sh
    ./scripts/seed-staging.sh --dry-run
    ./scripts/seed-staging.sh --clear

EOF
}

# ------------------------------------------------------------------
# Main execution
# ------------------------------------------------------------------
main() {
    echo -e "${BOLD}=== Seed Staging Database ===${NC}"
    echo "Issue #11: Test scenarios for pricing and availability"
    echo ""

    # Parse arguments
    parse_args "$@"

    # Check prerequisites
    check_prerequisites

    # Confirm before proceeding (unless dry-run)
    if [[ -z "$DRY_RUN_FLAG" ]]; then
        echo ""
        if [[ -n "$CLEAR_FLAG" ]]; then
            log_warning "This will CLEAR existing seed data and re-seed."
        else
            log_info "This will add seed data to the staging database."
        fi
        
        read -p "Continue? [y/N] " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Aborted."
            exit 0
        fi
    fi

    # Run the seed command
    log_step "Running seed_staging command"
    railway run python manage.py seed_staging $CLEAR_FLAG $DRY_RUN_FLAG

    # Verify
    log_step "Verifying seed data"
    
    # Check if we can get the product list
    log_info "Checking API health..."
    if curl -s https://optimistic-youth-staging.up.railway.app/api/health/ > /dev/null; then
        log_success "API is healthy"
    else
        log_warning "Could not verify API health (may be normal)"
    fi

    # Check if seed products exist
    log_info "Checking seed products..."
    SEED_COUNT=$(railway run python -c "
from api.models import ProductosModel
print(ProductosModel.objects.filter(nombre__startswith='[SEED]').count())
" 2>/dev/null || echo "0")

    if [[ "$SEED_COUNT" -gt 0 ]]; then
        log_success "Found $SEED_COUNT seed products in database"
    else
        log_warning "No seed products found (may need to check manually)"
    fi

    echo ""
    log_success "Seed staging complete!"
    echo ""
    echo "To verify:"
    echo "  railway run python manage.py shell -c \"from api.models import ProductosModel; print(ProductosModel.objects.filter(nombre__startswith='[SEED]').count())\""
    echo ""
    echo "To clear:"
    echo "  ./scripts/seed-staging.sh --clear"
}

# Run main function
main "$@"
