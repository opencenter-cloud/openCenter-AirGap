#!/bin/bash
set -euo pipefail

# Validation script for kubespray-offline bastion setup
# Verifies that setup-all.sh executed correctly

INSTALL_PATH="${INSTALL_PATH:-/opt/opencenter}"
OUTPUTS_DIR="${INSTALL_PATH}/outputs"
REGISTRY_PORT="${REGISTRY_PORT:-35000}"
NGINX_PORT="${NGINX_PORT:-80}"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counters
TESTS_PASSED=0
TESTS_FAILED=0

# Helper functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

test_pass() {
    echo -e "${GREEN}[PASS]${NC} $*"
    ((TESTS_PASSED++))
}

test_fail() {
    echo -e "${RED}[FAIL]${NC} $*"
    ((TESTS_FAILED++))
}

# Test 1: Verify containerd is installed
test_containerd_installed() {
    log_info "Testing: containerd installation"
    
    if command -v containerd &> /dev/null; then
        local version=$(containerd --version | awk '{print $3}')
        test_pass "containerd is installed (version: $version)"
        return 0
    else
        test_fail "containerd is not installed"
        return 1
    fi
}

# Test 2: Verify nerdctl is installed
test_nerdctl_installed() {
    log_info "Testing: nerdctl installation"
    
    if [ -f /usr/local/bin/nerdctl ]; then
        local version=$(/usr/local/bin/nerdctl --version | awk '{print $3}')
        test_pass "nerdctl is installed (version: $version)"
        return 0
    else
        test_fail "nerdctl is not installed at /usr/local/bin/nerdctl"
        return 1
    fi
}

# Test 3: Verify nginx container is running
test_nginx_running() {
    log_info "Testing: nginx container status"
    
    if sudo /usr/local/bin/nerdctl ps --format '{{.Names}}' | grep -q '^nginx$'; then
        test_pass "nginx container is running"
        return 0
    else
        test_fail "nginx container is not running"
        return 1
    fi
}

# Test 4: Verify nginx is accessible on port 80
test_nginx_accessible() {
    log_info "Testing: nginx accessibility on port ${NGINX_PORT}"
    
    if curl -sf "http://localhost:${NGINX_PORT}/files/" > /dev/null 2>&1; then
        test_pass "nginx is accessible at http://localhost:${NGINX_PORT}/files/"
        return 0
    else
        test_fail "nginx is not accessible at http://localhost:${NGINX_PORT}/files/"
        return 1
    fi
}

# Test 5: Verify nginx serves files directory
test_nginx_serves_files() {
    log_info "Testing: nginx serves files directory"
    
    local response=$(curl -s "http://localhost:${NGINX_PORT}/files/" | head -n 20)
    if echo "$response" | grep -q "Index of /files"; then
        test_pass "nginx serves files directory with directory listing"
        return 0
    else
        test_fail "nginx does not serve files directory correctly"
        return 1
    fi
}

# Test 6: Verify nginx serves debs directory
test_nginx_serves_debs() {
    log_info "Testing: nginx serves debs directory"
    
    if curl -sf "http://localhost:${NGINX_PORT}/debs/local/Packages.gz" > /dev/null 2>&1; then
        test_pass "nginx serves debs repository (Packages.gz found)"
        return 0
    else
        test_fail "nginx does not serve debs repository correctly"
        return 1
    fi
}

# Test 7: Verify nginx serves pypi directory
test_nginx_serves_pypi() {
    log_info "Testing: nginx serves pypi directory"
    
    if curl -sf "http://localhost:${NGINX_PORT}/pypi/" > /dev/null 2>&1; then
        test_pass "nginx serves pypi mirror"
        return 0
    else
        test_fail "nginx does not serve pypi mirror correctly"
        return 1
    fi
}

# Test 8: Verify apt sources configured
test_apt_sources_configured() {
    log_info "Testing: apt sources configuration"
    
    if [ -f /etc/apt/sources.list.d/offline.list ]; then
        if grep -q "http://localhost/debs/local/" /etc/apt/sources.list.d/offline.list; then
            test_pass "apt offline sources configured correctly"
            return 0
        else
            test_fail "apt offline sources file exists but content is incorrect"
            return 1
        fi
    else
        test_fail "apt offline sources file not found at /etc/apt/sources.list.d/offline.list"
        return 1
    fi
}

# Test 9: Verify pip configuration
test_pip_configured() {
    log_info "Testing: pip configuration"
    
    if [ -f ~/.config/pip/pip.conf ]; then
        if grep -q "http://localhost/pypi/" ~/.config/pip/pip.conf; then
            test_pass "pip configured to use local mirror"
            return 0
        else
            test_fail "pip.conf exists but does not point to local mirror"
            return 1
        fi
    else
        test_fail "pip.conf not found at ~/.config/pip/pip.conf"
        return 1
    fi
}

