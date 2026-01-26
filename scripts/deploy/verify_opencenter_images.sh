#!/bin/bash
set -euo pipefail

# Verify openCenter platform service images are available in bastion registry
# This script queries the bastion registry and checks for all required openCenter images

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
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

log_section() {
    echo ""
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN}$*${NC}"
    echo -e "${CYAN}========================================${NC}"
    echo ""
}

# Configuration
BASTION_IP="${BASTION_IP:-localhost}"
REGISTRY_PORT="${REGISTRY_PORT:-35000}"
REGISTRY_URL="http://${BASTION_IP}:${REGISTRY_PORT}"
OPENCENTER_IMAGES="${PROJECT_ROOT}/config/opencenter-images.txt"
REPORT_FILE="${PROJECT_ROOT}/build/opencenter-images-verification-$(date +%Y%m%d-%H%M%S).txt"

# Counters
TOTAL_IMAGES=0
FOUND_IMAGES=0
MISSING_IMAGES=0
FAILED_CHECKS=0

# Arrays
declare -a MISSING_IMAGE_LIST
declare -a FOUND_IMAGE_LIST

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    if ! command -v curl &> /dev/null; then
        log_error "curl is not installed"
        exit 1
    fi
    
    if ! command -v jq &> /dev/null; then
        log_error "jq is not installed"
        exit 1
    fi
    
    if [ ! -f "${OPENCENTER_IMAGES}" ]; then
        log_error "openCenter images list not found: ${OPENCENTER_IMAGES}"
        exit 1
    fi
    
    log_info "Prerequisites satisfied"
}

check_registry_connectivity() {
    log_info "Checking registry connectivity..."
    log_info "Registry URL: ${REGISTRY_URL}"
    
    if ! curl -sf "${REGISTRY_URL}/v2/" > /dev/null 2>&1; then
        log_error "Cannot connect to registry at ${REGISTRY_URL}"
        log_error "Ensure registry is running: curl ${REGISTRY_URL}/v2/"
        exit 1
    fi
    
    log_info "Registry is accessible"
}

get_registry_catalog() {
    log_info "Fetching registry catalog..."
    
    CATALOG=$(curl -sf "${REGISTRY_URL}/v2/_catalog" 2>/dev/null)
    
    if [ $? -ne 0 ]; then
        log_error "Failed to fetch registry catalog"
        exit 1
    fi
    
    REPO_COUNT=$(echo "${CATALOG}" | jq -r '.repositories | length')
    log_info "Registry contains ${REPO_COUNT} repositories"
    
    # Save catalog for reference
    echo "${CATALOG}" | jq '.' > "${PROJECT_ROOT}/build/registry-catalog.json"
    log_info "Catalog saved to: ${PROJECT_ROOT}/build/registry-catalog.json"
}

strip_registry_prefix() {
    local image="$1"
    
    # Strip common registry prefixes to match bastion registry format
    # kubespray-offline strips these prefixes when pushing to local registry
    echo "${image}" | sed -E 's|^(registry\.k8s\.io|gcr\.io|ghcr\.io|docker\.io|quay\.io|registry\.opensource\.zalan\.do|longhornio)/||'
}

