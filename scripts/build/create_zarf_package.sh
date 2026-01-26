#!/bin/bash
# create_zarf_package.sh
# Creates Zarf package from organized assets
# Requirements: 2.1, 2.8, 2.9

set -euo pipefail

# Determine project root (script is in scripts/build/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Configuration
ZARF_YAML="${PROJECT_ROOT}/zarf.yaml"
DIST_DIR="${PROJECT_ROOT}/dist"
MAX_PACKAGE_SIZE_GB=10

# Logging
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"
}

error() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $*" >&2
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check if zarf is installed
    if ! command -v zarf &> /dev/null; then
        error "Zarf CLI not found. Please install Zarf first."
        error "Visit: https://docs.zarf.dev/getting-started/install/"
        exit 1
    fi
    
    local zarf_version=$(zarf version 2>&1 | head -1 || echo "unknown")
    log "  Zarf version: ${zarf_version}"
    
    # Check container runtime
    if command -v podman &> /dev/null; then
        log "  Container runtime: podman $(podman --version | awk '{print $3}')"
    elif command -v docker &> /dev/null; then
        log "  Container runtime: docker $(docker --version | awk '{print $3}' | tr -d ',')"
    else
        error "No container runtime found (podman or docker required)"
        exit 1
    fi
    
    # Check if zarf.yaml exists
    if [ ! -f "${ZARF_YAML}" ]; then
        error "zarf.yaml not found at: ${ZARF_YAML}"
        error "Run generate_zarf_yaml.py first"
        exit 1
    fi
    
    log "  Found zarf.yaml: ${ZARF_YAML}"
    
    # Check if assets directory exists
    if [ ! -d "${PROJECT_ROOT}/assets" ]; then
        error "Assets directory not found: ${PROJECT_ROOT}/assets"
        error "Run organize_assets_for_zarf.sh first"
        exit 1
    fi
    
    log "  Found assets directory"
    
    # Check disk space (need at least 15GB for build process)
    local available_space_kb=$(df "${PROJECT_ROOT}" | tail -1 | awk '{print $4}')
    local available_space_gb=$((available_space_kb / 1024 / 1024))
    
    if [ ${available_space_gb} -lt 15 ]; then
        error "Insufficient disk space. Available: ${available_space_gb}GB, Required: 15GB"
        exit 1
    fi
    
    log "  Disk space available: ${available_space_gb}GB"
    
    log "Prerequisites check passed"
}

# Create distribution directory
prepare_dist_dir() {
    log "Preparing distribution directory..."
    
    mkdir -p "${DIST_DIR}"
    
    # Clean old packages (optional, keep for reference)
    local old_packages=$(find "${DIST_DIR}" -name "zarf-package-*.tar.zst" -type f | wc -l)
    if [ ${old_packages} -gt 0 ]; then
        log "  Found ${old_packages} existing package(s) in dist/"
        log "  Keeping existing packages for reference"
    fi
    
    log "Distribution directory ready: ${DIST_DIR}"
}

# Configure Zarf to use Podman
configure_zarf_runtime() {
    log "Configuring Zarf to use Podman..."
    
    local zarf_config_dir="${HOME}/.config/zarf"
    local zarf_config="${zarf_config_dir}/zarf-config.toml"
    
    mkdir -p "${zarf_config_dir}"
    
    cat > "${zarf_config}" << 'EOF'
[package]
[package.create]
[package.create.set]
EOF
    
    log "  Zarf config: ${zarf_config}"
    
    # Set CONTAINER_RUNTIME environment variable for Zarf
    export CONTAINER_RUNTIME=podman
    log "  Container runtime: podman"
}

# Create Zarf package
create_package() {
    log "Creating Zarf package..."
    log "This may take 10-30 minutes depending on asset size..."
    
    configure_zarf_runtime
    
    cd "${PROJECT_ROOT}"
    
    # Run zarf package create with podman
    # --confirm: Skip confirmation prompts
    # --output: Specify output directory
    # CONTAINER_RUNTIME=podman forces Zarf to use podman
    if CONTAINER_RUNTIME=podman zarf package create --confirm --output="${DIST_DIR}"; then
        log "Zarf package created successfully"
    else
        error "Zarf package creation failed"
        exit 1
    fi
}

