#!/bin/bash
set -euo pipefail

# Terraform execution script for OpenStack infrastructure provisioning
#
# This script:
# 1. Validates OpenStack credentials and configuration
# 2. Initializes Terraform with filesystem mirror
# 3. Plans infrastructure changes
# 4. Applies infrastructure (creates VMs, networks)
# 5. Generates Ansible inventory from Terraform outputs
# 6. Preserves state on failure for recovery

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source logging module
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/logging.sh"

INSTALL_PATH="${INSTALL_PATH:-/opt/opencenter}"
TERRAFORM_DIR="${TERRAFORM_DIR:-${INSTALL_PATH}/terraform}"
OPENSTACK_CONFIG="${OPENSTACK_CONFIG:-}"
CLUSTER_NAME="${CLUSTER_NAME:-mycluster}"
BASTION_IP="${BASTION_IP:-}"
AUTO_APPROVE="${AUTO_APPROVE:-false}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Usage information
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Terraform execution script for OpenStack infrastructure provisioning.

Required Options:
  --config FILE                Path to OpenStack configuration file
  --bastion-ip IP              IP address of bastion host

Optional:
  --cluster-name NAME          Cluster name (default: mycluster)
  --terraform-dir PATH         Terraform working directory (default: ${INSTALL_PATH}/terraform)
  --auto-approve               Skip interactive approval for terraform apply
  --destroy                    Destroy infrastructure instead of creating
  --help                       Show this help message

OpenStack Configuration File Format (YAML):
  auth_url: https://openstack.example.com:5000/v3
  project_name: my-project
  username: my-user
  password: my-password
  region: RegionOne
  domain_name: Default
  
  # VM Configuration
  control_plane_count: 3
  worker_count: 2
  flavor: m1.large
  image: ubuntu-24.04
  network: private-network
  floating_ip_pool: public
  key_pair: my-keypair

Examples:
  # Plan and apply infrastructure
  $0 --config openstack.yaml --bastion-ip 10.0.0.5

  # Auto-approve (non-interactive)
  $0 --config openstack.yaml --bastion-ip 10.0.0.5 --auto-approve

  # Destroy infrastructure
  $0 --config openstack.yaml --bastion-ip 10.0.0.5 --destroy

EOF
}

# Parse command line arguments
DESTROY_MODE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --config)
            OPENSTACK_CONFIG="$2"
            shift 2
            ;;
        --bastion-ip)
            BASTION_IP="$2"
            shift 2
            ;;
        --cluster-name)
            CLUSTER_NAME="$2"
            shift 2
            ;;
        --terraform-dir)
            TERRAFORM_DIR="$2"
            shift 2
            ;;
        --auto-approve)
            AUTO_APPROVE="true"
            shift
            ;;
        --destroy)
            DESTROY_MODE=true
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
if [ -z "${OPENSTACK_CONFIG}" ]; then
    log_error "OpenStack configuration file is required. Use --config FILE"
    exit 1
fi

if [ ! -f "${OPENSTACK_CONFIG}" ]; then
    log_error "OpenStack configuration file not found: ${OPENSTACK_CONFIG}"
    exit 1
fi

if [ -z "${BASTION_IP}" ]; then
    log_error "Bastion IP is required. Use --bastion-ip IP"
    exit 1
fi

# Load OpenStack configuration
log_step "Loading OpenStack configuration"
log_info "Config file: ${OPENSTACK_CONFIG}"

# Check if Python is available for YAML parsing
if ! command -v python3 &> /dev/null; then
    log_error "Python3 is required for configuration parsing"
    exit 1
fi

# Parse YAML configuration
CONFIG_JSON=$(python3 << 'EOF'
import sys
import yaml
import json

try:
    with open(sys.argv[1], 'r') as f:
        config = yaml.safe_load(f)
    print(json.dumps(config))
except Exception as e:
    print(f"Error parsing config: {e}", file=sys.stderr)
    sys.exit(1)
EOF
"${OPENSTACK_CONFIG}")

if [ $? -ne 0 ]; then
    log_error "Failed to parse OpenStack configuration"
    exit 1
fi

