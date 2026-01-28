#!/bin/bash
set -euo pipefail

# Integration test for Zarf YAML generation
#
# Tests the complete workflow:
# 1. Generate image lists
# 2. Generate zarf.yaml from template
# 3. Validate YAML syntax
# 4. Verify images block is present

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

# Test counter
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

run_test() {
    local test_name="$1"
    local test_cmd="$2"

    TESTS_RUN=$((TESTS_RUN + 1))

    echo ""
    log_info "Test ${TESTS_RUN}: ${test_name}"

    if eval "${test_cmd}"; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
        log_info "✓ PASSED"
        return 0
    else
        TESTS_FAILED=$((TESTS_FAILED + 1))
        log_error "✗ FAILED"
        return 1
    fi
}

# Test 1: Verify template exists
test_template_exists() {
    [ -f "${PROJECT_ROOT}/zarf.yaml.template" ]
}

# Test 2: Verify template has placeholder
test_template_has_placeholder() {
    grep -q "###IMAGES_BLOCK###" "${PROJECT_ROOT}/zarf.yaml.template"
}

# Test 3: Generate images block
test_generate_images_block() {
    python3 "${PROJECT_ROOT}/scripts/build/generate_zarf_images_block.py" > /tmp/images_block.yaml 2>&1
}

# Test 4: Verify images block format
test_images_block_format() {
    grep -q "^  images:" /tmp/images_block.yaml && \
    grep -q "^    - " /tmp/images_block.yaml
}

# Test 5: Generate complete zarf.yaml
test_generate_zarf_yaml() {
    python3 "${PROJECT_ROOT}/scripts/build/generate_zarf_yaml.py" 2>&1 | grep -q "Generated"
}

# Test 6: Verify generated zarf.yaml exists
test_zarf_yaml_exists() {
    [ -f "${PROJECT_ROOT}/zarf.yaml" ]
}

# Test 7: Verify zarf.yaml has images block
test_zarf_yaml_has_images() {
    grep -q "^  images:" "${PROJECT_ROOT}/zarf.yaml" && \
    grep -q "^    - " "${PROJECT_ROOT}/zarf.yaml"
}

# Test 8: Verify zarf.yaml has no placeholder
test_zarf_yaml_no_placeholder() {
    ! grep -q "###IMAGES_BLOCK###" "${PROJECT_ROOT}/zarf.yaml"
}

# Test 9: Validate YAML syntax with yq (if available)
test_yaml_syntax() {
    if command -v yq &> /dev/null; then
        yq eval . "${PROJECT_ROOT}/zarf.yaml" > /dev/null 2>&1
    else
        log_warn "yq not installed, skipping YAML validation"
        return 0
    fi
}

# Test 10: Verify image count matches
test_image_count() {
    local template_count=$(grep -c "^    - " /tmp/images_block.yaml || echo 0)
    local yaml_count=$(grep -c "^    - " "${PROJECT_ROOT}/zarf.yaml" || echo 0)

    [ "${template_count}" -eq "${yaml_count}" ]
}

# Main execution
main() {
    log_info "Starting Zarf YAML generation integration tests"
    log_info "Project root: ${PROJECT_ROOT}"
    echo ""

    # Backup existing zarf.yaml
    if [ -f "${PROJECT_ROOT}/zarf.yaml" ]; then
        cp "${PROJECT_ROOT}/zarf.yaml" "${PROJECT_ROOT}/zarf.yaml.backup"
        log_info "Backed up existing zarf.yaml"
    fi

    # Run tests
    run_test "Template file exists" "test_template_exists"
    run_test "Template has placeholder" "test_template_has_placeholder"
    run_test "Generate images block" "test_generate_images_block"
    run_test "Images block format valid" "test_images_block_format"
    run_test "Generate complete zarf.yaml" "test_generate_zarf_yaml"
    run_test "Generated zarf.yaml exists" "test_zarf_yaml_exists"
    run_test "zarf.yaml has images block" "test_zarf_yaml_has_images"
    run_test "zarf.yaml has no placeholder" "test_zarf_yaml_no_placeholder"
    run_test "YAML syntax valid" "test_yaml_syntax"
    run_test "Image count matches" "test_image_count"

    # Summary
    echo ""
    echo "========================================"
    echo "Test Summary"
    echo "========================================"
    echo "Tests run:    ${TESTS_RUN}"
    echo "Tests passed: ${TESTS_PASSED}"
    echo "Tests failed: ${TESTS_FAILED}"
    echo ""

    # Restore backup
    if [ -f "${PROJECT_ROOT}/zarf.yaml.backup" ]; then
        mv "${PROJECT_ROOT}/zarf.yaml.backup" "${PROJECT_ROOT}/zarf.yaml"
        log_info "Restored original zarf.yaml"
    fi

    # Cleanup
    rm -f /tmp/images_block.yaml

    if [ ${TESTS_FAILED} -eq 0 ]; then
        log_info "All tests passed!"
        exit 0
    else
        log_error "${TESTS_FAILED} test(s) failed"
        exit 1
    fi
}

main "$@"
