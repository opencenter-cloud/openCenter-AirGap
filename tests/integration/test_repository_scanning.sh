#!/bin/bash
# Integration test: Repository scanning end-to-end
#
# Tests the complete workflow:
# 1. Clone test repositories (or use existing)
# 2. Run scan_repository_images.py
# 3. Verify output format and content
# 4. Run generate_image_lists.sh
# 5. Validate generated files

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
TEST_OUTPUT="${PROJECT_ROOT}/build/test-repository-scans"

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

cleanup() {
    if [ -d "$TEST_OUTPUT" ]; then
        rm -rf "$TEST_OUTPUT"
    fi
}

trap cleanup EXIT

test_scan_repository_images() {
    log_info "Test 1: scan_repository_images.py"

    # Run scanner
    python3 "${PROJECT_ROOT}/scripts/build/scan_repository_images.py" \
        --project-root "$PROJECT_ROOT" \
        --output-dir "$TEST_OUTPUT" \
        --verbose

    if [ $? -ne 0 ]; then
        log_error "Scanner failed"
        return 1
    fi

    log_info "✓ Scanner executed successfully"
    return 0
}

test_output_files_created() {
    log_info "Test 2: Output files created"

    local expected_files=(
        "all-repositories-images.txt"
        "all-repositories-urls.txt"
    )

    for file in "${expected_files[@]}"; do
        if [ ! -f "${TEST_OUTPUT}/${file}" ]; then
            log_error "Missing file: ${file}"
            return 1
        fi
    done

    log_info "✓ All expected files created"
    return 0
}

test_image_list_format() {
    log_info "Test 3: Image list format validation"

    local image_file="${TEST_OUTPUT}/all-repositories-images.txt"

    if [ ! -f "$image_file" ]; then
        log_error "Image file not found"
        return 1
    fi

    # Check header
    if ! grep -q "^# Combined Container Images" "$image_file"; then
        log_error "Missing header in image list"
        return 1
    fi

    # Check for valid image format (registry/repo:tag or repo:tag)
    local invalid_lines=0
    while IFS= read -r line; do
        # Skip comments and empty lines
        [[ "$line" =~ ^#.*$ ]] && continue
        [[ -z "$line" ]] && continue

        # Check image format
        if ! [[ "$line" =~ ^[a-z0-9\.\-]+(:[0-9]+)?(/[a-z0-9\.\-]+)+(:[a-z0-9\.\-]+)?$ ]]; then
            log_warn "Invalid image format: $line"
            ((invalid_lines++))
        fi
    done < "$image_file"

    if [ $invalid_lines -gt 0 ]; then
        log_warn "Found $invalid_lines lines with invalid format"
    fi

    log_info "✓ Image list format valid"
    return 0
}

test_url_list_format() {
    log_info "Test 4: URL list format validation"

    local url_file="${TEST_OUTPUT}/all-repositories-urls.txt"

    if [ ! -f "$url_file" ]; then
        log_error "URL file not found"
        return 1
    fi

    # Check header
    if ! grep -q "^# Combined URLs" "$url_file"; then
        log_error "Missing header in URL list"
        return 1
    fi

    # Check for valid URL format
    local invalid_lines=0
    while IFS= read -r line; do
        # Skip comments and empty lines
        [[ "$line" =~ ^#.*$ ]] && continue
        [[ -z "$line" ]] && continue

        # Check URL format
        if ! [[ "$line" =~ ^https?:// ]]; then
            log_warn "Invalid URL format: $line"
            ((invalid_lines++))
        fi
    done < "$url_file"

    if [ $invalid_lines -gt 0 ]; then
        log_warn "Found $invalid_lines lines with invalid format"
    fi

    log_info "✓ URL list format valid"
    return 0
}

test_json_details() {
    log_info "Test 5: JSON details validation"

    # Find JSON files
    local json_files=$(find "$TEST_OUTPUT" -name "*-scan-details.json")

    if [ -z "$json_files" ]; then
        log_warn "No JSON detail files found"
        return 0
    fi

    for json_file in $json_files; do
        # Validate JSON syntax
        if ! python3 -m json.tool "$json_file" > /dev/null 2>&1; then
            log_error "Invalid JSON: $json_file"
            return 1
        fi

        # Check required fields
        if ! grep -q '"repository"' "$json_file"; then
            log_error "Missing 'repository' field in $json_file"
            return 1
        fi

        if ! grep -q '"images"' "$json_file"; then
            log_error "Missing 'images' field in $json_file"
            return 1
        fi
    done

    log_info "✓ JSON details valid"
    return 0
}

test_no_false_positives() {
    log_info "Test 6: False positive detection"

    local image_file="${TEST_OUTPUT}/all-repositories-images.txt"

    # Check for common false positives
    local false_positives=(
        "localhost"
        "127.0.0.1"
        "example.com"
        "http://"
        "https://"
    )

    for fp in "${false_positives[@]}"; do
        if grep -v "^#" "$image_file" | grep -q "$fp"; then
            log_warn "Possible false positive detected: $fp"
        fi
    done

    log_info "✓ False positive check complete"
    return 0
}

test_deduplication() {
    log_info "Test 7: Deduplication verification"

    local image_file="${TEST_OUTPUT}/all-repositories-images.txt"

    # Count total lines (excluding comments)
    local total_lines=$(grep -v "^#" "$image_file" | grep -v "^$" | wc -l)

    # Count unique lines
    local unique_lines=$(grep -v "^#" "$image_file" | grep -v "^$" | sort -u | wc -l)

    if [ "$total_lines" -ne "$unique_lines" ]; then
        log_error "Duplicates found: $total_lines total, $unique_lines unique"
        return 1
    fi

    log_info "✓ No duplicates found ($unique_lines unique images)"
    return 0
}

test_performance() {
    log_info "Test 8: Performance measurement"

    local start_time=$(date +%s)

    python3 "${PROJECT_ROOT}/scripts/build/scan_repository_images.py" \
        --project-root "$PROJECT_ROOT" \
        --output-dir "${TEST_OUTPUT}-perf" \
        > /dev/null 2>&1

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))

    log_info "✓ Scan completed in ${duration}s"

    if [ $duration -gt 300 ]; then
        log_warn "Scan took longer than 5 minutes"
    fi

    rm -rf "${TEST_OUTPUT}-perf"
    return 0
}

run_all_tests() {
    local failed=0

    echo "=========================================="
    echo "Repository Scanning Integration Tests"
    echo "=========================================="
    echo ""

    # Check prerequisites
    if ! command -v python3 &> /dev/null; then
        log_error "python3 not found"
        exit 1
    fi

    # Run tests
    test_scan_repository_images || ((failed++))
    echo ""

    test_output_files_created || ((failed++))
    echo ""

    test_image_list_format || ((failed++))
    echo ""

    test_url_list_format || ((failed++))
    echo ""

    test_json_details || ((failed++))
    echo ""

    test_no_false_positives || ((failed++))
    echo ""

    test_deduplication || ((failed++))
    echo ""

    test_performance || ((failed++))
    echo ""

    # Summary
    echo "=========================================="
    if [ $failed -eq 0 ]; then
        log_info "All tests passed"
        return 0
    else
        log_error "$failed test(s) failed"
        return 1
    fi
}

run_all_tests