# Extract configuration values
OS_AUTH_URL=$(echo "${CONFIG_JSON}" | python3 -c "import sys, json; print(json.load(sys.stdin).get('auth_url', ''))")
OS_PROJECT_NAME=$(echo "${CONFIG_JSON}" | python3 -c "import sys, json; print(json.load(sys.stdin).get('project_name', ''))")
OS_USERNAME=$(echo "${CONFIG_JSON}" | python3 -c "import sys, json; print(json.load(sys.stdin).get('username', ''))")
OS_PASSWORD=$(echo "${CONFIG_JSON}" | python3 -c "import sys, json; print(json.load(sys.stdin).get('password', ''))")
OS_REGION=$(echo "${CONFIG_JSON}" | python3 -c "import sys, json; print(json.load(sys.stdin).get('region', 'RegionOne'))")
OS_DOMAIN_NAME=$(echo "${CONFIG_JSON}" | python3 -c "import sys, json; print(json.load(sys.stdin).get('domain_name', 'Default'))")

CONTROL_PLANE_COUNT=$(echo "${CONFIG_JSON}" | python3 -c "import sys, json; print(json.load(sys.stdin).get('control_plane_count', 3))")
WORKER_COUNT=$(echo "${CONFIG_JSON}" | python3 -c "import sys, json; print(json.load(sys.stdin).get('worker_count', 2))")
FLAVOR=$(echo "${CONFIG_JSON}" | python3 -c "import sys, json; print(json.load(sys.stdin).get('flavor', 'm1.large'))")
IMAGE=$(echo "${CONFIG_JSON}" | python3 -c "import sys, json; print(json.load(sys.stdin).get('image', 'ubuntu-24.04'))")
NETWORK=$(echo "${CONFIG_JSON}" | python3 -c "import sys, json; print(json.load(sys.stdin).get('network', ''))")
FLOATING_IP_POOL=$(echo "${CONFIG_JSON}" | python3 -c "import sys, json; print(json.load(sys.stdin).get('floating_ip_pool', ''))")
KEY_PAIR=$(echo "${CONFIG_JSON}" | python3 -c "import sys, json; print(json.load(sys.stdin).get('key_pair', ''))")

# Validate required OpenStack parameters
if [ -z "${OS_AUTH_URL}" ] || [ -z "${OS_PROJECT_NAME}" ] || [ -z "${OS_USERNAME}" ] || [ -z "${OS_PASSWORD}" ]; then
    log_error "Missing required OpenStack credentials in configuration file"
    log_error "Required: auth_url, project_name, username, password"
    exit 1
fi

if [ -z "${NETWORK}" ]; then
    log_error "Missing required parameter: network"
    exit 1
fi

log_info "✓ Configuration loaded"
log_info "  Project: ${OS_PROJECT_NAME}"
log_info "  Region: ${OS_REGION}"
log_info "  Control planes: ${CONTROL_PLANE_COUNT}"
log_info "  Workers: ${WORKER_COUNT}"

# Export OpenStack environment variables
export OS_AUTH_URL
export OS_PROJECT_NAME
export OS_USERNAME
export OS_PASSWORD
export OS_REGION_NAME="${OS_REGION}"
export OS_USER_DOMAIN_NAME="${OS_DOMAIN_NAME}"
export OS_PROJECT_DOMAIN_NAME="${OS_DOMAIN_NAME}"

# Check Terraform directory
log_step "Checking Terraform directory"
if [ ! -d "${TERRAFORM_DIR}" ]; then
    log_error "Terraform directory not found: ${TERRAFORM_DIR}"
    log_error "Please ensure Terraform configuration is deployed"
    exit 1
fi
log_info "✓ Terraform directory: ${TERRAFORM_DIR}"

# Check .terraformrc configuration
log_step "Checking Terraform configuration"
if [ ! -f "/root/.terraformrc" ]; then
    log_warn ".terraformrc not found at /root/.terraformrc"
    log_warn "Terraform may attempt to download providers from internet"
else
    log_info "✓ .terraformrc configured for offline operation"
fi

# Check for existing Terraform state
log_step "Checking for existing Terraform state"
cd "${TERRAFORM_DIR}"

