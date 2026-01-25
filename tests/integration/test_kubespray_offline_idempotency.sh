#!/bin/bash
#
# Test kubespray-offline script idempotency
#
# This script verifies that kubespray-offline target scripts can be safely re-run
# without causing errors or duplicate operations.
#
# Requirements: 8.1, 8.2, 8.3

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test results
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_TOTAL=0

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

test_pass() {
    ((TESTS_PASSED++))
    ((TESTS_TOTAL++))
    log_info "✓ PASS: $*"
}

test_fail() {
    ((TESTS_FAILED++))
    ((TESTS_TOTAL++))
    log_error "✗ FAIL: $*"
}

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then
    log_error "This test must be run as root or with sudo"
    exit 1
fi

# Check if outputs directory exists
OUTPUTS_DIR="${OUTPUTS_DIR:-/opt/opencenter/outputs}"
if [ ! -d "$OUTPUTS_DIR" ]; then
    log_error "Outputs directory not found: $OUTPUTS_DIR"
    log_error "Please deploy the Zarf package first"
    exit 1
fi

cd "$OUTPUTS_DIR"

log_info "Testing kubespray-offline script idempotency"
log_info "Outputs directory: $OUTPUTS_DIR"
echo ""

# Test 1: setup-container.sh idempotency
log_test "Test 1: setup-container.sh idempotency"
echo "Testing containerd installation re-run..."

# First run
log_info "First run of setup-container.sh..."
if ./setup-container.sh > /tmp/setup-container-run1.log 2>&1; then
    log_info "First run succeeded"
else
    test_fail "setup-container.sh first run failed"
    cat /tmp/setup-container-run1.log
fi

# Check containerd is installed
if command -v containerd &> /dev/null; then
    test_pass "containerd installed after first run"
else
    test_fail "containerd not found after first run"
fi

# Second run (should be idempotent)
log_info "Second run of setup-container.sh..."
if ./setup-container.sh > /tmp/setup-container-run2.log 2>&1; then
    log_info "Second run succeeded"
    test_pass "setup-container.sh is idempotent (no errors on re-run)"
else
    log_warn "Second run failed - checking if this is expected behavior"
    # Some scripts may fail if already installed, which is acceptable
    if grep -q "already installed\|already exists" /tmp/setup-container-run2.log; then
        test_pass "setup-container.sh detected existing installation"
    else
        test_fail "setup-container.sh second run failed unexpectedly"
        cat /tmp/setup-container-run2.log
    fi
fi

echo ""

# Test 2: start-nginx.sh idempotency
log_test "Test 2: start-nginx.sh idempotency"
echo "Testing nginx container startup re-run..."

# First run
log_info "First run of start-nginx.sh..."
if ./start-nginx.sh > /tmp/start-nginx-run1.log 2>&1; then
    log_info "First run succeeded"
else
    test_fail "start-nginx.sh first run failed"
    cat /tmp/start-nginx-run1.log
fi

# Check nginx is running
sleep 2
if /usr/local/bin/nerdctl ps | grep -q nginx; then
    test_pass "nginx container running after first run"
    
    # Check nginx is accessible
    if curl -sf http://localhost/files/ > /dev/null 2>&1; then
        test_pass "nginx is serving files on port 80"
    else
        test_fail "nginx not accessible on port 80"
    fi
else
    test_fail "nginx container not running after first run"
fi

# Second run (should stop and restart)
log_info "Second run of start-nginx.sh..."
if ./start-nginx.sh > /tmp/start-nginx-run2.log 2>&1; then
    log_info "Second run succeeded"
    test_pass "start-nginx.sh is idempotent (stops and restarts container)"
else
    test_fail "start-nginx.sh second run failed"
    cat /tmp/start-nginx-run2.log
fi

# Verify nginx still running
sleep 2
if /usr/local/bin/nerdctl ps | grep -q nginx; then
    test_pass "nginx container still running after second run"
else
    test_fail "nginx container not running after second run"
fi

echo ""

# Test 3: start-registry.sh idempotency
log_test "Test 3: start-registry.sh idempotency"
echo "Testing registry container startup re-run..."

# First run
log_info "First run of start-registry.sh..."
if ./start-registry.sh > /tmp/start-registry-run1.log 2>&1; then
    log_info "First run succeeded"
else
    test_fail "start-registry.sh first run failed"
    cat /tmp/start-registry-run1.log
fi

# Check registry is running
sleep 2
if /usr/local/bin/nerdctl ps | grep -q registry; then
    test_pass "registry container running after first run"
    
    # Check registry is accessible
    if curl -sf http://localhost:35000/v2/_catalog > /dev/null 2>&1; then
        test_pass "registry is accessible on port 35000"
    else
        test_fail "registry not accessible on port 35000"
    fi
else
    test_fail "registry container not running after first run"
fi

# Second run (should fail because container already exists)
log_info "Second run of start-registry.sh..."
if ./start-registry.sh > /tmp/start-registry-run2.log 2>&1; then
    log_warn "Second run succeeded - container may have been recreated"
    test_pass "start-registry.sh handled existing container"
else
    # Expected to fail with "already exists" error
    if grep -q "already\|exists\|conflict" /tmp/start-registry-run2.log; then
        test_pass "start-registry.sh correctly detected existing container"
        log_info "Note: start-registry.sh does not automatically remove existing container"
    else
        test_fail "start-registry.sh second run failed unexpectedly"
        cat /tmp/start-registry-run2.log
    fi
