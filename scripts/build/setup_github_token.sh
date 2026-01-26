#!/bin/bash
set -euo pipefail

# Interactive script to help set up GitHub token for openCenter asset collection
# GitHub API does not allow programmatic token creation without existing auth,
# so this script guides the user through manual creation and validates the token.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

print_header() {
    echo ""
    echo "=========================================="
    echo "  GitHub Token Setup for openCenter"
    echo "=========================================="
    echo ""
}

print_instructions() {
    cat <<'EOF'
GitHub Personal Access Tokens (PAT) must be created manually through the GitHub web interface.
This script will guide you through the process and validate your token.

Required Token Scopes:
  • read:packages  - Read container images from GitHub Container Registry
  • repo           - Access private repositories (if needed)

Token Types:
  1. Classic Token (recommended for simplicity)
  2. Fine-grained Token (recommended for security)

EOF
}

open_browser() {
    local url="$1"
    
    if command -v open &> /dev/null; then
        # macOS
        open "${url}"
    elif command -v xdg-open &> /dev/null; then
        # Linux
        xdg-open "${url}"
    elif command -v wslview &> /dev/null; then
        # WSL
        wslview "${url}"
    else
        log_warn "Could not open browser automatically"
        echo "Please open this URL manually: ${url}"
    fi
}

create_classic_token() {
    log_step "Creating Classic Token"
    echo ""
    echo "1. Opening GitHub token creation page..."
    sleep 1
    
    open_browser "https://github.com/settings/tokens/new"
    
    echo ""
    echo "2. Configure your token:"
    echo "   • Note: openCenter-airgap-build"
    echo "   • Expiration: 90 days (recommended)"
    echo "   • Select scopes:"
    echo "     ☑ read:packages"
    echo "     ☑ repo (if accessing private repos)"
    echo ""
    echo "3. Click 'Generate token' at the bottom"
    echo "4. Copy the token (starts with 'ghp_')"
    echo ""
}

create_finegrained_token() {
    log_step "Creating Fine-grained Token"
    echo ""
    echo "1. Opening GitHub fine-grained token creation page..."
    sleep 1
    
    open_browser "https://github.com/settings/tokens?type=beta"
    
    echo ""
    echo "2. Click 'Generate new token'"
    echo ""
    echo "3. Configure your token:"
    echo "   • Token name: openCenter-airgap-build"
    echo "   • Expiration: 90 days"
    echo "   • Repository access: All repositories (or select specific)"
    echo ""
    echo "4. Set Permissions:"
    echo "   • Contents: Read-only"
    echo "   • Packages: Read-only"
    echo ""
    echo "5. Click 'Generate token'"
    echo "6. Copy the token (starts with 'github_pat_')"
    echo ""
}

prompt_token_type() {
    echo "Select token type:"
    echo "  1) Classic Token (simpler, broader access)"
    echo "  2) Fine-grained Token (more secure, granular)"
    echo ""
    read -p "Enter choice [1-2]: " choice
    
    case $choice in
        1)
            create_classic_token
            ;;
        2)
            create_finegrained_token
            ;;
        *)
            log_error "Invalid choice"
            exit 1
            ;;
    esac
}

