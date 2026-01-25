#!/bin/bash
set -euo pipefail

# FluxCD installation script with idempotency checks
#
# This script installs or updates FluxCD in the cluster.
# It is designed to be idempotent - safe to re-run multiple times.
#
# Requirements: 8.6

# Configuration
FLUX_NAMESPACE="${FLUX_NAMESPACE:-flux-system}"
FLUX_VERSION="${FLUX_VERSION:-v2.2.0}"
GITEA_URL="${GITEA_URL:-}"
GITEA_REPO="${GITEA_REPO:-cluster-config}"
GITEA_BRANCH="${GITEA_BRANCH:-main}"
GITEA_USERNAME="${GITEA_USERNAME:-gitea}"
GITEA_PASSWORD="${GITEA_PASSWORD:-}"

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

# Usage information
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Install or update FluxCD in the cluster with idempotency checks.

Optional:
  --gitea-url URL              Gitea URL (e.g., http://gitea.gitea.svc.cluster.local:3000)
  --gitea-repo REPO            Gitea repository name (default: cluster-config)
  --gitea-branch BRANCH        Git branch (default: main)
  --gitea-username USER        Gitea username (default: gitea)
  --gitea-password PASS        Gitea password
  --flux-version VERSION       FluxCD version (default: v2.2.0)
  --namespace NAMESPACE        FluxCD namespace (default: flux-system)
  --help                       Show this help message

Examples:
  # Install FluxCD (standalone)
  $0

  # Install FluxCD with Gitea integration
  $0 --gitea-url http://gitea.gitea.svc.cluster.local:3000 \\
     --gitea-username gitea \\
     --gitea-password mypassword

  # Update existing FluxCD installation
  $0 --flux-version v2.3.0

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --gitea-url)
            GITEA_URL="$2"
            shift 2
            ;;
        --gitea-repo)
            GITEA_REPO="$2"
            shift 2
            ;;
        --gitea-branch)
            GITEA_BRANCH="$2"
            shift 2
            ;;
        --gitea-username)
            GITEA_USERNAME="$2"
            shift 2
            ;;
        --gitea-password)
            GITEA_PASSWORD="$2"
            shift 2
            ;;
        --flux-version)
            FLUX_VERSION="$2"
            shift 2
            ;;
        --namespace)
            FLUX_NAMESPACE="$2"
            shift 2
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

# Check kubectl is available
if ! command -v kubectl &> /dev/null; then
    log_error "kubectl not found in PATH"
    exit 1
fi

# Check cluster is accessible
log_step "Checking cluster access"
if ! kubectl cluster-info &> /dev/null; then
    log_error "Cannot access cluster - ensure kubeconfig is configured"
    exit 1
fi
log_info "✓ Cluster is accessible"

# Check if flux CLI is available
log_step "Checking flux CLI"
if ! command -v flux &> /dev/null; then
    log_warn "flux CLI not found - will use kubectl for installation"
    USE_FLUX_CLI=false
else
    FLUX_CLI_VERSION=$(flux version --client 2>/dev/null | grep "flux:" | awk '{print $2}')
    log_info "✓ flux CLI available: ${FLUX_CLI_VERSION}"
    USE_FLUX_CLI=true
fi

# Check if FluxCD is already installed
log_step "Checking for existing FluxCD installation"

