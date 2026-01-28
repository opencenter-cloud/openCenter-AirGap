#!/usr/bin/env bash
# Integration tests for container image scanning
# Tests Trivy integration and vulnerability threshold enforcement

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
SCAN_SCRIPT="${PROJECT_ROOT}/scripts/build/scan_images.sh"
TEST_OUTPUT_DIR="${PROJECT_ROOT}/build/test-scan"
TEST_IMAGE_LIST="${TEST_OUTPUT_DIR}/test-images.txt"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Logging
log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

log_test() {
    echo -e "${YELLOW}[TEST]${NC} $*"
}

# Test result tracking
pass_test() {
    ((TESTS_PASSED++))
    log_info "✓ PASSED: $1"
}

fail_test() {
    ((TESTS_FAILED++))
    log_error "✗ FAILED: $1"
}

# Setup test environment
setup() {
    log_info "Setting up test environment..."
    mkdir -p "${TEST_OUTPUT_DIR}"

    # Check if Trivy is installed
    if ! command -v trivy &> /dev/null; then
        log_error "Trivy not installed. Skipping integration tests."
        log_info "Install with: curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin"
        exit 77  # Exit code 77 = tests skipped
    fi
}

# Cleanup test environment
cleanup() {
    log_info "Cleaning up test environment..."
    rm -rf "${TEST_OUTPUT_DIR}"
}

# Test 1: Scan script exists and is executable
test_scan_script_exists() {
    ((TESTS_RUN++))
    log_test "Test 1: Scan script exists and is executable"

    if [[ -x "${SCAN_SCRIPT}" ]]; then
        pass_test "Scan script exists and is executable"
    else
        fail_test "Scan script not found or not executable: ${SCAN_SCRIPT}"
    fi
}

# Test 2: Scan clean image (no vulnerabilities)
test_scan_clean_image() {
    ((TESTS_RUN++))
    log_test "Test 2: Scan clean image (should pass)"

    # Create test image list with a known clean image
    cat > "${TEST_IMAGE_LIST}" <<EOF
# Test image list - clean image
alpine:3.19
EOF

    # Override IMAGE_LIST for this test
    if IMAGE_LIST="${TEST_IMAGE_LIST}" OUTPUT_DIR="${TEST_OUTPUT_DIR}" "${SCAN_SCRIPT}" &> "${TEST_OUTPUT_DIR}/clean-scan.log"; then
        # Check that results file was created
        if [[ -f "${TEST_OUTPUT_DIR}/image-scan-results.json" ]]; then
            pass_test "Clean image scan passed"
        else
            fail_test "Results file not created"
        fi
    else
        fail_test "Clean image scan failed unexpectedly"
        cat "${TEST_OUTPUT_DIR}/clean-scan.log"
    fi
}

# Test 3: Scan vulnerable image (should fail on CRITICAL)
test_scan_vulnerable_image() {
    ((TESTS_RUN++))
    log_test "Test 3: Scan vulnerable image (should fail on CRITICAL)"

    # Create test image list with a known vulnerable image
    # Using an old Alpine version known to have vulnerabilities
    cat > "${TEST_IMAGE_LIST}" <<EOF
# Test image list - vulnerable image
alpine:3.2
EOF

    # Clean previous results
    rm -f "${TEST_OUTPUT_DIR}/image-scan-results.json"
    rm -f "${TEST_OUTPUT_DIR}/image-vulnerabilities.txt"

    # Override IMAGE_LIST for this test - expect failure
    if IMAGE_LIST="${TEST_IMAGE_LIST}" OUTPUT_DIR="${TEST_OUTPUT_DIR}" "${SCAN_SCRIPT}" &> "${TEST_OUTPUT_DIR}/vulnerable-scan.log"; then
        # If it passed, check if there were actually no CRITICAL vulnerabilities
        if [[ -f "${TEST_OUTPUT_DIR}/image-vulnerabilities.txt" ]]; then
            if grep -q "CRITICAL: 0" "${TEST_OUTPUT_DIR}/image-vulnerabilities.txt"; then
                log_info "Note: Test image had no CRITICAL vulnerabilities (may have been patched)"
                pass_test "Scan completed (no CRITICAL found in test image)"
            else
                fail_test "Scan should have failed on CRITICAL vulnerabilities"
            fi
        else
            fail_test "Summary file not created"
        fi
    else
        # Expected failure - verify it was due to CRITICAL vulnerabilities
        if [[ -f "${TEST_OUTPUT_DIR}/image-vulnerabilities.txt" ]]; then
            if grep -q "POLICY VIOLATION" "${TEST_OUTPUT_DIR}/image-vulnerabilities.txt"; then
                pass_test "Scan correctly failed on CRITICAL vulnerabilities"
            else
                fail_test "Scan failed but not due to policy violation"
                cat "${TEST_OUTPUT_DIR}/image-vulnerabilities.txt"
            fi
        else
            fail_test "Summary file not created"
        fi
    fi
}

