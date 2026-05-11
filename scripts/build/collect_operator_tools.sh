#!/bin/bash
set -euo pipefail

# Collect operator tools for air-gap deployment
#
# Downloads CLI tools that improve operator experience:
# - k9s: Terminal UI for Kubernetes
# - helm: Chart deployment
# - stern: Multi-pod log tailing
# - kubectx/kubens: Context switching
#
# All downloads are recorded in build/provenance/downloads.ndjson
# via the shared download library.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
TOOLS_DIR="${PROJECT_ROOT}/assets/operator-tools"

# Source shared download library (provenance tracking)
# shellcheck disable=SC1091
source "${PROJECT_ROOT}/scripts/lib/download.sh"

# Source versions
if [ -f "${PROJECT_ROOT}/config/versions.env" ]; then
    # shellcheck disable=SC1091
    source "${PROJECT_ROOT}/config/versions.env"
fi

# Tool versions (with defaults)
K9S_VERSION="${K9S_VERSION:-v0.32.5}"
HELM_VERSION="${HELM_VERSION:-v3.14.0}"
STERN_VERSION="${STERN_VERSION:-v1.28.0}"
KUBECTX_VERSION="${KUBECTX_VERSION:-v0.9.5}"

ARCH="amd64"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_step() {
    echo -e "${CYAN}[STEP]${NC} $*"
}

# Create tools directory and initialize provenance
mkdir -p "${TOOLS_DIR}"
export PROVENANCE_DIR="${PROJECT_ROOT}/build/provenance"
export PROVENANCE_FILE="${PROVENANCE_DIR}/downloads.ndjson"
init_provenance

download_k9s() {
    log_step "Downloading k9s ${K9S_VERSION}..."
    local url="https://github.com/derailed/k9s/releases/download/${K9S_VERSION}/k9s_Linux_${ARCH}.tar.gz"

    if download_and_extract "${url}" "${TOOLS_DIR}" "k9s" "k9s"; then
        chmod +x "${TOOLS_DIR}/k9s"
        log_info "✓ k9s downloaded"
    else
        log_warn "Failed to download k9s"
        return 1
    fi
}

download_helm() {
    log_step "Downloading helm ${HELM_VERSION}..."
    local url="https://get.helm.sh/helm-${HELM_VERSION}-linux-${ARCH}.tar.gz"

    if download_and_extract "${url}" "${TOOLS_DIR}" "--strip-components=1 linux-${ARCH}/helm" "helm"; then
        chmod +x "${TOOLS_DIR}/helm"
        log_info "✓ helm downloaded"
    else
        log_warn "Failed to download helm"
        return 1
    fi
}

download_stern() {
    log_step "Downloading stern ${STERN_VERSION}..."
    local version_num="${STERN_VERSION#v}"
    local url="https://github.com/stern/stern/releases/download/${STERN_VERSION}/stern_${version_num}_linux_${ARCH}.tar.gz"

    if download_and_extract "${url}" "${TOOLS_DIR}" "stern" "stern"; then
        chmod +x "${TOOLS_DIR}/stern"
        log_info "✓ stern downloaded"
    else
        log_warn "Failed to download stern"
        return 1
    fi
}

download_kubectx() {
    log_step "Downloading kubectx/kubens ${KUBECTX_VERSION}..."
    local base_url="https://github.com/ahmetb/kubectx/releases/download/${KUBECTX_VERSION}"

    if download_artifact "${base_url}/kubectx" "${TOOLS_DIR}/kubectx" "" "kubectx" && \
       download_artifact "${base_url}/kubens" "${TOOLS_DIR}/kubens" "" "kubens"; then
        chmod +x "${TOOLS_DIR}/kubectx" "${TOOLS_DIR}/kubens"
        log_info "✓ kubectx/kubens downloaded"
    else
        log_warn "Failed to download kubectx/kubens"
        return 1
    fi
}

# Main execution
main() {
    log_info "Collecting operator tools..."
    log_info "Target directory: ${TOOLS_DIR}"
    log_info "Provenance log: ${PROVENANCE_FILE}"
    echo ""

    # Download all tools
    download_k9s
    download_helm
    download_stern
    download_kubectx

    echo ""
    log_info "Operator tools collected:"
    ls -lh "${TOOLS_DIR}"

    echo ""
    log_info "Verifying tools..."

    # Verify executables
    for tool in k9s helm stern kubectx kubens; do
        if [ -x "${TOOLS_DIR}/${tool}" ]; then
            local size
            size=$(du -h "${TOOLS_DIR}/${tool}" | cut -f1)
            log_info "  ✓ ${tool} (${size})"
        else
            log_warn "  ✗ ${tool} missing or not executable"
        fi
    done

    echo ""
    log_info "Collection complete"
    log_info "Provenance records written to: ${PROVENANCE_FILE}"
}

main "$@"
