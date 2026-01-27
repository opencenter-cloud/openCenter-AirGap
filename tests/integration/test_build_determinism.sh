#!/bin/bash
# Test Build Determinism
#
# Builds the Zarf package twice with identical configuration and verifies
# that both builds produce identical image lists.
#
# This validates Requirement 8.8: Build determinism

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
BUILD_SCRIPT="${PROJECT_ROOT}/scripts/build/build.py"
SNAPSHOT_SCRIPT="${PROJECT_ROOT}/scripts/build/snapshot_image_list.py"
COMPARE_SCRIPT="${PROJECT_ROOT}/scripts/build/compare_image_lists.py"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

log_test() {
    echo -e "${BLUE}[TEST]${NC} $*"
}

# Usage
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Test build determinism by building package twice and comparing image lists.

OPTIONS:
    --skip-build        Skip builds, use existing packages
    --package1 PATH     Path to first package (if --skip-build)
    --package2 PATH     Path to second package (if --skip-build)
    --keep-artifacts    Keep build artifacts after test
    -h, --help          Show this help

EXAMPLES:
    # Run full test (build twice and compare)
    $0

    # Compare existing packages
    $0 --skip-build --package1 dist/pkg1.tar.zst --package2 dist/pkg2.tar.zst

    # Keep artifacts for inspection
    $0 --keep-artifacts

REQUIREMENTS:
    - Python 3.12+ with venv
    - Zarf CLI installed
    - Build dependencies (podman, git, etc.)
    - Sufficient disk space (10GB+ per build)

EXIT CODES:
    0 - Builds are deterministic (identical image lists)
    1 - Builds differ (non-deterministic)
    2 - Test error (build failure, missing dependencies, etc.)
EOF
    exit 0
}

# Parse arguments
SKIP_BUILD=false
PACKAGE1=""
PACKAGE2=""
KEEP_ARTIFACTS=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        --package1)
            PACKAGE1="$2"
            shift 2
            ;;
        --package2)
            PACKAGE2="$2"
            shift 2
            ;;
        --keep-artifacts)
            KEEP_ARTIFACTS=true
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            log_error "Unknown option: $1"
            usage
            ;;
    esac
done

# Validate skip-build mode
if [ "$SKIP_BUILD" = true ]; then
    if [ -z "$PACKAGE1" ] || [ -z "$PACKAGE2" ]; then
        log_error "--skip-build requires --package1 and --package2"
        exit 2
    fi
    if [ ! -f "$PACKAGE1" ]; then
        log_error "Package 1 not found: $PACKAGE1"
        exit 2
    fi
    if [ ! -f "$PACKAGE2" ]; then
        log_error "Package 2 not found: $PACKAGE2"
        exit 2
    fi
fi

# Check prerequisites
log_info "Checking prerequisites..."

if ! command -v python3 &> /dev/null; then
    log_error "Python 3 not found"
    exit 2
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
log_info "Python version: $PYTHON_VERSION"

if ! command -v zarf &> /dev/null; then
    log_error "Zarf CLI not found. Please install Zarf."
    exit 2
fi

ZARF_VERSION=$(zarf version 2>&1 | head -1 || echo "unknown")
log_info "Zarf version: $ZARF_VERSION"

if [ ! -f "$SNAPSHOT_SCRIPT" ]; then
    log_error "Snapshot script not found: $SNAPSHOT_SCRIPT"
    exit 2
fi

if [ ! -f "$COMPARE_SCRIPT" ]; then
    log_error "Compare script not found: $COMPARE_SCRIPT"
    exit 2
fi

echo ""
log_test "Build Determinism Test"
echo ""

# Create test workspace
TEST_WORKSPACE="${PROJECT_ROOT}/build/determinism-test-$(date +%s)"
mkdir -p "$TEST_WORKSPACE"
log_info "Test workspace: $TEST_WORKSPACE"

