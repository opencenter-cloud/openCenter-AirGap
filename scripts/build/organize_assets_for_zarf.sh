#!/bin/bash
# organize_assets_for_zarf.sh
# Organizes kubespray-offline outputs into Zarf-compatible asset structure
# Requirements: 2.3

set -euo pipefail

# Determine project root (script is in scripts/build/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Source directories
KUBESPRAY_OFFLINE_DIR="${PROJECT_ROOT}/build/kubespray-offline/outputs"

# Target directories
ZARF_ASSETS_DIR="${PROJECT_ROOT}/assets"

# Logging
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"
}

error() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $*" >&2
}

# Verify source directory exists
if [ ! -d "${KUBESPRAY_OFFLINE_DIR}" ]; then
    error "kubespray-offline outputs directory not found: ${KUBESPRAY_OFFLINE_DIR}"
    error "Run kubespray-offline download-all.sh first"
    exit 1
fi

log "Starting asset organization for Zarf packaging"
log "Source: ${KUBESPRAY_OFFLINE_DIR}"
log "Target: ${ZARF_ASSETS_DIR}"

# Create target directory structure
log "Creating Zarf asset directory structure..."
mkdir -p "${ZARF_ASSETS_DIR}"/{k8s-binaries,python-wheels,repos/apt,target-scripts,kubespray,playbook,terraform-mirror}

# 1. Copy Kubernetes binaries
log "Step 1/7: Copying Kubernetes binaries..."
if [ -d "${KUBESPRAY_OFFLINE_DIR}/files" ]; then
    cp -r "${KUBESPRAY_OFFLINE_DIR}/files/"* "${ZARF_ASSETS_DIR}/k8s-binaries/"
    log "  Copied K8s binaries from outputs/files/"
else
    error "outputs/files/ directory not found"
    exit 1
fi

# 2. Copy Python wheels
log "Step 2/7: Copying Python wheels..."
if [ -d "${KUBESPRAY_OFFLINE_DIR}/pypi" ]; then
    cp -r "${KUBESPRAY_OFFLINE_DIR}/pypi/"* "${ZARF_ASSETS_DIR}/python-wheels/"
    log "  Copied Python wheels from outputs/pypi/"
else
    error "outputs/pypi/ directory not found"
    exit 1
fi

# 3. Copy apt repository
log "Step 3/7: Copying apt repository..."
if [ -d "${KUBESPRAY_OFFLINE_DIR}/debs" ]; then
    cp -r "${KUBESPRAY_OFFLINE_DIR}/debs/"* "${ZARF_ASSETS_DIR}/repos/apt/"
    log "  Copied apt repository from outputs/debs/"
else
    error "outputs/debs/ directory not found"
    exit 1
fi

# 4. Load container images into podman (optional - Zarf will handle images)
log "Step 4/7: Preparing container images..."
if [ -d "${KUBESPRAY_OFFLINE_DIR}/images" ]; then
    image_count=$(find "${KUBESPRAY_OFFLINE_DIR}/images" -name "*.tar.gz" -type f | wc -l)
    log "  Found ${image_count} container images in outputs/images/"
    log "  Note: Images will be packaged by Zarf directly from tar.gz files"
    log "  Skipping podman load (not required for Zarf packaging)"
else
    error "outputs/images/ directory not found"
    exit 1
fi

# 5. Extract Kubespray tarball
log "Step 5/7: Extracting Kubespray tarball..."
kubespray_tarball="${KUBESPRAY_OFFLINE_DIR}/files/kubespray-master.tar.gz"
if [ -f "${kubespray_tarball}" ]; then
    tar xzf "${kubespray_tarball}" -C "${ZARF_ASSETS_DIR}/kubespray/"
    log "  Extracted kubespray-master.tar.gz to assets/kubespray/"
else
    error "Kubespray tarball not found: ${kubespray_tarball}"
    exit 1
fi

# 6. Copy target scripts
log "Step 6/7: Copying target scripts..."
# Target scripts are in outputs/ root, not in a subdirectory
for script in setup-all.sh setup-container.sh start-nginx.sh start-registry.sh \
              load-push-all-images.sh extract-kubespray.sh setup-offline.sh \
              setup-py.sh install-containerd.sh config.sh config.toml \
              containerd.service nginx-default.conf pyver.sh venv.sh; do
    if [ -f "${KUBESPRAY_OFFLINE_DIR}/${script}" ]; then
        cp "${KUBESPRAY_OFFLINE_DIR}/${script}" "${ZARF_ASSETS_DIR}/target-scripts/"
    fi
done

# Also copy patches directory if it exists
if [ -d "${KUBESPRAY_OFFLINE_DIR}/patches" ]; then
    cp -r "${KUBESPRAY_OFFLINE_DIR}/patches" "${ZARF_ASSETS_DIR}/target-scripts/"
fi

log "  Copied target scripts from outputs/"

# 7. Copy playbook
log "Step 7/7: Copying offline-repo.yml playbook..."
if [ -d "${KUBESPRAY_OFFLINE_DIR}/playbook" ]; then
    cp -r "${KUBESPRAY_OFFLINE_DIR}/playbook/"* "${ZARF_ASSETS_DIR}/playbook/"
    log "  Copied playbook from outputs/playbook/"
else
    error "outputs/playbook/ directory not found"
    exit 1
fi

# 8. Copy Terraform providers (if OpenStack mode enabled)
log "Step 8/8: Copying Terraform providers (optional)..."
TERRAFORM_MIRROR_SRC="${PROJECT_ROOT}/assets/terraform-mirror"
if [ -d "${TERRAFORM_MIRROR_SRC}" ] && [ "$(ls -A ${TERRAFORM_MIRROR_SRC})" ]; then
    # Terraform mirror already exists from task 3.2
    log "  Terraform provider mirror already organized at assets/terraform-mirror/"
    log "  Skipping copy (already in place)"
else
    log "  No Terraform providers found (bare-metal mode or not yet collected)"
    log "  Skipping Terraform provider organization"
fi

log "Asset organization complete!"
log "Assets organized at: ${ZARF_ASSETS_DIR}"
log ""
log "Directory structure:"
log "  ${ZARF_ASSETS_DIR}/k8s-binaries/    - Kubernetes binaries and components"
log "  ${ZARF_ASSETS_DIR}/python-wheels/   - Python packages (PyPI mirror)"
log "  ${ZARF_ASSETS_DIR}/repos/apt/       - Ubuntu package repository"
log "  ${ZARF_ASSETS_DIR}/target-scripts/  - Deployment scripts for bastion"
log "  ${ZARF_ASSETS_DIR}/kubespray/       - Kubespray source"
log "  ${ZARF_ASSETS_DIR}/playbook/        - Ansible playbooks"
log "  ${ZARF_ASSETS_DIR}/terraform-mirror/ - Terraform providers (if OpenStack)"
log ""
log "Container images: ${image_count} tar.gz files ready for Zarf packaging"