if [ -f "terraform.tfstate" ]; then
    log_info "Existing Terraform state found"
    
    # Check if state has resources
    RESOURCE_COUNT=$(terraform show -json 2>/dev/null | python3 -c "import sys, json; data = json.load(sys.stdin); print(len(data.get('values', {}).get('root_module', {}).get('resources', [])))" 2>/dev/null || echo "0")
    
    if [ "${RESOURCE_COUNT}" -gt 0 ]; then
        log_info "State contains ${RESOURCE_COUNT} existing resources"
        log_info "Terraform will use existing state for planning"
    else
        log_info "State file exists but contains no resources"
    fi
else
    log_info "No existing Terraform state found (fresh deployment)"
fi

# Initialize Terraform
log_step "Initializing Terraform"

# Requirement 11.2: Log Terraform output
if log_command "Terraform init" "terraform init -upgrade=false"; then
    log_info "✓ Terraform initialized"
else
    log_error_context "Terraform" "init" "Terraform initialization failed" \
        "Check that provider mirror is configured correctly" \
        "Verify .terraformrc at /root/.terraformrc"
    exit 1
fi

# Validate Terraform configuration
log_step "Validating Terraform configuration"
if log_command "Terraform validate" "terraform validate"; then
    log_info "✓ Terraform configuration is valid"
else
    log_error_context "Terraform" "validate" "Terraform configuration validation failed"
    exit 1
fi

if [ "${DESTROY_MODE}" = "true" ]; then
    # Destroy infrastructure
    log_step "Destroying infrastructure"
    log_warn "This will destroy all resources created by Terraform"
    
    if [ "${AUTO_APPROVE}" = "true" ]; then
        APPROVE_FLAG="-auto-approve"
    else
        APPROVE_FLAG=""
    fi
    
    if terraform destroy ${APPROVE_FLAG} \
        -var="cluster_name=${CLUSTER_NAME}" \
        -var="control_plane_count=${CONTROL_PLANE_COUNT}" \
        -var="worker_count=${WORKER_COUNT}" \
        -var="flavor=${FLAVOR}" \
        -var="image=${IMAGE}" \
        -var="network=${NETWORK}" \
        -var="floating_ip_pool=${FLOATING_IP_POOL}" \
        -var="key_pair=${KEY_PAIR}"; then
        log_info "✓ Infrastructure destroyed"
    else
        log_error "Terraform destroy failed"
        log_error "State file preserved at: ${TERRAFORM_DIR}/terraform.tfstate"
        exit 1
    fi
    
    exit 0
fi

# Plan infrastructure changes
log_step "Planning infrastructure changes"
PLAN_OUTPUT=$(mktemp)

if terraform plan \
    -var="cluster_name=${CLUSTER_NAME}" \
    -var="control_plane_count=${CONTROL_PLANE_COUNT}" \
    -var="worker_count=${WORKER_COUNT}" \
    -var="flavor=${FLAVOR}" \
    -var="image=${IMAGE}" \
    -var="network=${NETWORK}" \
    -var="floating_ip_pool=${FLOATING_IP_POOL}" \
    -var="key_pair=${KEY_PAIR}" \
    -out=tfplan | tee "${PLAN_OUTPUT}"; then
    log_info "✓ Terraform plan created"
    
    # Check if plan has changes
    if grep -q "No changes" "${PLAN_OUTPUT}"; then
        log_info "Infrastructure already exists and matches desired state"
        log_info "No changes needed - skipping apply"
        rm -f "${PLAN_OUTPUT}" tfplan
        
        # Still need to extract outputs for inventory generation
        log_step "Extracting Terraform outputs from existing state"
        CONTROL_PLANE_IPS=$(terraform output -json control_plane_ips 2>/dev/null || echo "[]")
        WORKER_IPS=$(terraform output -json worker_ips 2>/dev/null || echo "[]")
        
        if [ "${CONTROL_PLANE_IPS}" != "[]" ] && [ "${WORKER_IPS}" != "[]" ]; then
            log_info "✓ Using existing infrastructure"
            SKIP_APPLY=true
        else
            log_warn "Could not extract outputs from existing state"
            log_warn "Will proceed with apply to ensure outputs are available"
            SKIP_APPLY=false
        fi
    else
        log_info "Infrastructure changes detected"
        SKIP_APPLY=false
    fi
    
    rm -f "${PLAN_OUTPUT}"
else
    log_error "Terraform plan failed"
    rm -f "${PLAN_OUTPUT}"
    exit 1
fi