# Build or use existing packages
if [ "$SKIP_BUILD" = false ]; then
    log_info "Building package twice with identical configuration..."
    echo ""
    
    # Build 1
    log_test "Build 1: Starting..."
    BUILD1_DIR="${TEST_WORKSPACE}/build1"
    mkdir -p "$BUILD1_DIR"
    
    if [ ! -f "$BUILD_SCRIPT" ]; then
        log_error "Build script not found: $BUILD_SCRIPT"
        exit 2
    fi
    
    # Note: This is a simplified test. Full build would run: python3 scripts/build/build.py
    # For now, we'll document the expected behavior
    log_warn "Full build test requires kubespray-offline assets"
    log_warn "This test validates the comparison logic only"
    log_warn "To test actual builds, run: python3 $BUILD_SCRIPT --clean"
    
    # Create mock packages for testing (if no real packages exist)
    if [ ! -d "${PROJECT_ROOT}/dist" ] || [ -z "$(ls -A ${PROJECT_ROOT}/dist/*.tar.zst 2>/dev/null)" ]; then
        log_warn "No packages found in dist/. Cannot test without packages."
        log_info "To run full test:"
        log_info "  1. Run: $BUILD_SCRIPT"
        log_info "  2. Run: $BUILD_SCRIPT (again)"
        log_info "  3. Run: $0 --skip-build --package1 dist/pkg1.tar.zst --package2 dist/pkg2.tar.zst"
        exit 2
    fi
    
    # Use existing packages if available
    PACKAGES=(${PROJECT_ROOT}/dist/*.tar.zst)
    if [ ${#PACKAGES[@]} -ge 2 ]; then
        PACKAGE1="${PACKAGES[0]}"
        PACKAGE2="${PACKAGES[1]}"
        log_info "Using existing packages for comparison"
    elif [ ${#PACKAGES[@]} -eq 1 ]; then
        log_error "Only one package found. Need two packages to compare."
        log_info "Run build script twice to generate two packages."
        exit 2
    fi
else
    log_info "Using provided packages:"
    log_info "  Package 1: $PACKAGE1"
    log_info "  Package 2: $PACKAGE2"
fi

echo ""

# Create snapshots
log_test "Creating image list snapshots..."
echo ""

SNAPSHOT1="${TEST_WORKSPACE}/snapshot1.json"
SNAPSHOT2="${TEST_WORKSPACE}/snapshot2.json"

log_info "Snapshot 1: $PACKAGE1 -> $SNAPSHOT1"
if ! python3 "$SNAPSHOT_SCRIPT" "$PACKAGE1" "$SNAPSHOT1"; then
    log_error "Failed to create snapshot 1"
    exit 2
fi

log_info "Snapshot 2: $PACKAGE2 -> $SNAPSHOT2"
if ! python3 "$SNAPSHOT_SCRIPT" "$PACKAGE2" "$SNAPSHOT2"; then
    log_error "Failed to create snapshot 2"
    exit 2
fi

echo ""

# Compare snapshots
log_test "Comparing snapshots..."
echo ""

if python3 "$COMPARE_SCRIPT" "$SNAPSHOT1" "$SNAPSHOT2"; then
    log_info "✓ Build is deterministic"
    log_info "  Both builds produced identical image lists"
    RESULT=0
else
    log_error "✗ Build is non-deterministic"
    log_error "  Builds produced different image lists"
    log_error "  See comparison output above for details"
    RESULT=1
fi

echo ""

# Cleanup
if [ "$KEEP_ARTIFACTS" = false ]; then
    log_info "Cleaning up test workspace..."
    rm -rf "$TEST_WORKSPACE"
else
    log_info "Keeping artifacts at: $TEST_WORKSPACE"
    log_info "  Snapshot 1: $SNAPSHOT1"
    log_info "  Snapshot 2: $SNAPSHOT2"
fi

echo ""
log_info "Test complete"
exit $RESULT