if kubectl get namespace "${FLUX_NAMESPACE}" &> /dev/null; then
    log_info "FluxCD namespace exists: ${FLUX_NAMESPACE}"
    FLUX_INSTALLED=true
    
    # Check if FluxCD controllers are running
    CONTROLLER_COUNT=$(kubectl get deployments -n "${FLUX_NAMESPACE}" --no-headers 2>/dev/null | wc -l)
    if [ "$CONTROLLER_COUNT" -gt 0 ]; then
        log_info "FluxCD controllers found: ${CONTROLLER_COUNT}"
        
        # List controllers
        log_info "Existing controllers:"
        kubectl get deployments -n "${FLUX_NAMESPACE}" --no-headers | awk '{print "  - " $1}'
        
        # Check controller health
        NOT_READY=$(kubectl get deployments -n "${FLUX_NAMESPACE}" --no-headers 2>/dev/null | awk '$2 !~ /^[0-9]+\/\1$/ {print $1}' | wc -l)
        if [ "$NOT_READY" -eq 0 ]; then
            log_info "✓ All controllers are ready"
        else
            log_warn "Some controllers not ready: ${NOT_READY}"
        fi
    else
        log_warn "FluxCD namespace exists but no controllers found"
        FLUX_INSTALLED=false
    fi
else
    log_info "FluxCD not installed (namespace does not exist)"
    FLUX_INSTALLED=false
fi

echo ""

# Install or update FluxCD
if [ "$FLUX_INSTALLED" = "true" ]; then
    log_step "Updating existing FluxCD installation"
    log_info "FluxCD is already installed - will update to ensure desired state"
    
    if [ "$USE_FLUX_CLI" = "true" ]; then
        log_info "Using flux CLI for update..."
        
        # flux install is idempotent - it will update existing installation
        if flux install \
            --namespace="${FLUX_NAMESPACE}" \
            --version="${FLUX_VERSION}"; then
            log_info "✓ FluxCD updated successfully"
        else
            log_error "FluxCD update failed"
            exit 1
        fi
    else
        log_info "Using kubectl for update..."
        log_warn "Manual update via kubectl not implemented"
        log_warn "Install flux CLI for automatic updates"
        log_info "✓ Using existing FluxCD installation"
    fi
    
else
    log_step "Installing FluxCD"
    
    if [ "$USE_FLUX_CLI" = "true" ]; then
        log_info "Using flux CLI for installation..."
        
        # flux install is idempotent
        if flux install \
            --namespace="${FLUX_NAMESPACE}" \
            --version="${FLUX_VERSION}"; then
            log_info "✓ FluxCD installed successfully"
        else
            log_error "FluxCD installation failed"
            exit 1
        fi
    else
        log_error "flux CLI required for installation"
        log_error "Please install flux CLI: https://fluxcd.io/flux/installation/"
        exit 1
    fi
fi

# Wait for FluxCD to be ready
log_step "Waiting for FluxCD controllers to be ready"
log_info "Waiting up to 5 minutes..."

TIMEOUT=300
ELAPSED=0
INTERVAL=10

while [ $ELAPSED -lt $TIMEOUT ]; do
    NOT_READY=$(kubectl get deployments -n "${FLUX_NAMESPACE}" --no-headers 2>/dev/null | awk '$2 !~ /^[0-9]+\/\1$/ {print $1}' | wc -l)
    
    if [ "$NOT_READY" -eq 0 ]; then
        log_info "✓ All FluxCD controllers are ready"
        break
    fi
    
    log_info "Waiting for controllers to be ready... (${ELAPSED}s elapsed)"
    sleep $INTERVAL
    ELAPSED=$((ELAPSED + INTERVAL))
done

if [ $ELAPSED -ge $TIMEOUT ]; then
    log_error "Timeout waiting for FluxCD controllers to be ready"
    log_error "Check controller status:"
    kubectl get deployments -n "${FLUX_NAMESPACE}"
    exit 1
fi

# Verify FluxCD installation
log_step "Verifying FluxCD installation"

if [ "$USE_FLUX_CLI" = "true" ]; then
    if flux check; then
        log_info "✓ FluxCD installation verified"
    else
        log_error "FluxCD verification failed"
        exit 1
    fi
