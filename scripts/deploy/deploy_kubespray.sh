#!/bin/bash
set -euo pipefail

# Deploy Kubernetes cluster using Kubespray with kubespray-offline workflow
#
# This script follows the kubespray-offline deployment pattern:
# 1. Extract kubespray-*.tar.gz to kubespray-master/
# 2. Activate Python venv (~/.venv/kubespray)
# 3. Install Ansible dependencies
# 4. Copy inventory from sample
# 5. Generate hosts.yaml (bare-metal or OpenStack)
# 6. Copy offline.yml with bastion IP substituted
# 7. Run offline-repo.yml playbook to configure nodes
# 8. Execute cluster.yml to deploy Kubernetes
# 9. Export kubeconfig to ~/.kube/config

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source logging module
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/logging.sh"

# Default configuration
INSTALL_PATH="${INSTALL_PATH:-/opt/opencenter}"
BASTION_IP="${BASTION_IP:-}"
CLUSTER_NAME="${CLUSTER_NAME:-mycluster}"
DEPLOYMENT_MODE="${DEPLOYMENT_MODE:-baremetal}"
NODES_FILE="${NODES_FILE:-}"
INVENTORY_PATH="${INVENTORY_PATH:-}"
SKIP_EXTRACTION="${SKIP_EXTRACTION:-false}"
SKIP_VENV_SETUP="${SKIP_VENV_SETUP:-false}"
SKIP_INVENTORY="${SKIP_INVENTORY:-false}"
SKIP_OFFLINE_REPO="${SKIP_OFFLINE_REPO:-false}"
SKIP_CLUSTER_DEPLOY="${SKIP_CLUSTER_DEPLOY:-false}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Usage information
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Deploy Kubernetes cluster using Kubespray with kubespray-offline workflow.

Required Options:
  --bastion-ip IP              IP address of bastion host
  --mode MODE                  Deployment mode: baremetal or openstack

Bare-metal Mode Options:
  --nodes FILE                 Path to node list file (JSON or YAML)

OpenStack Mode Options:
  --inventory-path PATH        Path to generated inventory directory

Common Options:
  --cluster-name NAME          Cluster name (default: mycluster)
  --install-path PATH          Installation directory (default: /opt/opencenter)
  --skip-extraction            Skip Kubespray extraction
  --skip-venv-setup            Skip Python venv setup
  --skip-inventory             Skip inventory generation
  --skip-offline-repo          Skip offline-repo.yml playbook
  --skip-cluster-deploy        Skip cluster.yml deployment
  --help                       Show this help message

Environment Variables:
  INSTALL_PATH                 Same as --install-path
  BASTION_IP                   Same as --bastion-ip
  CLUSTER_NAME                 Same as --cluster-name
  DEPLOYMENT_MODE              Same as --mode

Examples:
  # Bare-metal deployment
  $0 --mode baremetal --bastion-ip 192.168.1.5 --nodes nodes.yaml

  # OpenStack deployment (inventory already generated)
  $0 --mode openstack --bastion-ip 10.0.0.5 --inventory-path /opt/opencenter/kubespray/inventory/mycluster

  # Skip extraction and venv setup (for re-runs)
  $0 --mode baremetal --bastion-ip 192.168.1.5 --nodes nodes.yaml --skip-extraction --skip-venv-setup

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --mode)
            DEPLOYMENT_MODE="$2"
            shift 2
            ;;
        --bastion-ip)
            BASTION_IP="$2"
            shift 2
            ;;
        --nodes)
            NODES_FILE="$2"
            shift 2
            ;;
        --inventory-path)
            INVENTORY_PATH="$2"
            shift 2
            ;;
        --cluster-name)
            CLUSTER_NAME="$2"
            shift 2
            ;;
        --install-path)
            INSTALL_PATH="$2"
            shift 2
            ;;
        --skip-extraction)
            SKIP_EXTRACTION="true"
            shift
            ;;
        --skip-venv-setup)
            SKIP_VENV_SETUP="true"
            shift
            ;;
        --skip-inventory)
            SKIP_INVENTORY="true"
            shift
            ;;
        --skip-offline-repo)
            SKIP_OFFLINE_REPO="true"
            shift
            ;;
        --skip-cluster-deploy)
            SKIP_CLUSTER_DEPLOY="true"
            shift
            ;;
        --help)
            usage
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            echo ""
            usage
            exit 1
            ;;
    esac
done

# Validate required parameters
if [ -z "${BASTION_IP}" ]; then
    log_error "Bastion IP is required. Use --bastion-ip or set BASTION_IP environment variable"
    exit 1
fi

if [ "${DEPLOYMENT_MODE}" != "baremetal" ] && [ "${DEPLOYMENT_MODE}" != "openstack" ]; then
    log_error "Invalid deployment mode: ${DEPLOYMENT_MODE}"
    log_error "Must be 'baremetal' or 'openstack'"
    exit 1
