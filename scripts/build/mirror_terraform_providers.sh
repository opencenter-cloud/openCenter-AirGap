#!/bin/bash
# Mirror Terraform providers for offline deployment
# Executes terraform providers mirror for AMD64 and generates cross-platform lock file

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TERRAFORM_DIR="${PROJECT_ROOT}/assets/terraform"
MIRROR_DIR="${PROJECT_ROOT}/assets/terraform-mirror"
LOCK_FILE="${TERRAFORM_DIR}/.terraform.lock.hcl"

echo "==> Terraform Provider Mirror Script"
echo "Project root: ${PROJECT_ROOT}"
echo "Terraform config: ${TERRAFORM_DIR}"
echo "Mirror output: ${MIRROR_DIR}"

# Verify Terraform is installed
if ! command -v terraform &> /dev/null; then
    echo "ERROR: terraform command not found. Install Terraform 1.6.6 first."
    exit 1
fi

# Verify Terraform version
TERRAFORM_VERSION=$(terraform version | head -n1 | awk '{print $2}' | sed 's/v//')
echo "Terraform version: ${TERRAFORM_VERSION}"
if [[ "${TERRAFORM_VERSION}" != "1.6.6" ]]; then
    echo "WARNING: Expected Terraform 1.6.6, found ${TERRAFORM_VERSION}"
    echo "Continuing anyway. Provider mirroring should work across versions."
fi

# Verify versions.tf exists
if [[ ! -f "${TERRAFORM_DIR}/versions.tf" ]]; then
    echo "ERROR: ${TERRAFORM_DIR}/versions.tf not found"
    echo "Run task 3.1 first to create Terraform requirements file"
    exit 1
fi

# Create mirror directory
mkdir -p "${MIRROR_DIR}"

echo ""
echo "==> Step 1: Initialize Terraform to download providers"
cd "${TERRAFORM_DIR}"
terraform init

echo ""
echo "==> Step 2: Mirror providers for linux_amd64"
terraform providers mirror -platform=linux_amd64 "${MIRROR_DIR}"

echo ""
echo "==> Step 3: Generate cross-platform lock file"
# Remove existing lock file if present
rm -f "${LOCK_FILE}"

# Generate lock file with AMD64 hashes
terraform providers lock -platform=linux_amd64

echo ""
echo "==> Step 4: Verify lock file contains AMD64 hashes"
if [[ ! -f "${LOCK_FILE}" ]]; then
    echo "ERROR: Lock file not generated at ${LOCK_FILE}"
    exit 1
fi

# Verify lock file has provider entries with hashes
PROVIDER_COUNT=$(grep -c "^provider " "${LOCK_FILE}" || true)
if [[ ${PROVIDER_COUNT} -lt 4 ]]; then
    echo "ERROR: Lock file does not contain expected provider entries (found ${PROVIDER_COUNT}, expected 4)"
    exit 1
fi

echo "SUCCESS: Lock file generated with ${PROVIDER_COUNT} providers"

echo ""
echo "==> Step 5: Verify mirror directory structure"
EXPECTED_PROVIDERS=(
    "registry.terraform.io/hashicorp/local"
    "registry.terraform.io/hashicorp/null"
    "registry.terraform.io/hashicorp/tls"
    "registry.terraform.io/terraform-provider-openstack/openstack"
)

for provider in "${EXPECTED_PROVIDERS[@]}"; do
    if [[ ! -d "${MIRROR_DIR}/${provider}" ]]; then
        echo "WARNING: Provider ${provider} not found in mirror"
    else
        echo "  ✓ ${provider}"
    fi
done

echo ""
echo "==> Terraform provider mirror complete!"
echo "Mirror location: ${MIRROR_DIR}"
echo "Lock file: ${LOCK_FILE}"
echo ""
echo "Mirror size:"
du -sh "${MIRROR_DIR}"
