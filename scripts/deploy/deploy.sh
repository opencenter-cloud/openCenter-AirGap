#!/bin/bash
set -euo pipefail

# Main deployment orchestration script for openCenter AirGap
#
# This script orchestrates the complete deployment process:
# 1. Validate prerequisites
# 2. Generate inventory (bare-metal or OpenStack)
# 3. Configure nodes for offline operation
# 4. Deploy Kubernetes cluster with Kubespray
# 5. Verify cluster health

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source logging module
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/logging.sh"

# Default configuration
DEPLOYMENT_MODE="${DEPLOYMENT_MODE:-baremetal}"
BASTION_IP="${BASTION_IP:-}"
SSH_USER="${SSH_USER:-deployer}"
INSTALL_PATH="${INSTALL_PATH:-/opt/opencenter}"
CLUSTER_NAME="${CLUSTER_NAME:-mycluster}"
NODES_FILE="${NODES_FILE:-}"
OPENSTACK_CONFIG="${OPENSTACK_CONFIG:-}"
SKIP_INVENTORY="${SKIP_INVENTORY:-false}"
SKIP_OFFLINE_CONFIG="${SKIP_OFFLINE_CONFIG:-false}"
SKIP_CLUSTER_DEPLOY="${SKIP_CLUSTER_DEPLOY:-false}"

# Colors for output (for visual display, logging module handles file logging)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Enhanced logging functions that use both visual output and logging module
log_step() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}[STEP]${NC} $*"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    log_info "$*"
}

log_phase() {
    echo ""
    echo -e "${MAGENTA}╔════════════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${MAGENTA}║${NC} $*"
    echo -e "${MAGENTA}╚════════════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    log_phase_start "$*"
}

# Usage information
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Main deployment orchestration script for openCenter AirGap.

Required Options:
  --bastion-ip IP              IP address of bastion host
  --mode MODE                  Deployment mode: baremetal or openstack

Bare-metal Mode Options:
  --nodes FILE                 Path to node list file (JSON or YAML)

OpenStack Mode Options:
  --openstack-config FILE      Path to OpenStack configuration file

Common Options:
  --ssh-user USER              SSH user for node access (default: deployer)
  --cluster-name NAME          Cluster name (default: mycluster)
  --install-path PATH          Installation directory (default: /opt/opencenter)
  --skip-inventory             Skip inventory generation
  --skip-offline-config        Skip offline repository configuration
  --skip-cluster-deploy        Skip Kubernetes cluster deployment
  --help                       Show this help message

Environment Variables:
  DEPLOYMENT_MODE              Same as --mode
  BASTION_IP                   Same as --bastion-ip
  SSH_USER                     Same as --ssh-user
  INSTALL_PATH                 Same as --install-path
  CLUSTER_NAME                 Same as --cluster-name

Examples:
  # Bare-metal deployment
  $0 --mode baremetal --bastion-ip 192.168.1.5 --nodes nodes.yaml

  # OpenStack deployment
  $0 --mode openstack --bastion-ip 10.0.0.5 --openstack-config openstack.yaml

  # Bare-metal with custom cluster name
  $0 --mode baremetal --bastion-ip 192.168.1.5 --nodes nodes.yaml --cluster-name production

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
        --openstack-config)
            OPENSTACK_CONFIG="$2"
            shift 2
            ;;
        --ssh-user)
            SSH_USER="$2"
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
        --skip-inventory)
            SKIP_INVENTORY="true"
            shift
            ;;
        --skip-offline-config)
            SKIP_OFFLINE_CONFIG="true"
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

if [ "${DEPLOYMENT_MODE}" = "openstack" ] && [ -z "${OPENSTACK_CONFIG}" ] && [ "${SKIP_INVENTORY}" = "false" ]; then
    log_error "OpenStack mode requires --openstack-config FILE"
    exit 1
fi

# Initialize logging system
init_logging

# Display configuration
log_phase "openCenter AirGap Deployment"
log_info "Deployment mode: ${DEPLOYMENT_MODE}"
log_info "Bastion IP: ${BASTION_IP}"
log_info "SSH user: ${SSH_USER}"
log_info "Cluster name: ${CLUSTER_NAME}"
log_info "Install path: ${INSTALL_PATH}"

if [ "${DEPLOYMENT_MODE}" = "baremetal" ]; then
    log_info "Nodes file: ${NODES_FILE}"
else
    log_info "OpenStack config: ${OPENSTACK_CONFIG}"
fi

# Set paths
INVENTORY_PATH="${INSTALL_PATH}/kubespray/inventory/${CLUSTER_NAME}"
SCRIPTS_PATH="${INSTALL_PATH}/scripts"

