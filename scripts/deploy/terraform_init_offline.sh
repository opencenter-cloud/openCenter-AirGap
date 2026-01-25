#!/bin/bash
#
# Terraform Init Wrapper for Offline Operation
#
# This script initializes Terraform using a filesystem mirror without network access.
# It verifies that initialization succeeds using only local provider plugins.
#
# Requirements: 5.1
#
# Usage:
#   ./terraform_init_offline.sh --mirror-path <path> --terraform-dir <path> [--cache-dir <path>]
#
# Exit codes:
#   0 - Success
#   1 - Invalid arguments or missing dependencies
#   2 - Terraform init failed
#   3 - Network access detected during init

set -euo pipefail

# Default values
CACHE_DIR="/opt/opencenter/terraform-cache"
TERRAFORMRC_PATH=""
VERIFY_OFFLINE=true

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*" >&2
}

usage() {
    cat <<EOF
Usage: $0 --mirror-path <path> --terraform-dir <path> [options]

Initialize Terraform using filesystem mirror for offline operation.

Required arguments:
  --mirror-path PATH      Path to Terraform filesystem mirror
  --terraform-dir PATH    Path to Terraform configuration directory

Optional arguments:
  --cache-dir PATH        Plugin cache directory (default: /opt/opencenter/terraform-cache)
  --terraformrc PATH      Use existing .terraformrc file instead of generating
  --skip-offline-check    Skip network access verification
  -h, --help              Show this help message

Examples:
  # Basic usage
  $0 --mirror-path /opt/opencenter/terraform-mirror --terraform-dir /opt/opencenter/terraform

  # With custom cache directory
  $0 --mirror-path /opt/opencenter/terraform-mirror \\
     --terraform-dir /opt/opencenter/terraform \\
     --cache-dir /var/cache/terraform

EOF
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --mirror-path)
            MIRROR_PATH="$2"
            shift 2
            ;;
        --terraform-dir)
            TERRAFORM_DIR="$2"
            shift 2
            ;;
        --cache-dir)
            CACHE_DIR="$2"
            shift 2
            ;;
        --terraformrc)
            TERRAFORMRC_PATH="$2"
            shift 2
            ;;
        --skip-offline-check)
            VERIFY_OFFLINE=false
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            log_error "Unknown argument: $1"
            usage
            exit 1
            ;;
    esac
done

# Validate required arguments
if [[ -z "${MIRROR_PATH:-}" ]]; then
    log_error "Missing required argument: --mirror-path"
    usage
    exit 1
fi

if [[ -z "${TERRAFORM_DIR:-}" ]]; then
    log_error "Missing required argument: --terraform-dir"
    usage
    exit 1
fi

# Validate paths exist
if [[ ! -d "$MIRROR_PATH" ]]; then
    log_error "Mirror path does not exist: $MIRROR_PATH"
    exit 1
fi

if [[ ! -d "$TERRAFORM_DIR" ]]; then
    log_error "Terraform directory does not exist: $TERRAFORM_DIR"
    exit 1
fi

# Check for Terraform binary
if ! command -v terraform &> /dev/null; then
    log_error "Terraform binary not found in PATH"
    exit 1
fi

log_info "Terraform version: $(terraform version -json | jq -r '.terraform_version')"

# Generate or use existing .terraformrc
if [[ -n "$TERRAFORMRC_PATH" ]]; then
    if [[ ! -f "$TERRAFORMRC_PATH" ]]; then
        log_error "Specified .terraformrc does not exist: $TERRAFORMRC_PATH"
        exit 1
    fi
    log_info "Using existing .terraformrc: $TERRAFORMRC_PATH"