fi

if [ "${DEPLOYMENT_MODE}" = "baremetal" ] && [ -z "${NODES_FILE}" ] && [ "${SKIP_INVENTORY}" = "false" ]; then
    log_error "Bare-metal mode requires --nodes FILE"
    exit 1
fi

if [ "${DEPLOYMENT_MODE}" = "openstack" ] && [ -z "${INVENTORY_PATH}" ] && [ "${SKIP_INVENTORY}" = "false" ]; then
    log_error "OpenStack mode requires --inventory-path PATH"
    exit 1
fi

# Display configuration
log_info "Kubespray Deployment Configuration"
log_info "  Mode: ${DEPLOYMENT_MODE}"
log_info "  Bastion IP: ${BASTION_IP}"
log_info "  Cluster name: ${CLUSTER_NAME}"
log_info "  Install path: ${INSTALL_PATH}"

# Set paths
OUTPUTS_DIR="${INSTALL_PATH}/outputs"
KUBESPRAY_DIR="${OUTPUTS_DIR}/kubespray-master"
VENV_PATH="${HOME}/.venv/kubespray"
SCRIPTS_DIR="${INSTALL_PATH}/scripts"

# Set inventory path if not provided
if [ -z "${INVENTORY_PATH}" ]; then
    INVENTORY_PATH="${KUBESPRAY_DIR}/inventory/${CLUSTER_NAME}"
fi

# Step 1: Extract Kubespray tarball
if [ "${SKIP_EXTRACTION}" = "false" ]; then
    log_step "Step 1: Extract Kubespray tarball"
    
    if [ ! -d "${OUTPUTS_DIR}" ]; then
        log_error "Outputs directory not found: ${OUTPUTS_DIR}"
        log_error "Please ensure Zarf package has been deployed"
        exit 1
    fi
    
    cd "${OUTPUTS_DIR}"
    
    if [ ! -f "target-scripts/extract-kubespray.sh" ]; then
        log_error "extract-kubespray.sh not found at: ${OUTPUTS_DIR}/target-scripts/extract-kubespray.sh"
        exit 1
    fi
    
    log_info "Executing extract-kubespray.sh..."
    if ./target-scripts/extract-kubespray.sh; then
        log_info "✓ Kubespray extracted successfully"
    else
        log_error "Failed to extract Kubespray"
        exit 1
    fi
    
    # Verify extraction
    if [ ! -d "${KUBESPRAY_DIR}" ]; then
        log_error "Kubespray directory not found after extraction: ${KUBESPRAY_DIR}"
        exit 1
    fi
    log_info "✓ Kubespray directory: ${KUBESPRAY_DIR}"
    
else
    log_step "Step 1: Extract Kubespray (SKIPPED)"
    log_warn "Using existing Kubespray at: ${KUBESPRAY_DIR}"
    
    # Verify Kubespray exists
    if [ ! -d "${KUBESPRAY_DIR}" ]; then
        log_error "Kubespray directory not found: ${KUBESPRAY_DIR}"
        log_error "Cannot skip extraction without existing Kubespray"
        exit 1
    fi
fi

# Step 2: Activate Python venv and install Ansible
if [ "${SKIP_VENV_SETUP}" = "false" ]; then
    log_step "Step 2: Setup Python environment"
    
    # Check if venv exists
    if [ ! -d "${VENV_PATH}" ]; then
        log_error "Python venv not found: ${VENV_PATH}"
        log_error "Please run bastion setup first (setup-all.sh)"
        exit 1
    fi
    
    log_info "Activating Python venv: ${VENV_PATH}"
    # shellcheck disable=SC1091
    source "${VENV_PATH}/bin/activate"
    log_info "✓ Python venv activated"
    
    # Verify Python version
    PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
    log_info "Python version: ${PYTHON_VERSION}"
    
    # Install Ansible dependencies
    log_info "Installing Ansible dependencies..."
    cd "${KUBESPRAY_DIR}"
    
    if [ ! -f "requirements.txt" ]; then
        log_error "requirements.txt not found in Kubespray directory"
        exit 1
    fi
    
    if pip install -q -r requirements.txt; then
        log_info "✓ Ansible dependencies installed"
    else
        log_error "Failed to install Ansible dependencies"
        exit 1
    fi
    
    # Verify ansible-playbook is available
    if ! command -v ansible-playbook &> /dev/null; then
        log_error "ansible-playbook not found after installation"
        exit 1
    fi
    
    ANSIBLE_VERSION=$(ansible-playbook --version | head -1)
    log_info "Ansible version: ${ANSIBLE_VERSION}"
    