# Phase 1: Validate prerequisites
log_phase "Phase 1: Validate Prerequisites"

log_step "Checking installation directory"
if [ ! -d "${INSTALL_PATH}" ]; then
    log_error "Installation directory not found: ${INSTALL_PATH}"
    log_error "Please deploy the Zarf package first"
    exit 1
fi
log_info "✓ Installation directory exists"

log_step "Checking deployment scripts"
REQUIRED_SCRIPTS=(
    "${SCRIPTS_PATH}/generate_inventory_baremetal.py"
    "${SCRIPTS_PATH}/generate_offline_yml.py"
    "${SCRIPTS_PATH}/configure_nodes_offline.sh"
)

for script in "${REQUIRED_SCRIPTS[@]}"; do
    if [ ! -f "${script}" ]; then
        log_error "Required script not found: ${script}"
        exit 1
    fi
done
log_info "✓ All deployment scripts found"

log_step "Checking bastion services"
log_info "Checking nginx (port 80)..."
if curl -sf "http://localhost/files/" > /dev/null 2>&1; then
    log_info "✓ Nginx is running and serving files"
else
    log_warn "Nginx may not be running or not serving files"
    log_warn "Expected: http://localhost/files/"
fi

log_info "Checking registry (port 35000)..."
if curl -sf "http://localhost:35000/v2/_catalog" > /dev/null 2>&1; then
    log_info "✓ Registry is running"
else
    log_warn "Registry may not be running"
    log_warn "Expected: http://localhost:35000/v2/_catalog"
fi

# Phase 2: Generate inventory
if [ "${SKIP_INVENTORY}" = "false" ]; then
    log_phase "Phase 2: Generate Inventory"

    if [ "${DEPLOYMENT_MODE}" = "baremetal" ]; then
        log_step "Generating inventory for bare-metal deployment"
        
        if [ ! -f "${NODES_FILE}" ]; then
            log_error "Nodes file not found: ${NODES_FILE}"
            exit 1
        fi
        
        log_info "Nodes file: ${NODES_FILE}"
        log_info "Output directory: ${INSTALL_PATH}/kubespray/inventory"
        
        if python3 "${SCRIPTS_PATH}/generate_inventory_baremetal.py" \
            --nodes "${NODES_FILE}" \
            --bastion-ip "${BASTION_IP}" \
            --cluster-name "${CLUSTER_NAME}" \
            --output-dir "${INSTALL_PATH}/kubespray/inventory"; then
            log_info "✓ Inventory generated successfully"
        else
            log_error "Failed to generate inventory"
            exit 1
        fi
        
    else
        log_step "Provisioning infrastructure on OpenStack"
        
        if [ ! -f "${OPENSTACK_CONFIG}" ]; then
            log_error "OpenStack configuration file not found: ${OPENSTACK_CONFIG}"
            exit 1
        fi
        
        log_info "OpenStack config: ${OPENSTACK_CONFIG}"
        log_info "Terraform directory: ${INSTALL_PATH}/terraform"
        
        # Run Terraform provisioning script
        if "${SCRIPTS_PATH}/terraform_openstack.sh" \
            --config "${OPENSTACK_CONFIG}" \
            --bastion-ip "${BASTION_IP}" \
            --cluster-name "${CLUSTER_NAME}" \
            --terraform-dir "${INSTALL_PATH}/terraform"; then
            log_info "✓ Infrastructure provisioned on OpenStack"
        else
            log_error "Failed to provision infrastructure"
            log_error "Check Terraform logs for details"
            exit 1
        fi
    fi
    
    # Verify inventory was created
    if [ ! -f "${INVENTORY_PATH}/hosts.yaml" ]; then
        log_error "Inventory file not created: ${INVENTORY_PATH}/hosts.yaml"
        exit 1
    fi
    log_info "✓ Inventory file: ${INVENTORY_PATH}/hosts.yaml"
    
    if [ ! -f "${INVENTORY_PATH}/group_vars/all/offline.yml" ]; then
        log_error "offline.yml not created: ${INVENTORY_PATH}/group_vars/all/offline.yml"
        exit 1
    fi
    log_info "✓ Offline config: ${INVENTORY_PATH}/group_vars/all/offline.yml"
    
else
    log_phase "Phase 2: Inventory Generation (SKIPPED)"
    log_warn "Using existing inventory at: ${INVENTORY_PATH}"
    
    # Verify inventory exists
    if [ ! -f "${INVENTORY_PATH}/hosts.yaml" ]; then
        log_error "Inventory file not found: ${INVENTORY_PATH}/hosts.yaml"
        log_error "Cannot skip inventory generation without existing inventory"
        exit 1
    fi
fi

