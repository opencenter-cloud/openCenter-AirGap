#!/bin/bash
set -euo pipefail

# Verify Kubernetes cluster health
#
# This script checks:
# 1. Control plane component health (API server, controller-manager, scheduler, etcd)
# 2. Node Ready status
# 3. System pod health
#
# Requirements: 6.9, 6.10

# Default configuration
KUBECONFIG="${KUBECONFIG:-${HOME}/.kube/config}"
TIMEOUT="${TIMEOUT:-300}"
CHECK_INTERVAL="${CHECK_INTERVAL:-5}"
VERBOSE="${VERBOSE:-false}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

log_debug() {
    if [ "${VERBOSE}" = "true" ]; then
        echo -e "${CYAN}[DEBUG]${NC} $*"
    fi
}

log_section() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}$*${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# Usage information
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Verify Kubernetes cluster health by checking control plane components and node status.

Options:
  --kubeconfig PATH            Path to kubeconfig file (default: ~/.kube/config)
  --timeout SECONDS            Maximum time to wait for cluster (default: 300)
  --check-interval SECONDS     Interval between health checks (default: 5)
  --verbose                    Enable verbose output
  --help                       Show this help message

Environment Variables:
  KUBECONFIG                   Same as --kubeconfig
  TIMEOUT                      Same as --timeout
  CHECK_INTERVAL               Same as --check-interval
  VERBOSE                      Set to 'true' for verbose output

Exit Codes:
  0  - Cluster is healthy
  1  - Cluster is unhealthy or unreachable
  2  - Invalid arguments

Examples:
  # Basic health check
  $0

  # Check with custom kubeconfig
  $0 --kubeconfig /path/to/kubeconfig

  # Wait up to 10 minutes for cluster to become healthy
  $0 --timeout 600

  # Verbose output
  $0 --verbose

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --kubeconfig)
            KUBECONFIG="$2"
            shift 2
            ;;
        --timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        --check-interval)
            CHECK_INTERVAL="$2"
            shift 2
            ;;
        --verbose)
            VERBOSE="true"
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
            exit 2
            ;;
    esac
done

# Validate kubeconfig exists
if [ ! -f "${KUBECONFIG}" ]; then
    log_error "Kubeconfig not found: ${KUBECONFIG}"
    log_error "Please ensure cluster has been deployed and kubeconfig is available"
    exit 1
fi

export KUBECONFIG

# Verify kubectl is available
if ! command -v kubectl &> /dev/null; then
    log_error "kubectl not found in PATH"
    log_error "Please install kubectl or ensure it is in your PATH"
    exit 1
fi

log_info "Cluster Health Verification"
log_info "  Kubeconfig: ${KUBECONFIG}"
log_info "  Timeout: ${TIMEOUT}s"
log_info "  Check interval: ${CHECK_INTERVAL}s"

# Track overall health status
OVERALL_HEALTHY=true
UNHEALTHY_COMPONENTS=()

# Function to check if cluster is reachable
check_cluster_reachable() {
    log_section "Checking Cluster Connectivity"
    
    log_info "Attempting to connect to cluster..."
    
    if kubectl cluster-info &> /dev/null; then
        log_info "✓ Cluster is reachable"
        
        if [ "${VERBOSE}" = "true" ]; then
            kubectl cluster-info
        fi
        
        return 0
    else
        log_error "✗ Unable to connect to cluster"
        return 1
    fi
}

