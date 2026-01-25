#!/bin/bash
# Example workflow for deploying Kubernetes cluster in bare-metal mode
# This script demonstrates the complete deployment process

set -euo pipefail

# Configuration
BASTION_IP="192.168.1.5"
INSTALL_PATH="/opt/opencenter"
CLUSTER_NAME="mycluster"
NODES_FILE="examples/nodes-baremetal.yaml"

echo "=== openCenter AirGap Deployment Workflow (Bare-metal) ==="
echo ""
echo "Prerequisites:"
echo "  - Zarf package deployed to bastion"
echo "  - Bastion services running (nginx:80, registry:35000)"
echo "  - SSH access to all cluster nodes"
echo "  - Node list file: ${NODES_FILE}"
echo ""

# Option 1: Automated deployment (recommended)
echo "=== Option 1: Automated Deployment (Recommended) ==="
echo ""
echo "Running complete deployment with deploy.sh..."
${INSTALL_PATH}/scripts/deploy.sh \
  --mode baremetal \
  --bastion-ip "${BASTION_IP}" \
  --nodes "${NODES_FILE}" \
  --cluster-name "${CLUSTER_NAME}"

echo ""
echo "=== Deployment Complete ==="
echo ""

# Option 2: Manual step-by-step (for demonstration)
# Uncomment to use manual approach
: <<'MANUAL_DEPLOYMENT'

echo "=== Option 2: Manual Step-by-Step Deployment ==="
echo ""

# Step 1: Generate inventory
echo "Step 1: Generate Kubespray inventory"
echo "---------------------------------------"
python3 ${INSTALL_PATH}/scripts/generate_inventory_baremetal.py \
  --nodes "${NODES_FILE}" \
  --bastion-ip "${BASTION_IP}" \
  --cluster-name "${CLUSTER_NAME}" \
  --output-dir "${INSTALL_PATH}/kubespray/inventory"

echo ""
echo "✓ Inventory generated at: ${INSTALL_PATH}/kubespray/inventory/${CLUSTER_NAME}"
echo ""

# Step 2: Configure nodes to use offline repositories
echo "Step 2: Configure nodes for offline operation"
echo "----------------------------------------------"
${INSTALL_PATH}/scripts/configure_nodes_offline.sh \
  --bastion-ip "${BASTION_IP}" \
  --inventory-path "${INSTALL_PATH}/kubespray/inventory/${CLUSTER_NAME}"

echo ""
echo "✓ Nodes configured to use bastion repositories"
echo ""

# Step 3: Deploy Kubernetes cluster using deploy_kubespray.sh
echo "Step 3: Deploy Kubernetes cluster with Kubespray"
echo "-------------------------------------------------"
${INSTALL_PATH}/scripts/deploy_kubespray.sh \
  --mode baremetal \
  --bastion-ip "${BASTION_IP}" \
  --nodes "${NODES_FILE}" \
  --cluster-name "${CLUSTER_NAME}" \
  --skip-offline-repo

echo ""
echo "✓ Kubernetes cluster deployed"
echo ""

MANUAL_DEPLOYMENT

# Verify cluster
echo "Verifying cluster health..."
echo "----------------------------"
export KUBECONFIG="${HOME}/.kube/config"

echo "Checking nodes..."
kubectl get nodes

echo ""
echo "Checking system pods..."
kubectl get pods -A | head -20

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "Kubeconfig: ${KUBECONFIG}"
echo "Next steps:"
echo "  - Deploy core services (Gitea, FluxCD, cert-manager, etc.)"
echo "  - Configure ingress and load balancing"
echo "  - Set up monitoring and logging"