else
    # Manual verification
    EXPECTED_CONTROLLERS=("source-controller" "kustomize-controller" "helm-controller" "notification-controller")
    ALL_PRESENT=true
    
    for controller in "${EXPECTED_CONTROLLERS[@]}"; do
        if kubectl get deployment -n "${FLUX_NAMESPACE}" "${controller}" &> /dev/null; then
            log_info "✓ ${controller} present"
        else
            log_error "✗ ${controller} missing"
            ALL_PRESENT=false
        fi
    done
    
    if [ "$ALL_PRESENT" = "true" ]; then
        log_info "✓ All expected controllers present"
    else
        log_error "Some controllers missing"
        exit 1
    fi
fi

# Configure Gitea integration if requested
if [ -n "${GITEA_URL}" ]; then
    log_step "Configuring Gitea integration"
    
    if [ -z "${GITEA_PASSWORD}" ]; then
        log_error "Gitea password required for integration"
        log_error "Use --gitea-password option"
        exit 1
    fi
    
    # Create Gitea credentials secret
    log_info "Creating Gitea credentials secret..."
    
    # Check if secret already exists
    if kubectl get secret -n "${FLUX_NAMESPACE}" gitea-credentials &> /dev/null; then
        log_info "Gitea credentials secret already exists - updating..."
        kubectl delete secret -n "${FLUX_NAMESPACE}" gitea-credentials
    fi
    
    kubectl create secret generic gitea-credentials \
        -n "${FLUX_NAMESPACE}" \
        --from-literal=username="${GITEA_USERNAME}" \
        --from-literal=password="${GITEA_PASSWORD}"
    
    log_info "✓ Gitea credentials secret created"
    
    # Create GitRepository resource
    log_info "Creating GitRepository resource..."
    
    cat <<EOF | kubectl apply -f -
apiVersion: source.toolkit.fluxcd.io/v1
kind: GitRepository
metadata:
  name: cluster-config
  namespace: ${FLUX_NAMESPACE}
spec:
  interval: 1m
  url: ${GITEA_URL}/${GITEA_USERNAME}/${GITEA_REPO}
  ref:
    branch: ${GITEA_BRANCH}
  secretRef:
    name: gitea-credentials
EOF
    
    log_info "✓ GitRepository resource created"
    
    # Wait for GitRepository to be ready
    log_info "Waiting for GitRepository to be ready..."
    
    TIMEOUT=60
    ELAPSED=0
    INTERVAL=5
    
    while [ $ELAPSED -lt $TIMEOUT ]; do
        STATUS=$(kubectl get gitrepository -n "${FLUX_NAMESPACE}" cluster-config -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "Unknown")
        
        if [ "$STATUS" = "True" ]; then
            log_info "✓ GitRepository is ready"
            break
        fi
        
        log_info "Waiting for GitRepository... (${ELAPSED}s elapsed)"
        sleep $INTERVAL
        ELAPSED=$((ELAPSED + INTERVAL))
    done
    
    if [ $ELAPSED -ge $TIMEOUT ]; then
        log_warn "Timeout waiting for GitRepository to be ready"
        log_warn "Check GitRepository status:"
        kubectl describe gitrepository -n "${FLUX_NAMESPACE}" cluster-config
    fi
fi

# Summary
log_step "FluxCD installation complete"

log_info "FluxCD status:"
kubectl get deployments -n "${FLUX_NAMESPACE}"

if [ -n "${GITEA_URL}" ]; then
    echo ""
    log_info "Gitea integration:"
    log_info "  URL: ${GITEA_URL}"
    log_info "  Repository: ${GITEA_USERNAME}/${GITEA_REPO}"
    log_info "  Branch: ${GITEA_BRANCH}"
    
    echo ""
    log_info "GitRepository status:"
    kubectl get gitrepository -n "${FLUX_NAMESPACE}" cluster-config
fi

echo ""
log_info "Next steps:"
log_info "  1. Verify FluxCD: flux check"
log_info "  2. Check controllers: kubectl get pods -n ${FLUX_NAMESPACE}"
log_info "  3. Create Kustomization resources for your applications"
log_info "  4. Monitor reconciliation: flux get all"

exit 0