# Apply infrastructure changes
if [ "${SKIP_APPLY:-false}" = "false" ]; then
    log_step "Applying infrastructure changes"
    log_info "This will create VMs and network resources in OpenStack"

    if [ "${AUTO_APPROVE}" = "true" ]; then
        APPROVE_FLAG="-auto-approve"
    else
        APPROVE_FLAG=""
    fi

    if terraform apply ${APPROVE_FLAG} tfplan; then
        log_info "✓ Infrastructure provisioned"
    else
        log_error "Terraform apply failed"
        log_error "State file preserved at: ${TERRAFORM_DIR}/terraform.tfstate"
        log_error "You can retry by re-running this script"
        exit 1
    fi

    # Wait for VMs to be ready
    log_step "Waiting for VMs to reach running state"
    log_info "Waiting 30 seconds for VMs to initialize..."
    sleep 30
    log_info "✓ VMs should be running"
    
    # Extract Terraform outputs
    log_step "Extracting Terraform outputs"
    CONTROL_PLANE_IPS=$(terraform output -json control_plane_ips 2>/dev/null || echo "[]")
    WORKER_IPS=$(terraform output -json worker_ips 2>/dev/null || echo "[]")
else
    log_step "Applying infrastructure changes (SKIPPED)"
    log_info "Infrastructure already exists - using existing resources"
fi

if [ "${CONTROL_PLANE_IPS}" = "[]" ] || [ "${WORKER_IPS}" = "[]" ]; then
    log_error "Failed to extract Terraform outputs"
    log_error "Ensure Terraform configuration defines control_plane_ips and worker_ips outputs"
    exit 1
fi

log_info "✓ Terraform outputs extracted"
log_info "  Control plane IPs: ${CONTROL_PLANE_IPS}"
log_info "  Worker IPs: ${WORKER_IPS}"

# Generate Ansible inventory
log_step "Generating Ansible inventory from Terraform outputs"

INVENTORY_DIR="${INSTALL_PATH}/kubespray/inventory/${CLUSTER_NAME}"
mkdir -p "${INVENTORY_DIR}/group_vars/all"

# Create inventory JSON for Python script
INVENTORY_JSON=$(python3 << EOF
import json
import sys

control_ips = json.loads('${CONTROL_PLANE_IPS}')
worker_ips = json.loads('${WORKER_IPS}')

inventory = {
    "control_plane": [
        {"hostname": f"control-{i+1:02d}", "ip": ip}
        for i, ip in enumerate(control_ips)
    ],
    "workers": [
        {"hostname": f"worker-{i+1:02d}", "ip": ip}
        for i, ip in enumerate(worker_ips)
    ]
}

print(json.dumps(inventory))
EOF
)

# Save inventory JSON to temp file
TEMP_INVENTORY="/tmp/inventory-${CLUSTER_NAME}.json"
echo "${INVENTORY_JSON}" > "${TEMP_INVENTORY}"

# Generate inventory using existing script
if python3 "${INSTALL_PATH}/scripts/generate_inventory_baremetal.py" \
    --nodes "${TEMP_INVENTORY}" \
    --bastion-ip "${BASTION_IP}" \
    --cluster-name "${CLUSTER_NAME}" \
    --output-dir "${INSTALL_PATH}/kubespray/inventory"; then
    log_info "✓ Ansible inventory generated"
    rm -f "${TEMP_INVENTORY}"
else
    log_error "Failed to generate Ansible inventory"
    rm -f "${TEMP_INVENTORY}"
    exit 1
fi

log_info "Inventory location: ${INVENTORY_DIR}/hosts.yaml"
log_info "Offline config: ${INVENTORY_DIR}/group_vars/all/offline.yml"

# Summary
log_step "Infrastructure provisioning complete"
log_info "Resources created:"
log_info "  - ${CONTROL_PLANE_COUNT} control plane VMs"
log_info "  - ${WORKER_COUNT} worker VMs"
log_info "  - Network resources"
log_info ""
log_info "State file: ${TERRAFORM_DIR}/terraform.tfstate"
log_info "Inventory: ${INVENTORY_DIR}/hosts.yaml"
log_info ""
log_info "Next steps:"
log_info "  1. Configure nodes for offline operation"
log_info "  2. Deploy Kubernetes cluster with Kubespray"

exit 0