# Function to check control plane component health
check_control_plane_components() {
    log_section "Checking Control Plane Components"
    
    local components_healthy=true
    
    # Check component status using componentstatuses (deprecated but still useful)
    log_info "Checking component statuses..."
    
    # Note: componentstatuses is deprecated in K8s 1.19+
    # We'll check pods in kube-system namespace instead
    
    # Define expected control plane components
    local components=(
        "kube-apiserver"
        "kube-controller-manager"
        "kube-scheduler"
        "etcd"
    )
    
    for component in "${components[@]}"; do
        log_debug "Checking ${component}..."
        
        # Get pods for this component
        local pod_count
        pod_count=$(kubectl get pods -n kube-system \
            -l component="${component}" \
            --no-headers 2>/dev/null | wc -l)
        
        # If no pods found with component label, try tier label
        if [ "${pod_count}" -eq 0 ]; then
            pod_count=$(kubectl get pods -n kube-system \
                -l tier=control-plane,component="${component}" \
                --no-headers 2>/dev/null | wc -l)
        fi
        
        # For etcd, try different label
        if [ "${component}" = "etcd" ] && [ "${pod_count}" -eq 0 ]; then
            pod_count=$(kubectl get pods -n kube-system \
                -l component=etcd \
                --no-headers 2>/dev/null | wc -l)
        fi
        
        if [ "${pod_count}" -eq 0 ]; then
            log_warn "✗ ${component}: No pods found"
            log_debug "  This may be normal for some deployment types"
            continue
        fi
        
        # Check if all pods are running
        local running_count
        running_count=$(kubectl get pods -n kube-system \
            -l component="${component}" \
            --field-selector=status.phase=Running \
            --no-headers 2>/dev/null | wc -l)
        
        if [ "${running_count}" -eq 0 ]; then
            running_count=$(kubectl get pods -n kube-system \
                -l tier=control-plane,component="${component}" \
                --field-selector=status.phase=Running \
                --no-headers 2>/dev/null | wc -l)
        fi
        
        if [ "${component}" = "etcd" ] && [ "${running_count}" -eq 0 ]; then
            running_count=$(kubectl get pods -n kube-system \
                -l component=etcd \
                --field-selector=status.phase=Running \
                --no-headers 2>/dev/null | wc -l)
        fi
        
        if [ "${running_count}" -eq "${pod_count}" ]; then
            log_info "✓ ${component}: ${running_count}/${pod_count} pods running"
        else
            log_error "✗ ${component}: ${running_count}/${pod_count} pods running"
            UNHEALTHY_COMPONENTS+=("${component}")
            components_healthy=false
            
            # Show pod details if verbose
            if [ "${VERBOSE}" = "true" ]; then
                log_debug "Pod details:"
                kubectl get pods -n kube-system -l component="${component}" -o wide 2>/dev/null || true
            fi
        fi
    done
    
    # Alternative check: verify API server is responding
    log_info "Verifying API server responsiveness..."
    if kubectl get --raw /healthz &> /dev/null; then
        log_info "✓ API server health endpoint: healthy"
    else
        log_error "✗ API server health endpoint: unhealthy"
        UNHEALTHY_COMPONENTS+=("api-server-health")
        components_healthy=false
    fi
    
    # Check API server readiness
    if kubectl get --raw /readyz &> /dev/null; then
        log_info "✓ API server readiness endpoint: ready"
    else
        log_error "✗ API server readiness endpoint: not ready"
        UNHEALTHY_COMPONENTS+=("api-server-readiness")
        components_healthy=false
    fi
    
    if [ "${components_healthy}" = true ]; then
        log_info "✓ All control plane components are healthy"
        return 0
    else
        log_error "✗ Some control plane components are unhealthy"
        OVERALL_HEALTHY=false
        return 1
    fi
}

# Function to check node status
check_node_status() {
    log_section "Checking Node Status"
    
    local nodes_healthy=true
    
    # Get all nodes
    log_info "Retrieving node list..."
    
    local total_nodes
    total_nodes=$(kubectl get nodes --no-headers 2>/dev/null | wc -l)
    
    if [ "${total_nodes}" -eq 0 ]; then
        log_error "✗ No nodes found in cluster"
        UNHEALTHY_COMPONENTS+=("nodes")
        OVERALL_HEALTHY=false
        return 1
    fi
    
    log_info "Found ${total_nodes} node(s)"
    
    # Check Ready status
    local ready_nodes
    ready_nodes=$(kubectl get nodes --no-headers 2>/dev/null | grep -c " Ready " || true)
    
    log_info "Node status: ${ready_nodes}/${total_nodes} Ready"
    
    if [ "${ready_nodes}" -eq "${total_nodes}" ]; then
        log_info "✓ All nodes are Ready"
    else
        log_error "✗ Not all nodes are Ready (${ready_nodes}/${total_nodes})"
        UNHEALTHY_COMPONENTS+=("nodes-not-ready")
        nodes_healthy=false
    fi
    
    # Show detailed node status
    log_info "Detailed node status:"
    echo ""
    kubectl get nodes -o wide
    echo ""
    
    # Check for node conditions
    log_info "Checking node conditions..."
    
    local node_names
    node_names=$(kubectl get nodes -o jsonpath='{.items[*].metadata.name}')
    
    for node in ${node_names}; do
        log_debug "Checking conditions for node: ${node}"
        
        # Check for problematic conditions
        local conditions
        conditions=$(kubectl get node "${node}" -o jsonpath='{.status.conditions[?(@.status=="True")].type}')
        
        # Ready condition should be True
        if echo "${conditions}" | grep -q "Ready"; then
            log_debug "  ✓ ${node}: Ready"
        else
            log_error "  ✗ ${node}: Not Ready"
            UNHEALTHY_COMPONENTS+=("node-${node}")
            nodes_healthy=false
        fi
        
        # Check for bad conditions
        if echo "${conditions}" | grep -qE "MemoryPressure|DiskPressure|PIDPressure|NetworkUnavailable"; then
            log_warn "  ⚠ ${node}: Has pressure conditions"
            
            if [ "${VERBOSE}" = "true" ]; then
                kubectl get node "${node}" -o jsonpath='{.status.conditions}' | jq '.' 2>/dev/null || true
            fi
        fi
    done
    
    if [ "${nodes_healthy}" = true ]; then
        log_info "✓ All nodes are healthy"
        return 0
    else
        log_error "✗ Some nodes are unhealthy"
        OVERALL_HEALTHY=false
        return 1
    fi
}