else
    log_step "Step 2: Python environment setup (SKIPPED)"
    
    # Still need to activate venv for subsequent steps
    if [ -d "${VENV_PATH}" ]; then
        log_info "Activating existing Python venv: ${VENV_PATH}"
        # shellcheck disable=SC1091
        source "${VENV_PATH}/bin/activate"
    else
        log_warn "Python venv not found: ${VENV_PATH}"
        log_warn "Attempting to use system Python/Ansible"
    fi
    
    # Verify ansible-playbook is available
    if ! command -v ansible-playbook &> /dev/null; then
        log_error "ansible-playbook not found in PATH"
        exit 1
    fi
fi

# Step 3: Copy inventory from sample
log_step "Step 3: Prepare inventory structure"

cd "${KUBESPRAY_DIR}"

if [ ! -d "inventory/sample" ]; then
    log_error "Sample inventory not found: ${KUBESPRAY_DIR}/inventory/sample"
    exit 1
fi

# Create inventory directory if it doesn't exist
if [ ! -d "${INVENTORY_PATH}" ]; then
    log_info "Creating inventory directory: ${INVENTORY_PATH}"
    cp -r inventory/sample "${INVENTORY_PATH}"
    log_info "✓ Inventory structure created from sample"
else
    log_info "Inventory directory already exists: ${INVENTORY_PATH}"
fi

# Step 4: Generate hosts.yaml
if [ "${SKIP_INVENTORY}" = "false" ]; then
    log_step "Step 4: Generate hosts.yaml"
    
    if [ "${DEPLOYMENT_MODE}" = "baremetal" ]; then
        log_info "Generating inventory for bare-metal deployment"
        
        if [ ! -f "${NODES_FILE}" ]; then
            log_error "Nodes file not found: ${NODES_FILE}"
            exit 1
        fi
        
        if [ ! -f "${SCRIPTS_DIR}/generate_inventory_baremetal.py" ]; then
            log_error "generate_inventory_baremetal.py not found"
            exit 1
        fi
        
        log_info "Nodes file: ${NODES_FILE}"
        log_info "Output: ${INVENTORY_PATH}/hosts.yaml"
        
        if python3 "${SCRIPTS_DIR}/generate_inventory_baremetal.py" \
            --nodes "${NODES_FILE}" \
            --bastion-ip "${BASTION_IP}" \
            --cluster-name "${CLUSTER_NAME}" \
            --output-dir "${KUBESPRAY_DIR}/inventory"; then
            log_info "✓ Inventory generated successfully"
        else
            log_error "Failed to generate inventory"
            exit 1
        fi
        
    else
        log_info "Using inventory from OpenStack provisioning"
        
        if [ ! -f "${INVENTORY_PATH}/hosts.yaml" ]; then
            log_error "Inventory file not found: ${INVENTORY_PATH}/hosts.yaml"
            log_error "Please run Terraform provisioning first"
            exit 1
        fi
        
        log_info "✓ Using existing inventory: ${INVENTORY_PATH}/hosts.yaml"
    fi
    
    # Verify inventory was created
    if [ ! -f "${INVENTORY_PATH}/hosts.yaml" ]; then
        log_error "Inventory file not created: ${INVENTORY_PATH}/hosts.yaml"
        exit 1
    fi
    
    # Verify offline.yml was created
    if [ ! -f "${INVENTORY_PATH}/group_vars/all/offline.yml" ]; then
        log_error "offline.yml not created: ${INVENTORY_PATH}/group_vars/all/offline.yml"
        exit 1
    fi
    
    log_info "✓ Inventory files:"
    log_info "    hosts.yaml: ${INVENTORY_PATH}/hosts.yaml"
    log_info "    offline.yml: ${INVENTORY_PATH}/group_vars/all/offline.yml"
    
else
    log_step "Step 4: Generate hosts.yaml (SKIPPED)"
    log_warn "Using existing inventory"
    
    # Verify inventory exists
    if [ ! -f "${INVENTORY_PATH}/hosts.yaml" ]; then
        log_error "Inventory file not found: ${INVENTORY_PATH}/hosts.yaml"
        exit 1
    fi
    
    if [ ! -f "${INVENTORY_PATH}/group_vars/all/offline.yml" ]; then
        log_error "offline.yml not found: ${INVENTORY_PATH}/group_vars/all/offline.yml"
        exit 1
    fi
fi

# Step 5: Run offline-repo.yml playbook
if [ "${SKIP_OFFLINE_REPO}" = "false" ]; then
    log_step "Step 5: Configure nodes for offline operation"
    
    PLAYBOOK_PATH="${OUTPUTS_DIR}/playbook/offline-repo.yml"
    
    if [ ! -f "${PLAYBOOK_PATH}" ]; then
        log_error "offline-repo.yml playbook not found: ${PLAYBOOK_PATH}"
        exit 1
    fi
    
    log_info "Running offline-repo.yml playbook..."
    log_info "  Inventory: ${INVENTORY_PATH}/hosts.yaml"
    log_info "  Playbook: ${PLAYBOOK_PATH}"
    
    # Requirement 11.3: Log Ansible output
    if log_command "Ansible offline-repo playbook" \
        "ansible-playbook -i ${INVENTORY_PATH}/hosts.yaml ${PLAYBOOK_PATH} --become -v"; then
        log_info "✓ Nodes configured for offline operation"
    else
        log_error_context "Ansible" "offline-repo.yml" "offline-repo.yml playbook failed" \
            "Check Ansible output for details"
        exit 1
    fi
    
