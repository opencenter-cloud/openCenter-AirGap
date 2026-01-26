#!/bin/bash
#
# Sign Zarf package with Cosign.
#
# This script signs a Zarf package using Cosign for cryptographic verification.
# Signing is optional and requires a Cosign key pair.
#
# Requirements: 2.7
#
# Usage:
#   sign_package.sh <package-file> [key-file]
#
# Environment Variables:
#   COSIGN_KEY: Path to Cosign private key (default: cosign.key)
#   COSIGN_PASSWORD: Password for private key (prompted if not set)
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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

# Check if cosign is installed
check_cosign() {
    if ! command -v cosign &> /dev/null; then
        print_error "cosign is not installed"
        print_info "Install cosign from: https://docs.sigstore.dev/cosign/installation/"
        return 1
    fi
    
    local version
    version=$(cosign version 2>&1 | head -n1 || echo "unknown")
    print_info "Using cosign: ${version}"
    return 0
}

# Sign package with cosign
sign_package() {
    local package_file="$1"
    local key_file="${2:-${COSIGN_KEY:-cosign.key}}"
    
    # Validate inputs
    if [[ ! -f "${package_file}" ]]; then
        print_error "Package file not found: ${package_file}"
        return 1
    fi
    
    if [[ ! -f "${key_file}" ]]; then
        print_error "Key file not found: ${key_file}"
        print_info "Generate a key pair with: cosign generate-key-pair"
        return 1
    fi
    
    # Determine signature output path
    local sig_file="${package_file}.sig"
    
    print_info "Signing package: $(basename "${package_file}")"
    print_info "Using key: ${key_file}"
    
    # Sign with cosign
    # cosign sign-blob creates a detached signature
    if cosign sign-blob \
        --key "${key_file}" \
        --output-signature "${sig_file}" \
        "${package_file}"; then
        
        print_info "Signature written to: ${sig_file}"
        
        # Also create a certificate if available
        local cert_file="${package_file}.cert"
        if cosign sign-blob \
            --key "${key_file}" \
            --output-certificate "${cert_file}" \
            "${package_file}" 2>/dev/null; then
            print_info "Certificate written to: ${cert_file}"
        fi
        
        return 0
    else
        print_error "Failed to sign package"
        return 1
    fi
}

# Verify signature (for testing)
verify_signature() {
    local package_file="$1"
    local key_file="${2:-${COSIGN_KEY:-cosign.key}}"
    local sig_file="${package_file}.sig"
    
    # Convert private key to public key path
    local pub_key_file="${key_file%.key}.pub"
    
    if [[ ! -f "${pub_key_file}" ]]; then
        print_error "Public key not found: ${pub_key_file}"
        return 1
    fi
    
    if [[ ! -f "${sig_file}" ]]; then
        print_error "Signature file not found: ${sig_file}"
        return 1
    fi
    
    print_info "Verifying signature..."
    
    if cosign verify-blob \
        --key "${pub_key_file}" \
        --signature "${sig_file}" \
        "${package_file}"; then
        
        print_info "Signature verification: PASSED"
        return 0
    else
        print_error "Signature verification: FAILED"
        return 1
    fi
}

# Main function
main() {
    if [[ $# -lt 1 ]]; then
        cat >&2 <<EOF
Usage: $(basename "$0") <package-file> [key-file]

Sign a Zarf package with Cosign for cryptographic verification.

Arguments:
  package-file    Path to Zarf package (.tar.zst)
  key-file        Path to Cosign private key (default: cosign.key or \$COSIGN_KEY)

Environment Variables:
  COSIGN_KEY      Path to Cosign private key
  COSIGN_PASSWORD Password for private key (prompted if not set)

Examples:
  # Sign with default key (cosign.key)
  $(basename "$0") zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst

  # Sign with specific key
  $(basename "$0") zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst /path/to/key.key

  # Generate key pair first
  cosign generate-key-pair

Requirements: 2.7
EOF
        return 1
    fi
    
    local package_file="$1"
    local key_file="${2:-}"
    
    # Check prerequisites
    if ! check_cosign; then
        return 1
    fi
    
    # Sign package
    if sign_package "${package_file}" "${key_file}"; then
        print_info "Package signing complete"
        
        # Optionally verify
        if [[ "${VERIFY_AFTER_SIGN:-false}" == "true" ]]; then
            print_info ""
            verify_signature "${package_file}" "${key_file}"
        fi
        
        return 0
    else
        return 1
    fi
}

# Run main if executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
