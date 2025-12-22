#!/bin/bash
# Frontend deployment script for Vercel
# Ensures clean builds and proper deployment without stale cache issues

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Wonder Scraper Frontend Deploy ===${NC}"

# Check if we're in the right place
if [ ! -d "$FRONTEND_DIR" ]; then
    echo -e "${RED}Error: frontend directory not found at $FRONTEND_DIR${NC}"
    exit 1
fi

# Parse arguments
ENVIRONMENT="production"
SKIP_BUILD=false
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --staging)
            ENVIRONMENT="staging"
            shift
            ;;
        --preview)
            ENVIRONMENT="preview"
            shift
            ;;
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            echo "Usage: deploy-frontend.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --staging     Deploy to staging environment"
            echo "  --preview     Deploy as preview deployment"
            echo "  --skip-build  Skip npm build (use existing dist)"
            echo "  --dry-run     Show what would be deployed without deploying"
            echo "  -h, --help    Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

echo -e "Environment: ${YELLOW}$ENVIRONMENT${NC}"

# Step 1: Clean stale Vercel cache
echo -e "\n${GREEN}Step 1: Cleaning stale Vercel cache...${NC}"
if [ -d "$PROJECT_ROOT/.vercel/output" ]; then
    echo "Removing .vercel/output..."
    rm -rf "$PROJECT_ROOT/.vercel/output"
fi
if [ -d "$PROJECT_ROOT/.vercel/builders" ]; then
    echo "Removing .vercel/builders..."
    rm -rf "$PROJECT_ROOT/.vercel/builders"
fi

# Step 2: Build frontend
if [ "$SKIP_BUILD" = false ]; then
    echo -e "\n${GREEN}Step 2: Building frontend...${NC}"
    cd "$FRONTEND_DIR"

    # Clean previous build
    rm -rf dist

    # Install dependencies if needed
    if [ ! -d "node_modules" ]; then
        echo "Installing dependencies..."
        npm ci
    fi

    # Run type check first
    echo "Running type check..."
    npm run typecheck || {
        echo -e "${RED}Type check failed! Fix errors before deploying.${NC}"
        exit 1
    }

    # Build
    echo "Building..."
    npm run build || {
        echo -e "${RED}Build failed!${NC}"
        exit 1
    }

    cd "$PROJECT_ROOT"
else
    echo -e "\n${YELLOW}Step 2: Skipping build (--skip-build)${NC}"
fi

# Step 3: Validate bundle integrity
echo -e "\n${GREEN}Step 3: Validating bundle integrity...${NC}"
DIST_DIR="$FRONTEND_DIR/dist"

if [ ! -d "$DIST_DIR" ]; then
    echo -e "${RED}Error: dist directory not found. Run build first.${NC}"
    exit 1
fi

# Check that index.html exists
if [ ! -f "$DIST_DIR/index.html" ]; then
    echo -e "${RED}Error: index.html not found in dist${NC}"
    exit 1
fi

# Check for React vendor chunk
if ! ls "$DIST_DIR/assets/"*vendor-react*.js 1> /dev/null 2>&1; then
    echo -e "${RED}Error: React vendor chunk not found${NC}"
    exit 1
fi

# Verify React is loaded in correct order in index.html
# The vendor-react chunk should be loaded before the main chunk
if grep -q 'modulepreload.*vendor-react' "$DIST_DIR/index.html"; then
    echo "React module preload found"
else
    echo -e "${YELLOW}Warning: React modulepreload not found (may be handled differently)${NC}"
fi

# Check bundle sizes
echo ""
echo "Bundle sizes:"
du -sh "$DIST_DIR/assets/"*.js 2>/dev/null | sort -h | tail -10
echo ""

TOTAL_SIZE=$(du -sh "$DIST_DIR" | cut -f1)
echo -e "Total dist size: ${YELLOW}$TOTAL_SIZE${NC}"

# Step 4: Deploy
if [ "$DRY_RUN" = true ]; then
    echo -e "\n${YELLOW}Step 4: Dry run - skipping actual deployment${NC}"
    echo "Would deploy to: $ENVIRONMENT"
    echo "From directory: $DIST_DIR"
    exit 0
fi

echo -e "\n${GREEN}Step 4: Deploying to Vercel ($ENVIRONMENT)...${NC}"

# Check for vercel CLI
if ! command -v vercel &> /dev/null; then
    echo -e "${RED}Error: vercel CLI not found. Install with: npm i -g vercel${NC}"
    exit 1
fi

cd "$PROJECT_ROOT"

# Deploy based on environment
case $ENVIRONMENT in
    production)
        echo "Deploying to production..."
        vercel --prod
        ;;
    staging)
        echo "Deploying to staging..."
        vercel
        ;;
    preview)
        echo "Creating preview deployment..."
        vercel
        ;;
esac

echo -e "\n${GREEN}Deploy complete!${NC}"
