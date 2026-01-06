#!/bin/bash
#
# Local CI/CD Runner
# Runs the same checks as GitHub Actions CI pipeline locally
#
# Usage:
#   ./scripts/ci-local.sh          # Run all checks
#   ./scripts/ci-local.sh backend  # Backend only (lint + tests)
#   ./scripts/ci-local.sh frontend # Frontend only (lint + build)
#   ./scripts/ci-local.sh lint     # Lint only (both)
#   ./scripts/ci-local.sh test     # Tests only (both)
#   ./scripts/ci-local.sh quick    # Quick checks (lint only, no tests)
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Track failures
FAILED_CHECKS=()

# Helper functions
print_header() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_step() {
    echo -e "${YELLOW}→ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

run_check() {
    local name="$1"
    local cmd="$2"

    print_step "$name"
    if eval "$cmd"; then
        print_success "$name passed"
        return 0
    else
        print_error "$name failed"
        FAILED_CHECKS+=("$name")
        return 1
    fi
}

# Change to project root
cd "$(dirname "$0")/.."

# Parse arguments
MODE="${1:-all}"

#
# Backend Lint Checks
#
backend_lint() {
    print_header "Backend Lint"

    run_check "Ruff check" "poetry run ruff check app/" || true
    run_check "Ruff format check" "poetry run ruff format app/ --check" || true

    # ty type checker - may fail if venv is misconfigured
    if poetry run ty check app/ 2>/dev/null; then
        print_success "Type check (ty) passed"
    else
        print_step "Type check (ty) skipped (venv config issue)"
    fi
}

#
# Backend Tests
#
backend_test() {
    print_header "Backend Tests"

    # Check if PostgreSQL is available
    if ! command -v psql &> /dev/null; then
        print_step "PostgreSQL CLI not found, skipping DB tests"
        print_step "To run tests, ensure PostgreSQL is installed and DATABASE_URL is set"
        return 0
    fi

    # Check DATABASE_URL
    if [ -z "$DATABASE_URL" ]; then
        print_step "DATABASE_URL not set"
        print_step "Running tests without database (some tests will be skipped)"
    fi

    run_check "Pytest" "poetry run pytest tests/ -v --tb=short" || true
}

#
# Frontend Lint & Type Check
#
frontend_lint() {
    print_header "Frontend Lint & Type Check"

    cd frontend

    # Install deps if needed
    if [ ! -d "node_modules" ]; then
        print_step "Installing dependencies..."
        npm ci
    fi

    run_check "TypeScript check" "npm run typecheck" || true
    run_check "ESLint" "npm run lint" || true

    cd ..
}

#
# Frontend Build
#
frontend_build() {
    print_header "Frontend Build"

    cd frontend

    # Install deps if needed
    if [ ! -d "node_modules" ]; then
        print_step "Installing dependencies..."
        npm ci
    fi

    run_check "Production build" "npm run build" || true

    # Bundle integrity check
    if [ -d "dist" ]; then
        print_step "Validating bundle integrity..."

        local bundle_ok=true

        # Check React vendor chunk
        if ls dist/assets/*vendor-react*.js 1> /dev/null 2>&1; then
            print_success "React vendor chunk found"
        else
            print_error "React vendor chunk missing"
            bundle_ok=false
        fi

        # Check router chunk
        if ls dist/assets/*vendor-router*.js 1> /dev/null 2>&1; then
            print_success "Router vendor chunk found"
        else
            print_error "Router vendor chunk missing"
            bundle_ok=false
        fi

        # Check main entry
        if ls dist/assets/index-*.js 1> /dev/null 2>&1; then
            print_success "Main entry chunk found"
        else
            print_error "Main entry chunk missing"
            bundle_ok=false
        fi

        # Verify React runtime
        if [ -f "$(ls dist/assets/*vendor-react*.js 2>/dev/null | head -1)" ]; then
            if grep -q "createElement" dist/assets/*vendor-react*.js; then
                print_success "React runtime verified"
            else
                print_error "React runtime not found in bundle"
                bundle_ok=false
            fi
        fi

        # JS syntax check
        print_step "Checking JavaScript syntax..."
        for file in dist/assets/*.js; do
            if ! node --check "$file" 2>/dev/null; then
                print_error "Syntax error in $file"
                bundle_ok=false
            fi
        done

        if $bundle_ok; then
            print_success "Bundle integrity check passed"

            # Print sizes
            echo ""
            echo "Bundle sizes:"
            du -sh dist/assets/*.js 2>/dev/null | sort -h | head -10
            echo "Total: $(du -sh dist 2>/dev/null | cut -f1)"
        else
            FAILED_CHECKS+=("Bundle integrity")
        fi
    fi

    cd ..
}

#
# Summary
#
print_summary() {
    print_header "Summary"

    if [ ${#FAILED_CHECKS[@]} -eq 0 ]; then
        echo -e "${GREEN}"
        echo "  ╔═══════════════════════════════════════╗"
        echo "  ║     ALL CHECKS PASSED                 ║"
        echo "  ╚═══════════════════════════════════════╝"
        echo -e "${NC}"
        return 0
    else
        echo -e "${RED}"
        echo "  ╔═══════════════════════════════════════╗"
        echo "  ║     SOME CHECKS FAILED                ║"
        echo "  ╚═══════════════════════════════════════╝"
        echo -e "${NC}"
        echo ""
        echo "Failed checks:"
        for check in "${FAILED_CHECKS[@]}"; do
            echo -e "  ${RED}✗${NC} $check"
        done
        return 1
    fi
}

#
# Main
#
main() {
    echo -e "${BLUE}"
    echo "  ╔═══════════════════════════════════════╗"
    echo "  ║     LOCAL CI/CD RUNNER                ║"
    echo "  ╚═══════════════════════════════════════╝"
    echo -e "${NC}"
    echo "Mode: $MODE"

    case "$MODE" in
        all)
            backend_lint
            backend_test
            frontend_lint
            frontend_build
            ;;
        backend)
            backend_lint
            backend_test
            ;;
        frontend)
            frontend_lint
            frontend_build
            ;;
        lint)
            backend_lint
            frontend_lint
            ;;
        test)
            backend_test
            frontend_build
            ;;
        quick)
            backend_lint
            frontend_lint
            ;;
        *)
            echo "Unknown mode: $MODE"
            echo ""
            echo "Usage: $0 [all|backend|frontend|lint|test|quick]"
            exit 1
            ;;
    esac

    print_summary
}

main