else
    log_step "Step 5: Configure nodes (SKIPPED)"
    log_warn "Nodes may not be configured to use bastion repositories"
fi

# Step 6: Execute cluster.yml
if [ "${SKIP_CLUSTER_DEPLOY}" = "false" ]; then
    log_step "Step 6: Deploy Kubernetes cluster"
    
    log_info "Executing cluster.yml playbook..."
    log_info "This may take 20-30 minutes depending on cluster size"
    log_info ""
    log_info "  Inventory: ${INVENTORY_PATH}/hosts.yaml"
    log_info "  Playbook: cluster.yml"
    log_info "  Offline config: ${INVENTORY_PATH}/group_vars/all/offline.yml"
    log_info ""
    
    cd "${KUBESPRAY_DIR}"
    
    # Requirement 11.3: Log Ansible output
    # Run cluster.yml with verbose output
    if log_command "Ansible cluster.yml playbook" \
        "ansible-playbook -i ${INVENTORY_PATH}/hosts.yaml --become --become-user=root cluster.yml"; then
        log_info "✓ Kubernetes cluster deployed successfully"
    else
        log_error_context "Ansible" "cluster.yml" "Cluster deployment failed" \
            "Check Ansible logs for details" \
            "Logs location: ${KUBESPRAY_DIR}/ansible.log"
        exit 1
    fi
    
else
    log_step "Step 6: Deploy cluster (SKIPPED)"
    log_warn "Kubernetes cluster not deployed"
fi

# Step 7: Export kubeconfig
log_step "Step 7: Export kubeconfig"

KUBECONFIG_SRC="${INVENTORY_PATH}/artifacts/admin.conf"
KUBECONFIG_DEST="${HOME}/.kube/config"

if [ -f "${KUBECONFIG_SRC}" ]; then
    log_info "Exporting kubeconfig..."
    log_info "  Source: ${KUBECONFIG_SRC}"
    log_info "  Destination: ${KUBECONFIG_DEST}"
    
    # Create .kube directory if it doesn't exist
    mkdir -p "${HOME}/.kube"
    
    # Copy kubeconfig
    cp "${KUBECONFIG_SRC}" "${KUBECONFIG_DEST}"
    chmod 600 "${KUBECONFIG_DEST}"
    
    log_info "✓ Kubeconfig exported successfully"
    
    # Verify cluster access
    export KUBECONFIG="${KUBECONFIG_DEST}"
    
    log_info "Verifying cluster access..."
    if kubectl cluster-info &> /dev/null; then
        log_info "✓ Cluster is accessible"
        
        # Show cluster info
        echo ""
        kubectl cluster-info
        echo ""
        
        # Show nodes
        log_info "Cluster nodes:"
        kubectl get nodes -o wide
        
    else
        log_warn "Unable to access cluster"
        log_warn "Kubeconfig may need additional configuration"
    fi
    
else
    log_warn "Kubeconfig not found at: ${KUBECONFIG_SRC}"
    log_warn "Cluster may not have been deployed successfully"
fi

# Summary
echo ""
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log_info "Kubespray Deployment Complete"
log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
log_info "Deployment summary:"
log_info "  Mode: ${DEPLOYMENT_MODE}"
log_info "  Cluster: ${CLUSTER_NAME}"
log_info "  Bastion: ${BASTION_IP}"
log_info "  Kubespray: ${KUBESPRAY_DIR}"
log_info "  Inventory: ${INVENTORY_PATH}"

if [ -f "${KUBECONFIG_DEST}" ]; then
    log_info "  Kubeconfig: ${KUBECONFIG_DEST}"
fi

echo ""
log_info "Next steps:"
log_info "  1. Verify cluster health: kubectl get nodes"
log_info "  2. Check system pods: kubectl get pods -A"
log_info "  3. Deploy core services (Gitea, FluxCD, cert-manager, etc.)"
log_info "  4. Configure ingress and load balancing"
log_info "  5. Set up monitoring and logging"

echo ""
log_info "For troubleshooting:"
log_info "  - Ansible logs: ${KUBESPRAY_DIR}/ansible.log"
log_info "  - Kubespray artifacts: ${INVENTORY_PATH}/artifacts/"
log_info "  - Node logs: kubectl logs -n kube-system <pod-name>"

exit 0
