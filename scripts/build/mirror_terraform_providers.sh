#!/bin/bash
set -euo pipefail

# Mirror Terraform providers for offline use
#
# Downloads and mirrors Terraform providers to a local filesystem directory
# for air-gapped deployments. Includes OpenStack and common utility providers.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
MIRROR_DIR="${PROJECT_ROOT}/assets/terraform-mirror"
TERRAFORM_ASSETS="${PROJECT_ROOT}/assets/terraform"

# Source versions
if [ -f "${PROJECT_ROOT}/config/versions.env" ]; then
    # shellcheck disable=SC1091
    source "${PROJECT_ROOT}/config/versions.env"
fi

# Provider versions (with defaults)
TERRAFORM_VERSION="${TERRAFORM_VERSION:-1.6.6}"
OPENSTACK_PROVIDER_VERSION="${OPENSTACK_PROVIDER_VERSION:-1.54.1}"
LOCAL_PROVIDER_VERSION="${LOCAL_PROVIDER_VERSION:-2.4.1}"
NULL_PROVIDER_VERSION="${NULL_PROVIDER_VERSION:-3.2.2}"
RANDOM_PROVIDER_VERSION="${RANDOM_PROVIDER_VERSION:-3.6.0}"
TLS_PROVIDER_VERSION="${TLS_PROVIDER_VERSION:-4.0.5}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
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
    echo -e "${CYAN}[STEP]${NC} $*"
}

# Check prerequisites
check_prerequisites() {
    log_step "Checking prerequisites..."

    if ! command -v terraform &> /dev/null; then
        log_error "terraform not found. Install terraform ${TERRAFORM_VERSION}"
        exit 1
    fi

    local tf_version=$(terraform version -json | grep -o '"version":"[^"]*' | cut -d'"' -f4)
    log_info "Terraform version: ${tf_version}"

    if [ "${tf_version}" != "${TERRAFORM_VERSION}" ]; then
        log_warn "Terraform version mismatch: expected ${TERRAFORM_VERSION}, got ${tf_version}"
    fi
}

# Create temporary Terraform configuration
create_terraform_config() {
    log_step "Creating Terraform configuration..."

    local temp_dir=$(mktemp -d)
    echo "${temp_dir}"

    cat > "${temp_dir}/terraform-mirror.tf" <<EOF
terraform {
  required_version = ">= ${TERRAFORM_VERSION}"

  required_providers {
    openstack = {
      source  = "terraform-provider-openstack/openstack"
      version = "${OPENSTACK_PROVIDER_VERSION}"
    }
    local = {
      source  = "hashicorp/local"
      version = "${LOCAL_PROVIDER_VERSION}"
    }
    null = {
      source  = "hashicorp/null"
      version = "${NULL_PROVIDER_VERSION}"
    }
    random = {
      source  = "hashicorp/random"
      version = "${RANDOM_PROVIDER_VERSION}"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "${TLS_PROVIDER_VERSION}"
    }
  }
}

# Dummy resources to ensure providers are downloaded
resource "null_resource" "dummy" {}
EOF

    log_info "Configuration created at: ${temp_dir}/terraform-mirror.tf"
}

# Mirror providers
mirror_providers() {
    local temp_dir="$1"

    log_step "Mirroring Terraform providers..."
    log_info "Target directory: ${MIRROR_DIR}"

    mkdir -p "${MIRROR_DIR}"

    # Initialize to download providers
    log_info "Running terraform init..."
    if ! terraform -chdir="${temp_dir}" init -upgrade > /dev/null 2>&1; then
        log_error "terraform init failed"
        return 1
    fi

    # Mirror providers
    log_info "Running terraform providers mirror..."
    if terraform -chdir="${temp_dir}" providers mirror \
        -platform=linux_amd64 \
        "${MIRROR_DIR}"; then
        log_info "✓ Providers mirrored successfully"
    else
        log_error "terraform providers mirror failed"
        return 1
    fi

    # Generate lock file
    log_info "Generating provider lock file..."
    if terraform -chdir="${temp_dir}" providers lock \
        -platform=linux_amd64; then

        # Copy lock file to assets
        mkdir -p "${TERRAFORM_ASSETS}"
        cp "${temp_dir}/.terraform.lock.hcl" "${TERRAFORM_ASSETS}/.terraform.lock.hcl"
        log_info "✓ Lock file: ${TERRAFORM_ASSETS}/.terraform.lock.hcl"
    else
        log_warn "Failed to generate lock file"
    fi
}

# Verify mirrored providers
verify_providers() {
    log_step "Verifying mirrored providers..."

    local required_providers=(
        "terraform-provider-openstack/openstack"
        "hashicorp/local"
        "hashicorp/null"
        "hashicorp/random"
        "hashicorp/tls"
    )

    local missing=()

    for provider in "${required_providers[@]}"; do
        local provider_path="${MIRROR_DIR}/registry.terraform.io/${provider}"

        if [ -d "${provider_path}" ]; then
            local size=$(du -sh "${provider_path}" | cut -f1)
            log_info "  ✓ ${provider} (${size})"
        else
            log_error "  ✗ ${provider} missing"
            missing+=("${provider}")
        fi
    done

    if [ ${#missing[@]} -gt 0 ]; then
        log_error "Missing providers: ${missing[*]}"
        return 1
    fi

    log_info "All providers verified"
}

# Generate .terraformrc for offline use
generate_terraformrc() {
    log_step "Generating .terraformrc for offline use..."

    local terraformrc="${TERRAFORM_ASSETS}/.terraformrc"

    cat > "${terraformrc}" <<EOF
# Terraform configuration for air-gapped deployment
# Copy to ~/.terraformrc or /etc/terraform/terraformrc on bastion

plugin_cache_dir   = "/opt/opencenter/terraform-cache"
disable_checkpoint = true

provider_installation {
  filesystem_mirror {
    path    = "/opt/opencenter/terraform-mirror"
    include = ["*/*"]
  }
  direct {
    exclude = ["*/*"]
  }
}
EOF

    log_info "✓ Generated: ${terraformrc}"
}

# Main execution
main() {
    log_info "Mirroring Terraform providers for air-gap deployment"
    log_info "Target architecture: linux_amd64"
    echo ""

    check_prerequisites

    local temp_dir=$(create_terraform_config)

    # Ensure cleanup on exit
    trap "rm -rf ${temp_dir}" EXIT

    mirror_providers "${temp_dir}"
    verify_providers
    generate_terraformrc

    echo ""
    log_info "Provider mirror complete"
    log_info "Mirror directory: ${MIRROR_DIR}"
    log_info "Total size: $(du -sh ${MIRROR_DIR} | cut -f1)"

    echo ""
    log_info "Next steps:"
    log_info "  1. Verify providers: ls -R ${MIRROR_DIR}"
    log_info "  2. Build Zarf package: python3 scripts/build/build.py"
    log_info "  3. On bastion, Terraform will use filesystem mirror automatically"
}

main "$@"