# Phase 3: Configure nodes for offline operation
if [ "${SKIP_OFFLINE_CONFIG}" = "false" ]; then
    log_phase "Phase 3: Configure Nodes for Offline Operation"
    
    log_step "Running offline repository configuration"
    
    if "${SCRIPTS_PATH}/configure_nodes_offline.sh" \
        --bastion-ip "${BASTION_IP}" \
        --inventory-path "${INVENTORY_PATH}" \
        --install-path "${INSTALL_PATH}"; then
        log_info "✓ Nodes configured for offline operation"
    else
        log_error "Failed to configure nodes"
        exit 1
    fi
    
else
    log_phase "Phase 3: Offline Configuration (SKIPPED)"
    log_warn "Nodes may not be configured to use bastion repositories"
fi

# Phase 4: Deploy Kubernetes cluster
if [ "${SKIP_CLUSTER_DEPLOY}" = "false" ]; then
    log_phase "Phase 4: Deploy Kubernetes Cluster"
    
    log_step "Running Kubespray deployment script"
    
    # Prepare arguments for deploy_kubespray.sh
    KUBESPRAY_ARGS=(
        "--mode" "${DEPLOYMENT_MODE}"
        "--bastion-ip" "${BASTION_IP}"
        "--cluster-name" "${CLUSTER_NAME}"
        "--install-path" "${INSTALL_PATH}"
    )
    
    # Add mode-specific arguments
    if [ "${DEPLOYMENT_MODE}" = "baremetal" ]; then
        if [ -n "${NODES_FILE}" ]; then
            KUBESPRAY_ARGS+=("--nodes" "${NODES_FILE}")
        fi
    else
        # OpenStack mode - inventory already generated by Terraform
        KUBESPRAY_ARGS+=("--inventory-path" "${INVENTORY_PATH}")
        KUBESPRAY_ARGS+=("--skip-inventory")
    fi
    
    # Skip offline config if already done
    if [ "${SKIP_OFFLINE_CONFIG}" = "true" ]; then
        KUBESPRAY_ARGS+=("--skip-offline-repo")
    fi
    
    log_info "Executing: ${SCRIPTS_PATH}/deploy_kubespray.sh ${KUBESPRAY_ARGS[*]}"
    
    if "${SCRIPTS_PATH}/deploy_kubespray.sh" "${KUBESPRAY_ARGS[@]}"; then
        log_info "✓ Kubernetes cluster deployed successfully"
    else
        log_error "Kubespray deployment failed"
        log_error "Check logs for details"
        exit 1
    fi
    
else
    log_phase "Phase 4: Cluster Deployment (SKIPPED)"
    log_warn "Kubernetes cluster not deployed"
fi

# Phase 5: Verify cluster
log_phase "Phase 5: Verify Cluster"

KUBECONFIG_PATH="${HOME}/.kube/config"
if [ ! -f "${KUBECONFIG_PATH}" ]; then
    KUBECONFIG_PATH="${INVENTORY_PATH}/artifacts/admin.conf"
fi

if [ -f "${KUBECONFIG_PATH}" ]; then
    export KUBECONFIG="${KUBECONFIG_PATH}"
    
    log_step "Checking cluster nodes"
    if kubectl get nodes 2>/dev/null; then
        log_info "✓ Cluster nodes accessible"
    else
        log_warn "Unable to access cluster nodes"
        log_warn "Kubeconfig may not be configured correctly"
    fi
    
    log_step "Checking system pods"
    if kubectl get pods -A 2>/dev/null | head -20; then
        log_info "✓ System pods running"
    else
        log_warn "Unable to list pods"
    fi
else
    log_warn "Kubeconfig not found, skipping cluster verification"
fi

# Summary
log_phase "Deployment Complete"

log_info "Deployment summary:"
log_info "  Mode: ${DEPLOYMENT_MODE}"
log_info "  Cluster: ${CLUSTER_NAME}"
log_info "  Bastion: ${BASTION_IP}"
log_info "  Inventory: ${INVENTORY_PATH}"

if [ -f "${KUBECONFIG_PATH}" ]; then
    log_info "  Kubeconfig: ${KUBECONFIG_PATH}"
fi

echo ""
log_info "Next steps:"
log_info "  1. Verify cluster health: kubectl get nodes"
log_info "  2. Check system pods: kubectl get pods -A"
log_info "  3. Deploy core services (Gitea, FluxCD, cert-manager, etc.)"
log_info "  4. Configure ingress and load balancing"
log_info "  5. Set up monitoring and logging"

echo ""
log_info "For troubleshooting, check logs at:"
log_info "  - Ansible logs: ${KUBESPRAY_PATH}/ansible.log"
log_info "  - Kubespray artifacts: ${INVENTORY_PATH}/artifacts/"

exit 0