# Verify package
verify_package() {
    log "Verifying package..."
    
    # Find the created package
    local package_file=$(find "${DIST_DIR}" -name "zarf-package-openCenter-airgap-*.tar.zst" -type f -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)
    
    if [ -z "${package_file}" ]; then
        error "Package file not found in ${DIST_DIR}"
        exit 1
    fi
    
    log "Package file: ${package_file}"
    
    # Check package size
    local package_size_bytes=$(stat -c%s "${package_file}")
    local package_size_mb=$((package_size_bytes / 1024 / 1024))
    local package_size_gb=$((package_size_mb / 1024))
    
    log "Package size: ${package_size_mb}MB (${package_size_gb}GB)"
    
    # Verify size is under limit (Requirement 2.9)
    if [ ${package_size_gb} -ge ${MAX_PACKAGE_SIZE_GB} ]; then
        error "Package size exceeds limit: ${package_size_gb}GB >= ${MAX_PACKAGE_SIZE_GB}GB"
        error "Consider reducing asset size or increasing limit"
        exit 1
    fi
    
    log "  Size check passed: ${package_size_gb}GB < ${MAX_PACKAGE_SIZE_GB}GB"
    
    # Verify package format (Requirement 2.8)
    if [[ "${package_file}" != *.tar.zst ]]; then
        error "Package format incorrect: expected .tar.zst, got ${package_file}"
        exit 1
    fi
    
    log "  Format check passed: .tar.zst"
    
    # Inspect package contents
    log "Inspecting package contents..."
    if zarf package inspect "${package_file}" > "${DIST_DIR}/package-inspection.txt" 2>&1; then
        log "  Package inspection saved to: ${DIST_DIR}/package-inspection.txt"
        
        # Extract component count
        local component_count=$(grep -c "Component:" "${DIST_DIR}/package-inspection.txt" || echo "0")
        log "  Components found: ${component_count}"
        
        # Verify expected components
        local expected_components=("bootstrap-tools" "terraform-providers" "kubespray-core" "k8s-images" "deploy-cluster")
        for comp in "${expected_components[@]}"; do
            if grep -q "Component: ${comp}" "${DIST_DIR}/package-inspection.txt"; then
                log "    ✓ ${comp}"
            else
                error "    ✗ ${comp} - MISSING"
                exit 1
            fi
        done
    else
        error "Package inspection failed"
        exit 1
    fi
    
    # Check for SBOM (Requirement 2.4, 2.5)
    log "Checking for SBOM..."
    if zarf package inspect "${package_file}" --sbom > "${DIST_DIR}/package-sbom.txt" 2>&1; then
        log "  SBOM extracted to: ${DIST_DIR}/package-sbom.txt"
        
        # Verify SBOM is not empty
        local sbom_size=$(stat -c%s "${DIST_DIR}/package-sbom.txt")
        if [ ${sbom_size} -gt 100 ]; then
            log "  SBOM check passed: ${sbom_size} bytes"
        else
            error "SBOM appears empty or invalid"
            exit 1
        fi
        
        # Run SBOM completeness verification (Requirement 10.9)
        log "Verifying SBOM completeness..."
        if python3 "${SCRIPT_DIR}/verify_sbom.py" "${package_file}" -r "${DIST_DIR}/sbom-verification-report.txt"; then
            log "  SBOM completeness verification passed"
        else
            error "SBOM completeness verification failed"
            error "See: ${DIST_DIR}/sbom-verification-report.txt"
            exit 1
        fi
    else
        error "SBOM extraction failed"
        exit 1
    fi
    
    log "Package verification complete"
    
    # Return package file path for checksum generation
    echo "${package_file}"
}

# Generate checksums
generate_checksums() {
    local package_file="$1"
    
    log "Generating checksums..."
    
    local package_name=$(basename "${package_file}")
    local checksum_file="${DIST_DIR}/${package_name}.checksums"
    
    cd "${DIST_DIR}"
    
    # Generate MD5 checksum (Requirement 2.6)
    log "  Computing MD5..."
    local md5sum=$(md5sum "${package_name}" | awk '{print $1}')
    echo "MD5: ${md5sum}" > "${checksum_file}"
    log "    MD5: ${md5sum}"
    
    # Generate SHA256 checksum (Requirement 2.6)
    log "  Computing SHA256..."
    local sha256sum=$(sha256sum "${package_name}" | awk '{print $1}')
    echo "SHA256: ${sha256sum}" >> "${checksum_file}"
    log "    SHA256: ${sha256sum}"
    
    log "Checksums saved to: ${checksum_file}"
}

# Main execution
main() {
    log "========================================="
    log "Zarf Package Build Script"
    log "========================================="
    log ""
    
    check_prerequisites
    prepare_dist_dir
    create_package
    
    local package_file=$(verify_package)
    generate_checksums "${package_file}"
    
    log ""
    log "========================================="
    log "Package build complete!"
    log "========================================="
    log ""
    log "Package: ${package_file}"
    log "Checksums: ${DIST_DIR}/$(basename ${package_file}).checksums"
    log "Inspection: ${DIST_DIR}/package-inspection.txt"
    log "SBOM: ${DIST_DIR}/package-sbom.txt"
    log "SBOM Verification: ${DIST_DIR}/sbom-verification-report.txt"
    log ""
    log "Next steps:"
    log "1. Review package inspection and SBOM"
    log "2. (Optional) Sign package: cosign sign --key <key> ${package_file}"
    log "3. Transfer package to air-gapped environment"
    log "4. Deploy: zarf package deploy ${package_file}"
}

main "$@"
