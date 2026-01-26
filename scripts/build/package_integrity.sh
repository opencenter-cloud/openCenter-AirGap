#!/bin/bash
#
# Complete package integrity workflow.
#
# This script orchestrates the complete package integrity workflow:
# 1. Generate checksum manifest
# 2. Sign package (optional)
# 3. Verify package integrity
#
# Requirements: 2.6, 2.7, 3.1, 3.2, 3.3, 3.4, 3.5
#
# Usage:
#   package_integrity.sh <command> <package-file> [options]
#

set -euo pipefail

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print functions
print_info() {
    echo -e "${GREEN}[INFO]${NC} $*" >&2
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*" >&2
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $*" >&2
}

print_step() {
    echo -e "${BLUE}[STEP]${NC} $*" >&2
}

# Generate checksums for package
generate_checksums() {
    local package_file="$1"
    local format="${2:-json}"
    
    print_step "Generating checksum manifest..."
    
    if python3 "${SCRIPT_DIR}/generate_checksum_manifest.py" \
        --format "${format}" \
        --print \
        "${package_file}"; then
        print_info "Checksum manifest generated successfully"
        return 0
    else
        print_error "Failed to generate checksum manifest"
        return 1
    fi
}

# Sign package
sign_package() {
    local package_file="$1"
    local key_file="${2:-}"
    
    print_step "Signing package..."
    
    if bash "${SCRIPT_DIR}/sign_package.sh" "${package_file}" ${key_file:+"${key_file}"}; then
        print_info "Package signed successfully"
        return 0
    else
        print_warn "Package signing failed or skipped"
        return 0  # Don't fail if signing is optional
    fi
}

# Verify package
verify_package() {
    local package_file="$1"
    shift
    
    print_step "Verifying package integrity..."
    
    if python3 "${SCRIPT_DIR}/../deploy/verify_package.py" "${package_file}" "$@"; then
        print_info "Package verification PASSED"
        return 0
    else
        print_error "Package verification FAILED"
        return 1
    fi
}

# Complete workflow: generate + sign + verify
complete_workflow() {
    local package_file="$1"
    local key_file="${2:-}"
    
    print_info "Starting complete package integrity workflow"
    print_info "Package: ${package_file}"
    echo ""
    
    # Step 1: Generate checksums
    if ! generate_checksums "${package_file}" "json"; then
        return 1
    fi
    echo ""
    
    # Step 2: Sign package (optional)
    if [[ -n "${key_file}" ]] || [[ -f "cosign.key" ]]; then
        sign_package "${package_file}" "${key_file}"
        echo ""
    else
        print_warn "Skipping package signing (no key provided)"
        echo ""
    fi
    
    # Step 3: Verify package
    if ! verify_package "${package_file}"; then
        return 1
    fi
    
    print_info "Package integrity workflow completed successfully"
    return 0
}

# Show usage
usage() {
    cat >&2 <<EOF
Usage: $(basename "$0") <command> <package-file> [options]

Complete package integrity workflow for Zarf packages.

Commands:
  generate    Generate checksum manifest only
  sign        Sign package only (requires Cosign)
  verify      Verify package integrity only
  all         Complete workflow: generate + sign + verify

Arguments:
  package-file    Path to Zarf package (.tar.zst)

Options:
  -k, --key PATH  Path to Cosign private key (for signing)
  -f, --format    Manifest format: json or text (default: json)

Examples:
  # Complete workflow
  $(basename "$0") all zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst

  # Generate checksums only
  $(basename "$0") generate zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst

  # Sign with specific key
  $(basename "$0") sign zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst -k /path/to/key

  # Verify package
  $(basename "$0") verify zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst

Requirements: 2.6, 2.7, 3.1, 3.2, 3.3, 3.4, 3.5
EOF
}

# Main function
main() {
    if [[ $# -lt 2 ]]; then
        usage
        return 1
    fi
    
    local command="$1"
    local package_file="$2"
    shift 2
    
    # Parse options
    local key_file=""
    local format="json"
    
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -k|--key)
                key_file="$2"
                shift 2
                ;;
            -f|--format)
                format="$2"
                shift 2
                ;;
            *)
                print_error "Unknown option: $1"
                usage
                return 1
                ;;
        esac
    done
    
    # Validate package file
    if [[ ! -f "${package_file}" ]]; then
        print_error "Package file not found: ${package_file}"
        return 1
    fi
    
    # Execute command
    case "${command}" in
        generate)
            generate_checksums "${package_file}" "${format}"
            ;;
        sign)
            sign_package "${package_file}" "${key_file}"
            ;;
        verify)
            verify_package "${package_file}"
            ;;
        all)
            complete_workflow "${package_file}" "${key_file}"
            ;;
        *)
            print_error "Unknown command: ${command}"
            usage
            return 1
            ;;
    esac
}

# Run main if executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