# Test 10: Verify Python venv created
test_python_venv_created() {
    log_info "Testing: Python virtual environment"
    
    if [ -d ~/.venv/kubespray ]; then
        if [ -f ~/.venv/kubespray/bin/python ]; then
            local py_version=$(~/.venv/kubespray/bin/python --version 2>&1)
            test_pass "Python venv created at ~/.venv/kubespray ($py_version)"
            return 0
        else
            test_fail "Python venv directory exists but python binary not found"
            return 1
        fi
    else
        test_fail "Python venv not created at ~/.venv/kubespray"
        return 1
    fi
}

# Test 11: Verify registry container is running
test_registry_running() {
    log_info "Testing: registry container status"
    
    if sudo /usr/local/bin/nerdctl ps --format '{{.Names}}' | grep -q '^registry$'; then
        test_pass "registry container is running"
        return 0
    else
        test_fail "registry container is not running"
        return 1
    fi
}

# Test 12: Verify registry is accessible
test_registry_accessible() {
    log_info "Testing: registry accessibility on port ${REGISTRY_PORT}"
    
    if curl -sf "http://localhost:${REGISTRY_PORT}/v2/_catalog" > /dev/null 2>&1; then
        test_pass "registry is accessible at http://localhost:${REGISTRY_PORT}/v2/_catalog"
        return 0
    else
        test_fail "registry is not accessible at http://localhost:${REGISTRY_PORT}/v2/_catalog"
        return 1
    fi
}

# Test 13: Verify images are in registry
test_images_in_registry() {
    log_info "Testing: images pushed to registry"
    
    local catalog=$(curl -s "http://localhost:${REGISTRY_PORT}/v2/_catalog")
    local repo_count=$(echo "$catalog" | jq -r '.repositories | length' 2>/dev/null || echo "0")
    
    if [ "$repo_count" -gt 0 ]; then
        test_pass "registry contains $repo_count repositories"
        log_info "Sample repositories: $(echo "$catalog" | jq -r '.repositories[:5] | join(", ")' 2>/dev/null || echo 'N/A')"
        return 0
    else
        test_fail "registry catalog is empty or inaccessible"
        return 1
    fi
}

# Test 14: Verify registry data directory
test_registry_data_directory() {
    log_info "Testing: registry data directory"
    
    if [ -d /var/lib/registry ]; then
        local size=$(du -sh /var/lib/registry 2>/dev/null | awk '{print $1}')
        test_pass "registry data directory exists at /var/lib/registry (size: $size)"
        return 0
    else
        test_fail "registry data directory not found at /var/lib/registry"
        return 1
    fi
}

# Test 15: Verify nginx and registry images loaded
test_base_images_loaded() {
    log_info "Testing: nginx and registry images loaded"
    
    local nginx_loaded=$(sudo /usr/local/bin/nerdctl images --format '{{.Repository}}:{{.Tag}}' | grep -c "nginx:" || echo "0")
    local registry_loaded=$(sudo /usr/local/bin/nerdctl images --format '{{.Repository}}:{{.Tag}}' | grep -c "registry:" || echo "0")
    
    if [ "$nginx_loaded" -gt 0 ] && [ "$registry_loaded" -gt 0 ]; then
        test_pass "nginx and registry images are loaded"
        return 0
    else
        test_fail "nginx or registry images not loaded (nginx: $nginx_loaded, registry: $registry_loaded)"
        return 1
    fi
}

# Main execution
main() {
    echo "=========================================="
    echo "Bastion Setup Validation"
    echo "=========================================="
    echo ""
    
    # Run all tests
    test_containerd_installed
    test_nerdctl_installed
    test_nginx_running
    test_nginx_accessible
    test_nginx_serves_files
    test_nginx_serves_debs
    test_nginx_serves_pypi
    test_apt_sources_configured
    test_pip_configured
    test_python_venv_created
    test_registry_running
    test_registry_accessible
    test_images_in_registry
    test_registry_data_directory
    test_base_images_loaded
    
    # Summary
    echo ""
    echo "=========================================="
    echo "Validation Summary"
    echo "=========================================="
    echo -e "Tests Passed: ${GREEN}${TESTS_PASSED}${NC}"
    echo -e "Tests Failed: ${RED}${TESTS_FAILED}${NC}"
    echo ""
    
    if [ $TESTS_FAILED -eq 0 ]; then
        log_info "All validation tests passed! Bastion setup is complete."
        exit 0
    else
        log_error "Some validation tests failed. Please review the output above."
        exit 1
    fi
}

# Run main function
main
