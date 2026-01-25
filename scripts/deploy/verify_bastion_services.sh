#!/bin/bash
set -euo pipefail

# Quick verification script for bastion services
# Checks nginx, registry, and Python venv are operational

REGISTRY_PORT="${REGISTRY_PORT:-35000}"
NGINX_PORT="${NGINX_PORT:-80}"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*"
}

# Check nginx accessibility
check_nginx() {
    log_info "Checking nginx on port ${NGINX_PORT}..."
    
    if curl -sf "http://localhost:${NGINX_PORT}/files/" > /dev/null 2>&1; then
        log_success "nginx is accessible at http://localhost:${NGINX_PORT}/files/"
        return 0
    else
        log_error "nginx is not accessible at http://localhost:${NGINX_PORT}/files/"
        return 1
    fi
}

# Check registry accessibility
check_registry() {
    log_info "Checking registry on port ${REGISTRY_PORT}..."
    
    if curl -sf "http://localhost:${REGISTRY_PORT}/v2/_catalog" > /dev/null 2>&1; then
        log_success "registry is accessible at http://localhost:${REGISTRY_PORT}/v2/_catalog"
        
        # Show catalog summary
        local catalog=$(curl -s "http://localhost:${REGISTRY_PORT}/v2/_catalog")
        local repo_count=$(echo "$catalog" | jq -r '.repositories | length' 2>/dev/null || echo "unknown")
        log_info "Registry contains $repo_count repositories"
        
        return 0
    else
        log_error "registry is not accessible at http://localhost:${REGISTRY_PORT}/v2/_catalog"
        return 1
    fi
}

# Check Python venv
check_python_venv() {
    log_info "Checking Python virtual environment..."
    
    if [ -d ~/.venv/kubespray ]; then
        if [ -f ~/.venv/kubespray/bin/python ]; then
            local py_version=$(~/.venv/kubespray/bin/python --version 2>&1)
            log_success "Python venv exists at ~/.venv/kubespray ($py_version)"
            return 0
        else
            log_error "Python venv directory exists but python binary not found"
            return 1
        fi
    else
        log_error "Python venv not found at ~/.venv/kubespray"
        return 1
    fi
}

# Verify images in registry
verify_registry_images() {
    log_info "Verifying images in registry..."
    
    local catalog=$(curl -s "http://localhost:${REGISTRY_PORT}/v2/_catalog" 2>/dev/null)
    
    if [ -z "$catalog" ]; then
        log_error "Failed to retrieve registry catalog"
        return 1
    fi
    
    # Check if jq is available
    if ! command -v jq &> /dev/null; then
        log_info "jq not available, showing raw catalog:"
        echo "$catalog"
        return 0
    fi
    
    # Parse and display repositories
    local repos=$(echo "$catalog" | jq -r '.repositories[]' 2>/dev/null)
    
    if [ -z "$repos" ]; then
        log_error "No repositories found in registry"
        return 1
    fi
    
    log_success "Registry repositories:"
    echo "$repos" | head -n 10
    
    local total=$(echo "$repos" | wc -l)
    if [ "$total" -gt 10 ]; then
        log_info "... and $((total - 10)) more repositories"
    fi
    
    return 0
}

# Main execution
main() {
    echo "=========================================="
    echo "Bastion Services Verification"
    echo "=========================================="
    echo ""
    
    local exit_code=0
    
    # Run checks
    check_nginx || exit_code=1
    echo ""
    
    check_registry || exit_code=1
    echo ""
    
    check_python_venv || exit_code=1
    echo ""
    
    verify_registry_images || exit_code=1
    echo ""
    
    # Summary
    echo "=========================================="
    if [ $exit_code -eq 0 ]; then
        log_success "All bastion services are operational"
    else
        log_error "Some bastion services are not operational"
    fi
    echo "=========================================="
    
    exit $exit_code
}

# Run main
main
