#!/bin/bash
set -euo pipefail

# Run offline-repo.yml playbook to configure nodes to use bastion repositories
#
# This script:
# 1. Activates the Kubespray Python venv
# 2. Runs the offline-repo.yml playbook against all cluster nodes
# 3. Verifies the configuration was applied correctly

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_PATH="${INSTALL_PATH:-/opt/opencenter}"
INVENTORY_PATH="${INVENTORY_PATH:-${INSTALL_PATH}/kubespray/inventory/mycluster}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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

# Check if inventory exists
if [ ! -f "${INVENTORY_PATH}/hosts.yaml" ]; then
    log_error "Inventory file not found: ${INVENTORY_PATH}/hosts.yaml"
    log_error "Please generate inventory first using generate_inventory_baremetal.py"
    exit 1
fi

# Check if offline.yml exists
if [ ! -f "${INVENTORY_PATH}/group_vars/all/offline.yml" ]; then
    log_error "offline.yml not found: ${INVENTORY_PATH}/group_vars/all/offline.yml"
    log_error "Please generate offline.yml first"
    exit 1
fi

# Check if playbook exists
PLAYBOOK_PATH="${INSTALL_PATH}/outputs/playbook/offline-repo.yml"
if [ ! -f "${PLAYBOOK_PATH}" ]; then
    log_error "Playbook not found: ${PLAYBOOK_PATH}"
    log_error "Expected location: ${INSTALL_PATH}/outputs/playbook/offline-repo.yml"
    exit 1
fi

log_info "Running offline-repo.yml playbook..."
log_info "  Inventory: ${INVENTORY_PATH}/hosts.yaml"
log_info "  Playbook: ${PLAYBOOK_PATH}"

# Activate Python venv if it exists
VENV_PATH="${HOME}/.venv/kubespray"
if [ -d "${VENV_PATH}" ]; then
    log_info "Activating Python venv: ${VENV_PATH}"
    # shellcheck disable=SC1091
    source "${VENV_PATH}/bin/activate"
else
    log_warn "Python venv not found at ${VENV_PATH}"
    log_warn "Attempting to use system Python/Ansible"
fi

# Check if ansible-playbook is available
if ! command -v ansible-playbook &> /dev/null; then
    log_error "ansible-playbook not found in PATH"
    log_error "Please install Ansible or activate the correct Python venv"
    exit 1
fi

# Run the playbook
log_info "Executing playbook..."
if ansible-playbook \
    -i "${INVENTORY_PATH}/hosts.yaml" \
    "${PLAYBOOK_PATH}" \
    --become \
    -v; then
    log_info "Playbook execution completed successfully"
else
    log_error "Playbook execution failed"
    exit 1
fi

# Verify configuration on nodes
log_info "Verifying offline repository configuration..."

# Check if /etc/apt/sources.list.d/offline.list exists on all nodes
log_info "Checking for offline.list on all nodes..."
if ansible \
    -i "${INVENTORY_PATH}/hosts.yaml" \
    all \
    -m shell \
    -a "test -f /etc/apt/sources.list.d/offline.list && echo 'OK' || echo 'MISSING'" \
    --become \
    | grep -q "MISSING"; then
    log_warn "Some nodes are missing /etc/apt/sources.list.d/offline.list"
    log_warn "This may indicate the playbook did not complete successfully on all nodes"
else
    log_info "✓ offline.list found on all nodes"
fi

# Check if /etc/apt/apt.conf.d/99offline exists on all nodes
log_info "Checking for 99offline apt config on all nodes..."
if ansible \
    -i "${INVENTORY_PATH}/hosts.yaml" \
    all \
    -m shell \
    -a "test -f /etc/apt/apt.conf.d/99offline && echo 'OK' || echo 'MISSING'" \
    --become \
    | grep -q "MISSING"; then
    log_warn "Some nodes are missing /etc/apt/apt.conf.d/99offline"
else
    log_info "✓ 99offline apt config found on all nodes"
fi

log_info "Offline repository configuration complete!"
log_info "Nodes are now configured to use bastion for apt packages"

exit 0