else
    TERRAFORMRC_PATH="/tmp/terraformrc-$$"
    log_info "Generating .terraformrc at: $TERRAFORMRC_PATH"
    
    # Use the generator script if available
    if [[ -f "scripts/build/generate_terraformrc.py" ]]; then
        python3 scripts/build/generate_terraformrc.py \
            --mirror-path "$MIRROR_PATH" \
            --cache-dir "$CACHE_DIR" \
            --output "$TERRAFORMRC_PATH"
    else
        # Fallback: generate inline
        cat > "$TERRAFORMRC_PATH" <<EOF
plugin_cache_dir = "$CACHE_DIR"

disable_checkpoint = true
disable_checkpoint_signature = true

provider_installation {
  filesystem_mirror {
    path    = "$MIRROR_PATH"
    include = ["*/*"]
  }

  # Disable direct installation from registry
  direct {
    exclude = ["*/*"]
  }
}
EOF
        log_info "Generated .terraformrc (inline)"
    fi
fi

# Create cache directory
mkdir -p "$CACHE_DIR"

# Export TF_CLI_CONFIG_FILE to use our .terraformrc
export TF_CLI_CONFIG_FILE="$TERRAFORMRC_PATH"

log_info "Terraform configuration:"
log_info "  Mirror path: $MIRROR_PATH"
log_info "  Cache directory: $CACHE_DIR"
log_info "  Terraform directory: $TERRAFORM_DIR"
log_info "  CLI config: $TF_CLI_CONFIG_FILE"

# Change to Terraform directory
cd "$TERRAFORM_DIR"

# Verify offline operation if requested
if [[ "$VERIFY_OFFLINE" == "true" ]]; then
    log_info "Verifying offline operation (monitoring network connections)..."
    
    # Start network monitoring in background
    NETSTAT_LOG="/tmp/terraform-init-netstat-$$.log"
    (
        while true; do
            # Check for established connections to external IPs (not localhost, not private ranges)
            netstat -tn 2>/dev/null | grep ESTABLISHED | \
                awk '{print $5}' | cut -d: -f1 | \
                grep -v '^127\.' | \
                grep -v '^10\.' | \
                grep -v '^172\.1[6-9]\.' | \
                grep -v '^172\.2[0-9]\.' | \
                grep -v '^172\.3[0-1]\.' | \
                grep -v '^192\.168\.' >> "$NETSTAT_LOG" 2>/dev/null || true
            sleep 0.5
        done
    ) &
    NETSTAT_PID=$!
fi

# Run terraform init
log_info "Running: terraform init"
INIT_OUTPUT=$(mktemp)

if terraform init -no-color > "$INIT_OUTPUT" 2>&1; then
    log_info "Terraform init succeeded"
    cat "$INIT_OUTPUT"
    INIT_SUCCESS=true
else
    log_error "Terraform init failed"
    cat "$INIT_OUTPUT" >&2
    INIT_SUCCESS=false
fi

# Stop network monitoring
if [[ "$VERIFY_OFFLINE" == "true" ]]; then
    kill $NETSTAT_PID 2>/dev/null || true
    wait $NETSTAT_PID 2>/dev/null || true
    
    # Check for external connections
    if [[ -f "$NETSTAT_LOG" ]] && [[ -s "$NETSTAT_LOG" ]]; then
        log_error "External network connections detected during terraform init:"
        sort -u "$NETSTAT_LOG" | while read -r ip; do
            log_error "  Connection to: $ip"
        done
        rm -f "$NETSTAT_LOG" "$INIT_OUTPUT"
        exit 3
    fi
    
    log_info "No external network connections detected"
    rm -f "$NETSTAT_LOG"
fi

rm -f "$INIT_OUTPUT"

# Clean up temporary .terraformrc if we generated it
if [[ "$TERRAFORMRC_PATH" == "/tmp/terraformrc-$$" ]]; then
    rm -f "$TERRAFORMRC_PATH"
fi

if [[ "$INIT_SUCCESS" == "true" ]]; then
    log_info "Terraform initialization completed successfully"
    exit 0
else
    log_error "Terraform initialization failed"
    exit 2
fi
