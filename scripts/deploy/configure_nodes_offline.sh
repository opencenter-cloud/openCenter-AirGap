#!/bin/bash
set -euo pipefail

# Configure cluster nodes to use bastion offline repositories
#
# This script is designed to be called as a Zarf action and will:
# 1. Verify prerequisites (inventory, offline.yml, playbook)
# 2. Run the offline-repo.yml playbook
# 3. Verify the configuration was applied

INSTALL_PATH="${INSTALL_PATH:-/opt/opencenter}"
INVENTORY_PATH="${INVENTORY_PATH:-${INSTALL_PATH}/kubespray/inventory/mycluster}"
BASTION_IP="${BASTION_IP:-}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $*"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --inventory-path)
            INVENTORY_PATH="$2"
            shift 2
            ;;
        --bastion-ip)
            BASTION_IP="$2"
            shift 2
            ;;
        --install-path)
            INSTALL_PATH="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --inventory-path PATH    Path to Kubespray inventory directory (default: ${INSTALL_PATH}/kubespray/inventory/mycluster)"
            echo "  --bastion-ip IP          IP address of bastion host (required)"
            echo "  --install-path PATH      Installation directory (default: /opt/opencenter)"
            echo "  --help                   Show this help message"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Validate bastion IP
if [ -z "${BASTION_IP}" ]; then
    log_error "Bastion IP is required. Use --bastion-ip or set BASTION_IP environment variable"
    exit 1
fi

log_step "Configuring cluster nodes to use bastion offline repositories"
log_info "Bastion IP: ${BASTION_IP}"
log_info "Inventory: ${INVENTORY_PATH}"
log_info "Install path: ${INSTALL_PATH}"

# Check prerequisites
log_step "Checking prerequisites..."

if [ ! -f "${INVENTORY_PATH}/hosts.yaml" ]; then
    log_error "Inventory file not found: ${INVENTORY_PATH}/hosts.yaml"
    log_error "Please generate inventory first"
    exit 1
fi
log_info "✓ Inventory file found"

if [ ! -f "${INVENTORY_PATH}/group_vars/all/offline.yml" ]; then
    log_error "offline.yml not found: ${INVENTORY_PATH}/group_vars/all/offline.yml"
    log_error "Please generate offline.yml first"
    exit 1
fi
log_info "✓ offline.yml found"

PLAYBOOK_PATH="${INSTALL_PATH}/outputs/playbook/offline-repo.yml"
if [ ! -f "${PLAYBOOK_PATH}" ]; then
    log_error "Playbook not found: ${PLAYBOOK_PATH}"
    exit 1
fi
log_info "✓ Playbook found"

# Activate Python venv
log_step "Activating Python environment..."
VENV_PATH="${HOME}/.venv/kubespray"
if [ -d "${VENV_PATH}" ]; then
    log_info "Using Python venv: ${VENV_PATH}"
    # shellcheck disable=SC1091
    source "${VENV_PATH}/bin/activate"
else
    log_warn "Python venv not found at ${VENV_PATH}, using system Python"
fi

# Verify Ansible is available
if ! command -v ansible-playbook &> /dev/null; then
    log_error "ansible-playbook not found"
    log_error "Please install Ansible or activate the correct Python venv"
    exit 1
fi
log_info "✓ Ansible found: $(ansible-playbook --version | head -n1)"

# Test connectivity to nodes
log_step "Testing connectivity to cluster nodes..."
if ansible \
    -i "${INVENTORY_PATH}/hosts.yaml" \
    all \
    -m ping \
    --one-line \
    2>&1 | grep -q "SUCCESS"; then
    log_info "✓ All nodes are reachable"
else
    log_error "Some nodes are not reachable"
    log_error "Please verify SSH connectivity and credentials"
    exit 1
fi

# Run the offline-repo playbook
log_step "Running offline-repo.yml playbook..."
log_info "This will configure nodes to use bastion for apt packages"

if ansible-playbook \
    -i "${INVENTORY_PATH}/hosts.yaml" \
    "${PLAYBOOK_PATH}" \
    --become \
    -v; then
    log_info "✓ Playbook execution completed"
else
    log_error "Playbook execution failed"
    exit 1
fi

# Verify configuration
log_step "Verifying offline repository configuration..."

# Check offline.list
log_info "Checking /etc/apt/sources.list.d/offline.list..."
MISSING_OFFLINE_LIST=$(ansible \
    -i "${INVENTORY_PATH}/hosts.yaml" \
    all \
    -m shell \
    -a "test -f /etc/apt/sources.list.d/offline.list && echo 'OK' || echo 'MISSING'" \
    --become \
    --one-line \
    2>&1 | grep -c "MISSING" || true)

if [ "${MISSING_OFFLINE_LIST}" -gt 0 ]; then
    log_warn "${MISSING_OFFLINE_LIST} node(s) missing offline.list"
else
    log_info "✓ offline.list configured on all nodes"
fi

# Check 99offline apt config
log_info "Checking /etc/apt/apt.conf.d/99offline..."
MISSING_APT_CONFIG=$(ansible \
    -i "${INVENTORY_PATH}/hosts.yaml" \
    all \
    -m shell \
    -a "test -f /etc/apt/apt.conf.d/99offline && echo 'OK' || echo 'MISSING'" \
    --become \
    --one-line \
    2>&1 | grep -c "MISSING" || true)

if [ "${MISSING_APT_CONFIG}" -gt 0 ]; then
    log_warn "${MISSING_APT_CONFIG} node(s) missing 99offline apt config"
else
    log_info "✓ 99offline apt config on all nodes"
fi

# Verify apt can reach bastion repository
log_info "Testing apt repository connectivity..."
TEST_RESULT=$(ansible \
    -i "${INVENTORY_PATH}/hosts.yaml" \
    all \
    -m shell \
    -a "apt-get update 2>&1 | grep -q 'Reading package lists' && echo 'OK' || echo 'FAILED'" \
    --become \
    --one-line \
    2>&1 | grep -c "FAILED" || true)

if [ "${TEST_RESULT}" -gt 0 ]; then
    log_warn "${TEST_RESULT} node(s) failed to update apt cache"
    log_warn "This may indicate connectivity issues to bastion repository"
else
    log_info "✓ All nodes can reach bastion apt repository"
fi

log_step "Configuration complete!"
log_info "Cluster nodes are now configured to use bastion offline repositories"
log_info "Next step: Deploy Kubernetes cluster using Kubespray"
log_info "  cd ${INSTALL_PATH}/kubespray"
log_info "  ansible-playbook -i ${INVENTORY_PATH}/hosts.yaml --become cluster.yml"

exit 0
