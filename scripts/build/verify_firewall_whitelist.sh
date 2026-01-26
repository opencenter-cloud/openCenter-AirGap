#!/bin/bash
# Verify Firewall Whitelist Connectivity
#
# Tests connectivity to all required URLs for openCenter AirGap build.
# Run this script in Zone A (Factory) to verify firewall configuration.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
WHITELIST_FILE="${PROJECT_ROOT}/config/firewall-whitelist.txt"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Counters
TOTAL=0
SUCCESS=0
FAILED=0
SKIPPED=0

log_success() {
    echo -e "${GREEN}✓${NC} $*"
}

log_fail() {
    echo -e "${RED}✗${NC} $*"
}

log_skip() {
    echo -e "${YELLOW}⊘${NC} $*"
}

log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

# Test URL connectivity
test_url() {
    local url="$1"
    local timeout=5
    
    TOTAL=$((TOTAL + 1))
    
    # Try HTTPS first
    if curl -s -o /dev/null -w "%{http_code}" --connect-timeout "$timeout" "https://${url}" 2>/dev/null | grep -q "200\|301\|302\|403"; then
        log_success "$url (HTTPS)"
        SUCCESS=$((SUCCESS + 1))
        return 0
    fi
    
    # Try HTTP as fallback
    if curl -s -o /dev/null -w "%{http_code}" --connect-timeout "$timeout" "http://${url}" 2>/dev/null | grep -q "200\|301\|302"; then
        log_success "$url (HTTP)"
        SUCCESS=$((SUCCESS + 1))
        return 0
    fi
    
    # Check if DNS resolves
    if host "$url" >/dev/null 2>&1; then
        log_fail "$url (DNS OK, connection failed)"
    else
        log_fail "$url (DNS resolution failed)"
    fi
    
    FAILED=$((FAILED + 1))
    return 1
}

# Test DNS resolution
test_dns() {
    log_info "Testing DNS resolution..."
    
    if command -v host >/dev/null 2>&1; then
        if host google.com >/dev/null 2>&1; then
            log_success "DNS resolution working"
            return 0
        else
            log_fail "DNS resolution not working"
            return 1
        fi
    else
        log_skip "DNS test (host command not found)"
        return 0
    fi
}

# Test proxy configuration
test_proxy() {
    log_info "Checking proxy configuration..."
    
    if [ -n "${HTTP_PROXY:-}" ]; then
        log_info "HTTP_PROXY: $HTTP_PROXY"
    fi
    
    if [ -n "${HTTPS_PROXY:-}" ]; then
        log_info "HTTPS_PROXY: $HTTPS_PROXY"
    fi
    
    if [ -n "${NO_PROXY:-}" ]; then
        log_info "NO_PROXY: $NO_PROXY"
    fi
    
    if [ -z "${HTTP_PROXY:-}" ] && [ -z "${HTTPS_PROXY:-}" ]; then
        log_info "No proxy configured (direct connection)"
    fi
}

# Main
main() {
    echo "=========================================="
    echo "Firewall Whitelist Connectivity Test"
    echo "=========================================="
    echo ""
    
    # Check prerequisites
    if ! command -v curl >/dev/null 2>&1; then
        log_fail "curl not found. Please install curl."
        exit 1
    fi
    
    # Test DNS
    test_dns
    echo ""
    
    # Test proxy
    test_proxy
    echo ""
    
    # Load whitelist
    if [ ! -f "$WHITELIST_FILE" ]; then
        log_fail "Whitelist file not found: $WHITELIST_FILE"
        exit 1
    fi
    
    log_info "Testing URLs from: $WHITELIST_FILE"
    echo ""
    
    # Test each URL
    while IFS= read -r line; do
        # Skip comments and empty lines
        [[ "$line" =~ ^#.*$ ]] && continue
        [[ -z "$line" ]] && continue
        
        test_url "$line"
    done < "$WHITELIST_FILE"
    
    echo ""
    echo "=========================================="
    echo "Test Summary"
    echo "=========================================="
    echo "Total URLs tested: $TOTAL"
    echo -e "${GREEN}Successful: $SUCCESS${NC}"
    echo -e "${RED}Failed: $FAILED${NC}"
    
    if [ $FAILED -eq 0 ]; then
        echo ""
        log_success "All URLs accessible!"
        echo ""
        log_info "Firewall whitelist is correctly configured."
        log_info "You can proceed with the build process."
        exit 0
    else
        echo ""
        log_fail "Some URLs are not accessible!"
        echo ""
        log_info "Failed URLs need to be whitelisted in your firewall."
        log_info "Please review the firewall configuration and try again."
        echo ""
        log_info "Documentation: docs/reference/firewall-whitelist.md"
        exit 1
    fi
}

# Run main
main
