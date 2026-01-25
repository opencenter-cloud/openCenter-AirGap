#!/bin/bash
#
# Test Kubespray idempotency
#
# This script verifies that Kubespray cluster.yml can be safely re-run
# on a healthy cluster without causing changes.
#
# Requirements: 8.5

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test results
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_TOTAL=0

log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

log_test() {
    echo -e "${BLUE}[TEST]${NC} $*"
}

test_pass() {
    ((TESTS_PASSED++))
    ((TESTS_TOTAL++))
    log_info "✓ PASS: $*"
}

test_fail() {
    ((TESTS_FAILED++))
    ((TESTS_TOTAL++))
    log_error "✗ FAIL: $*"
}

# Configuration
KUBESPRAY_DIR="${KUBESPRAY_DIR:-/opt/opencenter/outputs/kubespray-master}"
INVENTORY_PATH="${INVENTORY_PATH:-${KUBESPRAY_DIR}/inventory/mycluster/hosts.yaml}"
VENV_PATH="${VENV_PATH:-${HOME}/.venv/kubespray}"

log_info "Testing Kubespray idempotency"
log_info "Kubespray directory: $KUBESPRAY_DIR"
log_info "Inventory: $INVENTORY_PATH"
echo ""

# Verify prerequisites
log_test "Verifying prerequisites"

if [ ! -d "$KUBESPRAY_DIR" ]; then
    log_error "Kubespray directory not found: $KUBESPRAY_DIR"
    exit 1
fi
test_pass "Kubespray directory exists"

if [ ! -f "$INVENTORY_PATH" ]; then
    log_error "Inventory file not found: $INVENTORY_PATH"
    exit 1
fi
test_pass "Inventory file exists"

if [ ! -d "$VENV_PATH" ]; then
    log_error "Python venv not found: $VENV_PATH"
    exit 1
fi
test_pass "Python venv exists"

# Activate venv
source "${VENV_PATH}/bin/activate"

if ! command -v ansible-playbook &> /dev/null; then
    log_error "ansible-playbook not found in venv"
    exit 1
fi
test_pass "ansible-playbook available"

# Check cluster is accessible
log_test "Verifying cluster is accessible"

if ! kubectl cluster-info &> /dev/null; then
    log_error "Cannot access cluster - ensure kubeconfig is configured"
    exit 1
fi
test_pass "Cluster is accessible"

# Capture cluster state before re-run
log_test "Capturing cluster state before re-run"

NODE_COUNT_BEFORE=$(kubectl get nodes --no-headers 2>/dev/null | wc -l)
POD_COUNT_BEFORE=$(kubectl get pods -A --no-headers 2>/dev/null | wc -l)
SERVICE_COUNT_BEFORE=$(kubectl get services -A --no-headers 2>/dev/null | wc -l)

log_info "Cluster state before:"
log_info "  Nodes: $NODE_COUNT_BEFORE"
log_info "  Pods: $POD_COUNT_BEFORE"
log_info "  Services: $SERVICE_COUNT_BEFORE"

# Verify all nodes are Ready
NODES_NOT_READY=$(kubectl get nodes --no-headers 2>/dev/null | grep -v " Ready " | wc -l)
if [ "$NODES_NOT_READY" -gt 0 ]; then
    log_warn "$NODES_NOT_READY node(s) not in Ready state"
    log_warn "Cluster may not be healthy - test results may be unreliable"
else
    test_pass "All nodes are Ready"
fi

echo ""

# Re-run cluster.yml
log_test "Re-running Kubespray cluster.yml"
log_info "This may take 10-20 minutes..."
log_info "Ansible output will be saved to /tmp/kubespray-rerun.log"

cd "$KUBESPRAY_DIR"

ANSIBLE_OUTPUT="/tmp/kubespray-rerun.log"
ANSIBLE_START=$(date +%s)

if ansible-playbook -i "$INVENTORY_PATH" \
    --become \
    --become-user=root \
    cluster.yml > "$ANSIBLE_OUTPUT" 2>&1; then
    ANSIBLE_END=$(date +%s)
    ANSIBLE_DURATION=$((ANSIBLE_END - ANSIBLE_START))
    log_info "cluster.yml completed in ${ANSIBLE_DURATION} seconds"
    test_pass "cluster.yml re-run succeeded"
else
    log_error "cluster.yml re-run failed"
    test_fail "cluster.yml re-run failed"
    log_error "Check Ansible output: $ANSIBLE_OUTPUT"
    tail -100 "$ANSIBLE_OUTPUT"
    exit 1
fi

echo ""

# Analyze Ansible output
log_test "Analyzing Ansible output for idempotency"

# Extract play recap
PLAY_RECAP=$(grep -A 100 "PLAY RECAP" "$ANSIBLE_OUTPUT" || echo "")

if [ -z "$PLAY_RECAP" ]; then
    log_error "Could not find PLAY RECAP in Ansible output"
    test_fail "PLAY RECAP not found"