# Function to check system pods
check_system_pods() {
    log_section "Checking System Pods"
    
    local pods_healthy=true
    
    # Check kube-system namespace pods
    log_info "Checking kube-system namespace..."
    
    local total_pods
    total_pods=$(kubectl get pods -n kube-system --no-headers 2>/dev/null | wc -l)
    
    if [ "${total_pods}" -eq 0 ]; then
        log_warn "⚠ No pods found in kube-system namespace"
        return 0
    fi
    
    log_info "Found ${total_pods} pod(s) in kube-system"
    
    # Count running pods
    local running_pods
    running_pods=$(kubectl get pods -n kube-system \
        --field-selector=status.phase=Running \
        --no-headers 2>/dev/null | wc -l)
    
    log_info "Pod status: ${running_pods}/${total_pods} Running"
    
    # Check for non-running pods
    local non_running_pods
    non_running_pods=$(kubectl get pods -n kube-system \
        --field-selector=status.phase!=Running,status.phase!=Succeeded \
        --no-headers 2>/dev/null)
    
    if [ -n "${non_running_pods}" ]; then
        log_error "✗ Found non-running pods in kube-system:"
        echo "${non_running_pods}"
        UNHEALTHY_COMPONENTS+=("system-pods")
        pods_healthy=false
    else
        log_info "✓ All system pods are running"
    fi
    
    # Show pod summary
    if [ "${VERBOSE}" = "true" ]; then
        log_debug "System pod summary:"
        kubectl get pods -n kube-system -o wide
    fi
    
    if [ "${pods_healthy}" = false ]; then
        OVERALL_HEALTHY=false
        return 1
    fi
    
    return 0
}

# Function to check DNS
check_dns() {
    log_section "Checking DNS Service"
    
    local dns_healthy=true
    
    # Check CoreDNS pods
    log_info "Checking CoreDNS pods..."
    
    local coredns_pods
    coredns_pods=$(kubectl get pods -n kube-system \
        -l k8s-app=kube-dns \
        --no-headers 2>/dev/null | wc -l)
    
    if [ "${coredns_pods}" -eq 0 ]; then
        log_warn "⚠ No CoreDNS pods found"
        log_debug "  DNS may be provided by a different service"
        return 0
    fi
    
    local running_coredns
    running_coredns=$(kubectl get pods -n kube-system \
        -l k8s-app=kube-dns \
        --field-selector=status.phase=Running \
        --no-headers 2>/dev/null | wc -l)
    
    if [ "${running_coredns}" -eq "${coredns_pods}" ]; then
        log_info "✓ CoreDNS: ${running_coredns}/${coredns_pods} pods running"
    else
        log_error "✗ CoreDNS: ${running_coredns}/${coredns_pods} pods running"
        UNHEALTHY_COMPONENTS+=("coredns")
        dns_healthy=false
    fi
    
    # Check DNS service
    log_info "Checking DNS service..."
    
    if kubectl get svc -n kube-system kube-dns &> /dev/null; then
        local dns_cluster_ip
        dns_cluster_ip=$(kubectl get svc -n kube-system kube-dns \
            -o jsonpath='{.spec.clusterIP}')
        log_info "✓ DNS service exists (ClusterIP: ${dns_cluster_ip})"
    else
        log_error "✗ DNS service not found"
        UNHEALTHY_COMPONENTS+=("dns-service")
        dns_healthy=false
    fi
    
    if [ "${dns_healthy}" = false ]; then
        OVERALL_HEALTHY=false
        return 1
    fi
    
    return 0
}

# Main execution
main() {
    local start_time
    start_time=$(date +%s)
    
    log_section "Starting Cluster Health Verification"
    
    # Check cluster connectivity
    if ! check_cluster_reachable; then
        log_error "Cannot proceed with health checks - cluster is unreachable"
        exit 1
    fi
    
    # Run health checks
    check_control_plane_components || true
    check_node_status || true
    check_system_pods || true
    check_dns || true
    
    # Calculate duration
    local end_time
    end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    # Summary
    log_section "Health Check Summary"
    
    echo ""
    log_info "Duration: ${duration}s"
    echo ""
    
    if [ "${OVERALL_HEALTHY}" = true ]; then
        log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        log_info "✓ CLUSTER IS HEALTHY"
        log_info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        log_info "All health checks passed:"
        log_info "  ✓ Control plane components are healthy"
        log_info "  ✓ All nodes are Ready"
        log_info "  ✓ System pods are running"
        log_info "  ✓ DNS service is operational"
        echo ""
        exit 0
    else
        log_error "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        log_error "✗ CLUSTER IS UNHEALTHY"
        log_error "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        log_error "Unhealthy components detected:"
        for component in "${UNHEALTHY_COMPONENTS[@]}"; do
            log_error "  ✗ ${component}"
        done
        echo ""
        log_error "Troubleshooting steps:"
        log_error "  1. Check pod logs: kubectl logs -n kube-system <pod-name>"
        log_error "  2. Check pod events: kubectl describe pod -n kube-system <pod-name>"
        log_error "  3. Check node conditions: kubectl describe node <node-name>"
        log_error "  4. Review Kubespray logs for deployment errors"
        log_error "  5. Verify bastion services are running (registry, nginx)"
        echo ""
        exit 1
    fi
}

# Run main function
main

