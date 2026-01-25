#!/bin/bash
#
# Wrapper script for package verification.
#
# This script provides a convenient interface for verifying Zarf packages
# before deployment. It calls the Python verification script with appropriate
# parameters.
#
# Requirements: 3.1, 3.2, 3.3, 3.4, 3.5
#
# Usage:
#   verify_package.sh <package-file> [options]
#

set -euo pipefail

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

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

# Check Python availability
check_python() {
    if ! command -v python3 &> /dev/null; then
        print_error "python3 is not installed"
        return 1
    fi
    return 0
}

# Main function
main() {
    if [[ $# -lt 1 ]]; then
        cat >&2 <<EOF
Usage: $(basename "$0") <package-file> [options]

Verify Zarf package integrity before deployment.

Arguments:
  package-file    Path to Zarf package (.tar.zst)

Options:
  -m, --manifest PATH       Path to checksum manifest (auto-detected if not provided)
  -k, --public-key PATH     Path to Cosign public key (auto-detected if not provided)
  --skip-signature          Skip signature verification
  --no-halt                 Don't halt on verification failure (for testing)

Examples:
  # Verify with auto-detected manifest
  $(basename "$0") zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst

  # Verify with explicit manifest
  $(basename "$0") -m checksums.json zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst

  # Verify with signature
  $(basename "$0") -k cosign.pub zarf-package-opencenter-airgap-amd64-1.0.0.tar.zst

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5
EOF
        return 1
    fi
    
    # Check prerequisites
    if ! check_python; then
        return 1
    fi
    
    # Call Python verification script
    python3 "${SCRIPT_DIR}/verify_package.py" "$@"
    return $?
}

# Run main if executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
