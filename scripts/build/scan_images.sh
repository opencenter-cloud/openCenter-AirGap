#!/usr/bin/env bash
# Container Image Vulnerability Scanning
# Scans all images in config/all-images.txt using Trivy
# Generates JSON results and summary report
# Fails build on CRITICAL vulnerabilities

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
IMAGE_LIST="${PROJECT_ROOT}/config/all-images.txt"
OUTPUT_DIR="${PROJECT_ROOT}/build"
RESULTS_FILE="${OUTPUT_DIR}/image-scan-results.json"
SUMMARY_FILE="${OUTPUT_DIR}/image-vulnerabilities.txt"
TEMP_DIR="${OUTPUT_DIR}/trivy-temp"

# Vulnerability thresholds
FAIL_ON_SEVERITY="CRITICAL"
WARN_ON_SEVERITY="HIGH"

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    if ! command -v trivy &> /dev/null; then
        log_error "Trivy not found. Install with:"
        log_error "  curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b /usr/local/bin"
        exit 1
    fi

    local trivy_version
    trivy_version=$(trivy --version | head -n1)
    log_info "Found ${trivy_version}"

    if [[ ! -f "${IMAGE_LIST}" ]]; then
        log_error "Image list not found: ${IMAGE_LIST}"
        exit 1
    fi
}

# Initialize output directory
init_output() {
    log_info "Initializing output directory..."
    mkdir -p "${OUTPUT_DIR}"
    mkdir -p "${TEMP_DIR}"

    # Initialize results file
    echo '{"scan_timestamp": "'$(date -u +"%Y-%m-%dT%H:%M:%SZ")'", "images": []}' > "${RESULTS_FILE}"

    # Initialize summary file
    cat > "${SUMMARY_FILE}" <<EOF
Container Image Vulnerability Scan Report
==========================================
Scan Date: $(date -u +"%Y-%m-%d %H:%M:%S UTC")
Policy: Fail on ${FAIL_ON_SEVERITY}, Warn on ${WARN_ON_SEVERITY}

EOF
}

# Scan single image
scan_image() {
    local image="$1"
    local temp_result="${TEMP_DIR}/$(echo "${image}" | tr '/:' '_').json"

    log_info "Scanning ${image}..."

    # Run Trivy scan
    if trivy image \
        --format json \
        --output "${temp_result}" \
        --severity "${WARN_ON_SEVERITY},${FAIL_ON_SEVERITY}" \
        --timeout 10m \
        "${image}" 2>&1 | grep -v "^$"; then

        # Parse results
        local critical_count high_count
        critical_count=$(jq '[.Results[]?.Vulnerabilities[]? | select(.Severity == "CRITICAL")] | length' "${temp_result}" 2>/dev/null || echo "0")
        high_count=$(jq '[.Results[]?.Vulnerabilities[]? | select(.Severity == "HIGH")] | length' "${temp_result}" 2>/dev/null || echo "0")

        echo "${image}|${critical_count}|${high_count}|${temp_result}"
        return 0
    else
        log_warn "Failed to scan ${image}"
        echo "${image}|ERROR|ERROR|${temp_result}"
        return 1
    fi
}

# Aggregate results
aggregate_results() {
    log_info "Aggregating scan results..."

    local total_images=0
    local scanned_images=0
    local failed_scans=0
    local total_critical=0
    local total_high=0
    local images_with_critical=0

    # Read image list
    while IFS= read -r image || [[ -n "${image}" ]]; do
        # Skip empty lines and comments
        [[ -z "${image}" || "${image}" =~ ^[[:space:]]*# ]] && continue

        ((total_images++))

        # Scan image
        local result
        if result=$(scan_image "${image}"); then
            ((scanned_images++))

            IFS='|' read -r img_name critical high temp_file <<< "${result}"

            # Update counters
            ((total_critical += critical))
            ((total_high += high))

            if [[ ${critical} -gt 0 ]]; then
                ((images_with_critical++))
            fi

            # Append to summary
            if [[ ${critical} -gt 0 || ${high} -gt 0 ]]; then
                cat >> "${SUMMARY_FILE}" <<EOF

Image: ${img_name}
  CRITICAL: ${critical}
  HIGH: ${high}
EOF

                # Add top 5 critical vulnerabilities
                if [[ ${critical} -gt 0 ]]; then
                    echo "  Top Critical CVEs:" >> "${SUMMARY_FILE}"
                    jq -r '.Results[]?.Vulnerabilities[]? | select(.Severity == "CRITICAL") | "    - \(.VulnerabilityID): \(.Title // .Description // "No description")"' "${temp_file}" 2>/dev/null | head -5 >> "${SUMMARY_FILE}" || true
                fi
            fi

            # Merge into results JSON
            jq --slurpfile new_result "${temp_file}" \
               --arg image "${img_name}" \
               '.images += [{image: $image, scan_result: $new_result[0]}]' \
               "${RESULTS_FILE}" > "${RESULTS_FILE}.tmp" && mv "${RESULTS_FILE}.tmp" "${RESULTS_FILE}"
        else
            ((failed_scans++))
            log_warn "Scan failed for ${image}"
        fi
    done < "${IMAGE_LIST}"

    # Write summary statistics
    cat >> "${SUMMARY_FILE}" <<EOF

==========================================
Summary Statistics
==========================================
Total Images: ${total_images}
Successfully Scanned: ${scanned_images}
Failed Scans: ${failed_scans}
Total CRITICAL Vulnerabilities: ${total_critical}
Total HIGH Vulnerabilities: ${total_high}
Images with CRITICAL: ${images_with_critical}

EOF

    # Add policy decision
    if [[ ${images_with_critical} -gt 0 ]]; then
        cat >> "${SUMMARY_FILE}" <<EOF
==========================================
POLICY VIOLATION
==========================================
Build FAILED: ${images_with_critical} image(s) contain CRITICAL vulnerabilities.

Remediation Steps:
1. Review vulnerability details in ${RESULTS_FILE}
2. Update affected images to patched versions
3. Update config/versions.env with new image tags
4. Re-run asset collection and rebuild package
5. If vulnerabilities cannot be fixed, document risk acceptance

EOF
        log_error "CRITICAL vulnerabilities found in ${images_with_critical} image(s)"
        return 1
    else
        cat >> "${SUMMARY_FILE}" <<EOF
==========================================
POLICY COMPLIANCE
==========================================
Build PASSED: No CRITICAL vulnerabilities found.

EOF
        if [[ ${total_high} -gt 0 ]]; then
            log_warn "Found ${total_high} HIGH severity vulnerabilities (non-blocking)"
        fi
        log_info "All images passed vulnerability scan"
        return 0
    fi
}

# Cleanup
cleanup() {
    log_info "Cleaning up temporary files..."
    rm -rf "${TEMP_DIR}"
}

# Main execution
main() {
    log_info "Starting container image vulnerability scan..."

    check_prerequisites
    init_output

    if aggregate_results; then
        log_info "Scan completed successfully"
        log_info "Results: ${RESULTS_FILE}"
        log_info "Summary: ${SUMMARY_FILE}"
        cleanup
        exit 0
    else
        log_error "Scan failed due to CRITICAL vulnerabilities"
        log_error "Results: ${RESULTS_FILE}"
        log_error "Summary: ${SUMMARY_FILE}"
        cleanup
        exit 1
    fi
}

# Run main
main "$@"