# Test 4: Verify JSON output format
test_json_output_format() {
    ((TESTS_RUN++))
    log_test "Test 4: Verify JSON output format"

    if [[ -f "${TEST_OUTPUT_DIR}/image-scan-results.json" ]]; then
        # Validate JSON structure
        if jq -e '.scan_timestamp' "${TEST_OUTPUT_DIR}/image-scan-results.json" &> /dev/null && \
           jq -e '.images' "${TEST_OUTPUT_DIR}/image-scan-results.json" &> /dev/null; then
            pass_test "JSON output has correct structure"
        else
            fail_test "JSON output missing required fields"
        fi
    else
        fail_test "JSON results file not found"
    fi
}

# Test 5: Verify summary report format
test_summary_report_format() {
    ((TESTS_RUN++))
    log_test "Test 5: Verify summary report format"

    if [[ -f "${TEST_OUTPUT_DIR}/image-vulnerabilities.txt" ]]; then
        # Check for required sections
        if grep -q "Container Image Vulnerability Scan Report" "${TEST_OUTPUT_DIR}/image-vulnerabilities.txt" && \
           grep -q "Summary Statistics" "${TEST_OUTPUT_DIR}/image-vulnerabilities.txt"; then
            pass_test "Summary report has correct format"
        else
            fail_test "Summary report missing required sections"
        fi
    else
        fail_test "Summary report file not found"
    fi
}

# Test 6: Verify threshold enforcement
test_threshold_enforcement() {
    ((TESTS_RUN++))
    log_test "Test 6: Verify threshold enforcement"

    # This test verifies that the script correctly identifies and reports CRITICAL vulnerabilities
    if [[ -f "${TEST_OUTPUT_DIR}/image-vulnerabilities.txt" ]]; then
        # Check that policy decision is present
        if grep -q "POLICY" "${TEST_OUTPUT_DIR}/image-vulnerabilities.txt"; then
            pass_test "Threshold policy enforcement present in report"
        else
            fail_test "Policy decision missing from report"
        fi
    else
        fail_test "Summary report not available for threshold test"
    fi
}

# Test 7: Handle missing image list
test_missing_image_list() {
    ((TESTS_RUN++))
    log_test "Test 7: Handle missing image list gracefully"

    # Try to run with non-existent image list
    if IMAGE_LIST="/nonexistent/images.txt" OUTPUT_DIR="${TEST_OUTPUT_DIR}" "${SCAN_SCRIPT}" &> "${TEST_OUTPUT_DIR}/missing-list.log"; then
        fail_test "Script should fail with missing image list"
    else
        # Check error message
        if grep -q "Image list not found" "${TEST_OUTPUT_DIR}/missing-list.log"; then
            pass_test "Script correctly handles missing image list"
        else
            fail_test "Script failed but with unexpected error"
        fi
    fi
}

# Print test summary
print_summary() {
    echo ""
    echo "=========================================="
    echo "Test Summary"
    echo "=========================================="
    echo "Tests Run:    ${TESTS_RUN}"
    echo "Tests Passed: ${TESTS_PASSED}"
    echo "Tests Failed: ${TESTS_FAILED}"
    echo "=========================================="

    if [[ ${TESTS_FAILED} -eq 0 ]]; then
        log_info "All tests passed!"
        return 0
    else
        log_error "${TESTS_FAILED} test(s) failed"
        return 1
    fi
}

# Main execution
main() {
    log_info "Starting image scanning integration tests..."

    setup

    # Run tests
    test_scan_script_exists
    test_scan_clean_image
    test_scan_vulnerable_image
    test_json_output_format
    test_summary_report_format
    test_threshold_enforcement
    test_missing_image_list

    # Print summary and cleanup
    print_summary
    local exit_code=$?

    cleanup

    exit ${exit_code}
}

# Run main
main "$@"