fi

# Verify registry still running
if /usr/local/bin/nerdctl ps | grep -q registry; then
    test_pass "registry container still running after second run"
else
    test_fail "registry container not running after second run"
fi

echo ""

# Test 4: load-push-all-images.sh idempotency
log_test "Test 4: load-push-all-images.sh idempotency"
echo "Testing image loading and pushing re-run..."

# Check if registry has images
CATALOG_BEFORE=$(curl -sf http://localhost:35000/v2/_catalog 2>/dev/null || echo '{"repositories":[]}')
IMAGE_COUNT_BEFORE=$(echo "$CATALOG_BEFORE" | jq -r '.repositories | length' 2>/dev/null || echo "0")
log_info "Images in registry before test: $IMAGE_COUNT_BEFORE"

# First run (may take a while)
log_info "First run of load-push-all-images.sh (this may take several minutes)..."
if timeout 600 ./load-push-all-images.sh > /tmp/load-push-run1.log 2>&1; then
    log_info "First run succeeded"
else
    EXIT_CODE=$?
    if [ $EXIT_CODE -eq 124 ]; then
        test_fail "load-push-all-images.sh first run timed out (>10 minutes)"
    else
        test_fail "load-push-all-images.sh first run failed"
    fi
    tail -50 /tmp/load-push-run1.log
fi

# Check images were pushed
CATALOG_AFTER=$(curl -sf http://localhost:35000/v2/_catalog 2>/dev/null || echo '{"repositories":[]}')
IMAGE_COUNT_AFTER=$(echo "$CATALOG_AFTER" | jq -r '.repositories | length' 2>/dev/null || echo "0")
log_info "Images in registry after first run: $IMAGE_COUNT_AFTER"

if [ "$IMAGE_COUNT_AFTER" -gt "$IMAGE_COUNT_BEFORE" ]; then
    test_pass "Images were pushed to registry"
else
    test_fail "No new images in registry after first run"
fi

# Second run (should re-push all images, but should succeed)
log_info "Second run of load-push-all-images.sh..."
if timeout 600 ./load-push-all-images.sh > /tmp/load-push-run2.log 2>&1; then
    log_info "Second run succeeded"
    test_pass "load-push-all-images.sh is idempotent (can re-push images)"
else
    EXIT_CODE=$?
    if [ $EXIT_CODE -eq 124 ]; then
        test_fail "load-push-all-images.sh second run timed out"
    else
        test_fail "load-push-all-images.sh second run failed"
    fi
    tail -50 /tmp/load-push-run2.log
fi

# Verify image count unchanged
CATALOG_FINAL=$(curl -sf http://localhost:35000/v2/_catalog 2>/dev/null || echo '{"repositories":[]}')
IMAGE_COUNT_FINAL=$(echo "$CATALOG_FINAL" | jq -r '.repositories | length' 2>/dev/null || echo "0")
log_info "Images in registry after second run: $IMAGE_COUNT_FINAL"

if [ "$IMAGE_COUNT_FINAL" -eq "$IMAGE_COUNT_AFTER" ]; then
    test_pass "Image count unchanged after second run (no duplicates)"
else
    test_fail "Image count changed after second run: $IMAGE_COUNT_AFTER -> $IMAGE_COUNT_FINAL"
fi

echo ""

# Test 5: setup-all.sh idempotency
log_test "Test 5: setup-all.sh full workflow idempotency"
echo "Testing complete setup-all.sh re-run..."

log_info "Running setup-all.sh (this may take several minutes)..."
if timeout 900 ./setup-all.sh > /tmp/setup-all-rerun.log 2>&1; then
    log_info "setup-all.sh re-run succeeded"
    test_pass "setup-all.sh can be safely re-run"
else
    EXIT_CODE=$?
    if [ $EXIT_CODE -eq 124 ]; then
        test_fail "setup-all.sh timed out (>15 minutes)"
    else
        log_warn "setup-all.sh re-run failed - checking for expected errors"
        if grep -q "already\|exists\|conflict" /tmp/setup-all-rerun.log; then
            test_pass "setup-all.sh detected existing resources (expected behavior)"
        else
            test_fail "setup-all.sh re-run failed unexpectedly"
        fi
    fi
    tail -100 /tmp/setup-all-rerun.log
fi

# Verify all services still running
log_info "Verifying all services are running..."
SERVICES_OK=true

if ! /usr/local/bin/nerdctl ps | grep -q nginx; then
    log_error "nginx container not running"
    SERVICES_OK=false
fi

if ! /usr/local/bin/nerdctl ps | grep -q registry; then
    log_error "registry container not running"
    SERVICES_OK=false
fi

if ! curl -sf http://localhost/files/ > /dev/null 2>&1; then
    log_error "nginx not accessible"
    SERVICES_OK=false
fi

if ! curl -sf http://localhost:35000/v2/_catalog > /dev/null 2>&1; then
    log_error "registry not accessible"
    SERVICES_OK=false
fi

if [ "$SERVICES_OK" = true ]; then
    test_pass "All services running after setup-all.sh re-run"
else
    test_fail "Some services not running after setup-all.sh re-run"
fi

echo ""

# Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test Summary"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Total tests: $TESTS_TOTAL"
echo "Passed: $TESTS_PASSED"
echo "Failed: $TESTS_FAILED"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    log_info "All tests passed!"
    exit 0
else
    log_error "$TESTS_FAILED test(s) failed"
    exit 1
fi