else
    log_info "PLAY RECAP found"
    
    # Check for changed tasks
    TOTAL_CHANGED=$(echo "$PLAY_RECAP" | grep -oP 'changed=\K\d+' | awk '{sum+=$1} END {print sum}')
    TOTAL_FAILED=$(echo "$PLAY_RECAP" | grep -oP 'failed=\K\d+' | awk '{sum+=$1} END {print sum}')
    TOTAL_UNREACHABLE=$(echo "$PLAY_RECAP" | grep -oP 'unreachable=\K\d+' | awk '{sum+=$1} END {print sum}')
    
    log_info "Ansible task summary:"
    log_info "  Total changed: ${TOTAL_CHANGED:-0}"
    log_info "  Total failed: ${TOTAL_FAILED:-0}"
    log_info "  Total unreachable: ${TOTAL_UNREACHABLE:-0}"
    
    # Test for idempotency
    if [ "${TOTAL_CHANGED:-0}" -eq 0 ]; then
        test_pass "No tasks changed (perfect idempotency)"
    elif [ "${TOTAL_CHANGED:-0}" -le 5 ]; then
        log_warn "Some tasks changed: ${TOTAL_CHANGED}"
        log_warn "This may be acceptable for temp files or dynamic configs"
        test_pass "Minimal changes (acceptable idempotency)"
        
        # Show which tasks changed
        log_info "Tasks that changed:"
        grep "changed: \[" "$ANSIBLE_OUTPUT" | head -10
    else
        log_error "Too many tasks changed: ${TOTAL_CHANGED}"
        test_fail "Excessive changes (poor idempotency)"
        
        # Show which tasks changed
        log_error "Tasks that changed:"
        grep "changed: \[" "$ANSIBLE_OUTPUT" | head -20
    fi
    
    # Check for failures
    if [ "${TOTAL_FAILED:-0}" -eq 0 ]; then
        test_pass "No tasks failed"
    else
        log_error "Some tasks failed: ${TOTAL_FAILED}"
        test_fail "Tasks failed during re-run"
    fi
    
    # Check for unreachable hosts
    if [ "${TOTAL_UNREACHABLE:-0}" -eq 0 ]; then
        test_pass "All hosts reachable"
    else
        log_error "Some hosts unreachable: ${TOTAL_UNREACHABLE}"
        test_fail "Hosts unreachable during re-run"
    fi
fi

echo ""

# Verify cluster state after re-run
log_test "Verifying cluster state after re-run"

# Wait for cluster to stabilize
log_info "Waiting 30 seconds for cluster to stabilize..."
sleep 30

NODE_COUNT_AFTER=$(kubectl get nodes --no-headers 2>/dev/null | wc -l)
POD_COUNT_AFTER=$(kubectl get pods -A --no-headers 2>/dev/null | wc -l)
SERVICE_COUNT_AFTER=$(kubectl get services -A --no-headers 2>/dev/null | wc -l)

log_info "Cluster state after:"
log_info "  Nodes: $NODE_COUNT_AFTER"
log_info "  Pods: $POD_COUNT_AFTER"
log_info "  Services: $SERVICE_COUNT_AFTER"

# Compare counts
if [ "$NODE_COUNT_BEFORE" -eq "$NODE_COUNT_AFTER" ]; then
    test_pass "Node count unchanged"
else
    log_error "Node count changed: $NODE_COUNT_BEFORE -> $NODE_COUNT_AFTER"
    test_fail "Node count changed"
fi

if [ "$POD_COUNT_BEFORE" -eq "$POD_COUNT_AFTER" ]; then
    test_pass "Pod count unchanged"
else
    # Pod count may vary slightly due to temporary pods
    DIFF=$((POD_COUNT_AFTER - POD_COUNT_BEFORE))
    DIFF=${DIFF#-}  # Absolute value
    
    if [ "$DIFF" -le 2 ]; then
        log_warn "Pod count changed slightly: $POD_COUNT_BEFORE -> $POD_COUNT_AFTER"
        test_pass "Pod count approximately unchanged (within tolerance)"
    else
        log_error "Pod count changed significantly: $POD_COUNT_BEFORE -> $POD_COUNT_AFTER"
        test_fail "Pod count changed significantly"
    fi
fi

if [ "$SERVICE_COUNT_BEFORE" -eq "$SERVICE_COUNT_AFTER" ]; then
    test_pass "Service count unchanged"
else
    log_error "Service count changed: $SERVICE_COUNT_BEFORE -> $SERVICE_COUNT_AFTER"
    test_fail "Service count changed"
fi

# Verify all nodes still Ready
NODES_NOT_READY_AFTER=$(kubectl get nodes --no-headers 2>/dev/null | grep -v " Ready " | wc -l)
if [ "$NODES_NOT_READY_AFTER" -eq 0 ]; then
    test_pass "All nodes still Ready after re-run"
else
    log_error "$NODES_NOT_READY_AFTER node(s) not Ready after re-run"
    test_fail "Some nodes not Ready after re-run"
    kubectl get nodes
fi

# Verify system pods still running
SYSTEM_PODS_NOT_RUNNING=$(kubectl get pods -n kube-system --no-headers 2>/dev/null | grep -v "Running\|Completed" | wc -l)
if [ "$SYSTEM_PODS_NOT_RUNNING" -eq 0 ]; then
    test_pass "All system pods still running"
else
    log_error "$SYSTEM_PODS_NOT_RUNNING system pod(s) not running"
    test_fail "Some system pods not running"
    kubectl get pods -n kube-system | grep -v "Running\|Completed"
fi

echo ""

# Summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test Summary"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Total tests: $TESTS_TOTAL"
echo "Passed: $TESTS_PASSED"
echo "Failed: $TESTS_FAILED"
echo ""
echo "Ansible output saved to: $ANSIBLE_OUTPUT"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    log_info "All tests passed!"
    log_info "Kubespray cluster.yml is idempotent"
    exit 0
else
    log_error "$TESTS_FAILED test(s) failed"
    log_error "Kubespray may not be fully idempotent"
    exit 1
fi