read_token() {
    echo ""
    read -sp "Paste your GitHub token: " token
    echo ""
    
    if [ -z "${token}" ]; then
        log_error "No token provided"
        exit 1
    fi
    
    # Validate token format
    if [[ ! "${token}" =~ ^(ghp_|github_pat_) ]]; then
        log_warn "Token doesn't match expected format (ghp_* or github_pat_*)"
        read -p "Continue anyway? [y/N]: " confirm
        if [[ ! "${confirm}" =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    
    echo "${token}"
}

validate_token() {
    local token="$1"
    
    log_step "Validating token..."
    
    # Test authentication
    local response
    response=$(curl -s -w "\n%{http_code}" \
        -H "Authorization: Bearer ${token}" \
        -H "Accept: application/vnd.github+json" \
        https://api.github.com/user)
    
    local http_code=$(echo "${response}" | tail -n1)
    local body=$(echo "${response}" | head -n-1)
    
    if [ "${http_code}" != "200" ]; then
        log_error "Token validation failed (HTTP ${http_code})"
        echo "${body}" | jq -r '.message' 2>/dev/null || echo "${body}"
        return 1
    fi
    
    local username=$(echo "${body}" | jq -r '.login')
    log_info "Authenticated as: ${username}"
    
    # Check scopes (Classic tokens only)
    local scopes_header=$(curl -sI \
        -H "Authorization: Bearer ${token}" \
        https://api.github.com/user | grep -i "x-oauth-scopes:" || true)
    
    if [ -n "${scopes_header}" ]; then
        local scopes=$(echo "${scopes_header}" | cut -d: -f2- | tr -d ' \r\n')
        log_info "Token scopes: ${scopes}"
        
        if [[ ! "${scopes}" =~ read:packages ]]; then
            log_warn "Token missing 'read:packages' scope"
            log_warn "You may not be able to pull container images"
        fi
    else
        log_info "Fine-grained token detected (scopes not shown in header)"
    fi
    
    # Test package access
    log_step "Testing package access..."
    local packages_response
    packages_response=$(curl -s -w "\n%{http_code}" \
        -H "Authorization: Bearer ${token}" \
        -H "Accept: application/vnd.github+json" \
        https://api.github.com/orgs/opencenter-cloud/packages?package_type=container)
    
    local packages_http_code=$(echo "${packages_response}" | tail -n1)
    
    if [ "${packages_http_code}" = "200" ]; then
        local package_count=$(echo "${packages_response}" | head -n-1 | jq '. | length')
        log_info "Package access: OK (${package_count} packages found)"
    elif [ "${packages_http_code}" = "404" ]; then
        log_warn "Organization 'opencenter-cloud' not found or no packages"
    else
        log_warn "Package access test failed (HTTP ${packages_http_code})"
    fi
    
    # Test GHCR login
    log_step "Testing GitHub Container Registry login..."
    
    local container_runtime
    if command -v podman &> /dev/null; then
        container_runtime="podman"
    elif command -v docker &> /dev/null; then
        container_runtime="docker"
    else
        log_warn "Neither podman nor docker found, skipping GHCR login test"
        return 0
    fi
    
    if echo "${token}" | ${container_runtime} login ghcr.io -u "${username}" --password-stdin &>/dev/null; then
        log_info "GHCR login: OK"
        ${container_runtime} logout ghcr.io &>/dev/null
    else
        log_warn "GHCR login failed"
    fi
    
    return 0
}

save_token() {
    local token="$1"
    
    echo ""
    echo "How would you like to save the token?"
    echo "  1) Environment variable (current session only)"
    echo "  2) Shell profile (~/.bashrc or ~/.zshrc)"
    echo "  3) Project .env file (gitignored)"
    echo "  4) Don't save (manual export required)"
    echo ""
    read -p "Enter choice [1-4]: " choice
    
    case $choice in
        1)
            export GITHUB_TOKEN="${token}"
            log_info "Token exported to GITHUB_TOKEN"
            echo ""
            echo "Run this in your current shell:"
            echo "  export GITHUB_TOKEN='${token}'"
            ;;
        2)
            local shell_profile
            if [ -n "${ZSH_VERSION:-}" ]; then
                shell_profile="${HOME}/.zshrc"
            else
                shell_profile="${HOME}/.bashrc"
            fi
            
            echo "" >> "${shell_profile}"
            echo "# GitHub token for openCenter builds" >> "${shell_profile}"
            echo "export GITHUB_TOKEN='${token}'" >> "${shell_profile}"
            
            log_info "Token added to ${shell_profile}"
            echo ""
            echo "Reload your shell:"
            echo "  source ${shell_profile}"
            ;;
        3)
            local env_file="${PROJECT_ROOT}/.env"
            echo "# GitHub token for openCenter builds" > "${env_file}"
            echo "export GITHUB_TOKEN='${token}'" >> "${env_file}"
            chmod 600 "${env_file}"
            
            # Ensure .env is in .gitignore
            local gitignore="${PROJECT_ROOT}/.gitignore"
            if [ -f "${gitignore}" ]; then
                if ! grep -q "^\.env$" "${gitignore}"; then
                    echo ".env" >> "${gitignore}"
                fi
            else
                echo ".env" > "${gitignore}"
            fi
            
            log_info "Token saved to ${env_file}"
            echo ""
            echo "Load token before building:"
            echo "  source .env"
            ;;
        4)
            log_info "Token not saved"
            echo ""
            echo "Export manually before building:"
            echo "  export GITHUB_TOKEN='${token}'"
            ;;
        *)
            log_error "Invalid choice"
            exit 1
            ;;
    esac
}

show_next_steps() {
    echo ""
    echo "=========================================="
    echo "  Setup Complete!"
    echo "=========================================="
    echo ""
    echo "Next steps:"
    echo ""
    echo "1. Verify token is set:"
    echo "   echo \$GITHUB_TOKEN"
    echo ""
    echo "2. Collect openCenter assets:"
    echo "   ./scripts/build/collect_opencenter_assets.sh"
    echo ""
    echo "3. Build air-gap package:"
    echo "   ./scripts/build/build.sh"
    echo ""
    echo "Documentation:"
    echo "  • Token reference: docs/reference/configuration/github-token.md"
    echo "  • Asset collection: docs/how-to/build/add-opencenter-assets.md"
    echo ""
}

check_existing_token() {
    if [ -n "${GITHUB_TOKEN:-}" ]; then
        log_info "GITHUB_TOKEN already set in environment"
        echo ""
        read -p "Validate existing token? [Y/n]: " validate
        
        if [[ ! "${validate}" =~ ^[Nn]$ ]]; then
            if validate_token "${GITHUB_TOKEN}"; then
                log_info "Existing token is valid"
                echo ""
                read -p "Continue with existing token? [Y/n]: " continue
                if [[ ! "${continue}" =~ ^[Nn]$ ]]; then
                    show_next_steps
                    exit 0
                fi
            else
                log_warn "Existing token is invalid"
            fi
        fi
        
        echo ""
        read -p "Create new token? [Y/n]: " create_new
        if [[ "${create_new}" =~ ^[Nn]$ ]]; then
            exit 0
        fi
    fi
}

main() {
    print_header
    print_instructions
    
    check_existing_token
    
    prompt_token_type
    
    token=$(read_token)
    
    if validate_token "${token}"; then
        log_info "Token validation successful!"
        save_token "${token}"
        show_next_steps
    else
        log_error "Token validation failed"
        echo ""
        echo "Please verify:"
        echo "  • Token was copied correctly"
        echo "  • Token has required scopes (read:packages)"
        echo "  • Token has not expired"
        exit 1
    fi
}

main "$@"