check_image_in_registry() {
    local full_image="$1"
    
    # Parse image into repository and tag
    local image_repo=$(echo "${full_image}" | cut -d':' -f1)
    local image_tag=$(echo "${full_image}" | cut -d':' -f2)
    
    # Strip registry prefix (kubespray-offline does this)
    local stripped_repo=$(strip_registry_prefix "${image_repo}")
    
    # Try to get tags for this repository
    local tags_url="${REGISTRY_URL}/v2/${stripped_repo}/tags/list"
    
    if ! TAGS=$(curl -sf "${tags_url}" 2>/dev/null); then
        # Repository not found
        return 1
    fi
    
    # Check if the specific tag exists
    if echo "${TAGS}" | jq -e ".tags | index(\"${image_tag}\")" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

verify_opencenter_images() {
    log_section "Verifying openCenter Platform Service Images"
    
    mkdir -p "${PROJECT_ROOT}/build"
    
    # Initialize report
    {
        echo "openCenter Platform Service Images Verification Report"
        echo "Generated: $(date)"
        echo "Registry: ${REGISTRY_URL}"
        echo ""
        echo "========================================"
        echo ""
    } > "${REPORT_FILE}"
    
    # Read images from config file (skip comments and empty lines)
    while IFS= read -r line; do
        # Skip comments and empty lines
        if [[ "${line}" =~ ^#.*$ ]] || [[ -z "${line}" ]]; then
            # Check if it's a section header
            if [[ "${line}" =~ ^#\ ===.*$ ]]; then
                SECTION=$(echo "${line}" | sed 's/^# = *//' | sed 's/ =.*//')
                log_info "Checking section: ${SECTION}"
                echo "" >> "${REPORT_FILE}"
                echo "## ${SECTION}" >> "${REPORT_FILE}"
                echo "" >> "${REPORT_FILE}"
            fi
            continue
        fi
        
        TOTAL_IMAGES=$((TOTAL_IMAGES + 1))
        
        # Check if image exists in registry
        if check_image_in_registry "${line}"; then
            FOUND_IMAGES=$((FOUND_IMAGES + 1))
            FOUND_IMAGE_LIST+=("${line}")
            echo "  ✓ ${line}" >> "${REPORT_FILE}"
        else
            MISSING_IMAGES=$((MISSING_IMAGES + 1))
            MISSING_IMAGE_LIST+=("${line}")
            log_warn "Missing: ${line}"
            echo "  ✗ ${line}" >> "${REPORT_FILE}"
        fi
        
    done < "${OPENCENTER_IMAGES}"
}

generate_summary() {
    log_section "Verification Summary"
    
    {
        echo ""
        echo "========================================"
        echo "SUMMARY"
        echo "========================================"
        echo ""
        echo "Total images checked: ${TOTAL_IMAGES}"
        echo "Found in registry:    ${FOUND_IMAGES}"
        echo "Missing from registry: ${MISSING_IMAGES}"
        echo ""
    } >> "${REPORT_FILE}"
    
    log_info "Total images checked: ${TOTAL_IMAGES}"
    log_info "Found in registry:    ${FOUND_IMAGES}"
    
    if [ ${MISSING_IMAGES} -gt 0 ]; then
        log_warn "Missing from registry: ${MISSING_IMAGES}"
        
        echo "Missing images:" >> "${REPORT_FILE}"
        for img in "${MISSING_IMAGE_LIST[@]}"; do
            echo "  - ${img}" >> "${REPORT_FILE}"
        done
        echo "" >> "${REPORT_FILE}"
    else
        log_info "All openCenter platform service images are available!"
    fi
    
    # Calculate percentage
    if [ ${TOTAL_IMAGES} -gt 0 ]; then
        PERCENTAGE=$((FOUND_IMAGES * 100 / TOTAL_IMAGES))
        log_info "Coverage: ${PERCENTAGE}%"
        echo "Coverage: ${PERCENTAGE}%" >> "${REPORT_FILE}"
    fi
    
    log_info "Verification report saved to: ${REPORT_FILE}"
    
    # Exit with error if any images are missing
    if [ ${MISSING_IMAGES} -gt 0 ]; then
        log_error "Verification failed: ${MISSING_IMAGES} images missing"
        log_error "Check report for details: ${REPORT_FILE}"
        return 1
    else
        log_info "Verification passed: All images available"
        return 0
    fi
}

print_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Verify openCenter platform service images are available in bastion registry.

Options:
  --bastion-ip IP       Bastion IP address (default: localhost)
  --registry-port PORT  Registry port (default: 35000)
  --help                Show this help message

Environment variables:
  BASTION_IP            Bastion IP address
  REGISTRY_PORT         Registry port

Examples:
  # Verify on localhost
  $0

  # Verify on remote bastion
  $0 --bastion-ip 192.168.1.100

  # Use environment variables
  BASTION_IP=192.168.1.100 $0

EOF
}

# Main execution
main() {
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --bastion-ip)
                BASTION_IP="$2"
                shift 2
                ;;
            --registry-port)
                REGISTRY_PORT="$2"
                shift 2
                ;;
            --help)
                print_usage
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                print_usage
                exit 1
                ;;
        esac
    done
    
    # Update registry URL with parsed values
    REGISTRY_URL="http://${BASTION_IP}:${REGISTRY_PORT}"
    
    log_section "openCenter Platform Service Images Verification"
    
    check_prerequisites
    check_registry_connectivity
    get_registry_catalog
    verify_opencenter_images
    generate_summary
}

main "$@"
