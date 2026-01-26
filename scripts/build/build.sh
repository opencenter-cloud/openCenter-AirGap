#!/bin/bash
set -euo pipefail

# openCenter AirGap Master Build Script
# Orchestrates complete build process from asset collection to Zarf package creation

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Build configuration
BUILD_START_TIME=$(date +%s)
BUILD_LOG="${PROJECT_ROOT}/build/build-$(date +%Y%m%d-%H%M%S).log"
SKIP_OPENCENTER="${SKIP_OPENCENTER:-false}"
SKIP_KUBESPRAY_OFFLINE="${SKIP_KUBESPRAY_OFFLINE:-false}"
SKIP_ZARF="${SKIP_ZARF:-false}"
NON_INTERACTIVE="${NON_INTERACTIVE:-false}"

log_info() {
    echo -e "${GREEN}[INFO]${NC} $*" | tee -a "${BUILD_LOG}"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*" | tee -a "${BUILD_LOG}"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*" | tee -a "${BUILD_LOG}"
}

log_step() {
    echo "" | tee -a "${BUILD_LOG}"
    echo -e "${CYAN}========================================${NC}" | tee -a "${BUILD_LOG}"
    echo -e "${CYAN}$*${NC}" | tee -a "${BUILD_LOG}"
    echo -e "${CYAN}========================================${NC}" | tee -a "${BUILD_LOG}"
    echo "" | tee -a "${BUILD_LOG}"
}

print_header() {
    clear
    echo -e "${BLUE}"
    cat << 'EOF'
╔═══════════════════════════════════════════════════════���═══════╗
║                                                               ║
║              openCenter AirGap Build System                   ║
║                                                               ║
║  Building air-gap deployment artifact for disconnected        ║
║  Kubernetes clusters                                          ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
EOF
    echo -e "${NC}"
}

check_prerequisites() {
    log_step "Step 0: Checking Prerequisites"
    
    local missing_deps=()
    
    # Check Python version
    if ! command -v python3.12 &> /dev/null; then
        if ! command -v python3 &> /dev/null; then
            missing_deps+=("python3.12")
        else
            PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
            if (( $(echo "$PYTHON_VERSION < 3.12" | bc -l) )); then
                log_error "Python 3.12+ required, found: $PYTHON_VERSION"
                missing_deps+=("python3.12")
            else
                log_info "Python version: $(python3 --version)"
            fi
        fi
    else
        log_info "Python version: $(python3.12 --version)"
    fi
    
    # Check container runtime
    if command -v podman &> /dev/null; then
        log_info "Container runtime: podman $(podman --version | cut -d' ' -f3)"
    elif command -v docker &> /dev/null; then
        log_info "Container runtime: docker $(docker --version | cut -d' ' -f3)"
    else
        missing_deps+=("podman or docker")
    fi
    
    # Check git
    if ! command -v git &> /dev/null; then
        missing_deps+=("git")
    else
        log_info "Git version: $(git --version | cut -d' ' -f3)"
    fi
    
    # Check jq
    if ! command -v jq &> /dev/null; then
        missing_deps+=("jq")
    else
        log_info "jq version: $(jq --version)"
    fi
    
    # Check Zarf (optional, can be installed later)
    if command -v zarf &> /dev/null; then
        log_info "Zarf version: $(zarf version)"
    else
        log_warn "Zarf CLI not found (will be needed for package creation)"
    fi
    
    # Check disk space
    AVAILABLE_SPACE=$(df -BG "${PROJECT_ROOT}" | tail -1 | awk '{print $4}' | sed 's/G//')
    if [ "${AVAILABLE_SPACE}" -lt 100 ]; then
        log_warn "Low disk space: ${AVAILABLE_SPACE}GB available (100GB+ recommended)"
    else
        log_info "Disk space: ${AVAILABLE_SPACE}GB available"
    fi
    
    if [ ${#missing_deps[@]} -gt 0 ]; then
        log_error "Missing dependencies: ${missing_deps[*]}"
        log_error "Install missing dependencies and re-run"
        exit 1
    fi
    
    log_info "All prerequisites satisfied"
}

setup_python_environment() {
    log_step "Step 1: Setting Up Python Environment"
    
    cd "${PROJECT_ROOT}"
    
    if [ ! -d "venv" ]; then
        log_info "Creating Python virtual environment..."
        python3.12 -m venv venv
    else
        log_info "Python virtual environment already exists"
    fi
    
    log_info "Activating virtual environment..."
    source venv/bin/activate
    
    log_info "Installing Python dependencies..."
    pip install --upgrade pip --quiet
    pip install pyyaml jinja2 requests hypothesis pytest --quiet
    
    log_info "Python environment ready"
}

check_github_token() {
    log_step "Step 2: Checking GitHub Token"
    
    if [ -z "${GITHUB_TOKEN:-}" ]; then
        log_warn "GITHUB_TOKEN not set"
        log_warn "openCenter assets require GitHub authentication"
        
        if [ "${NON_INTERACTIVE}" = "true" ]; then
            log_error "Running in non-interactive mode, cannot prompt for token"
            log_error "Set GITHUB_TOKEN or use SKIP_OPENCENTER=true"
            exit 1
        fi
        
        echo ""
        read -p "Run GitHub token setup now? [Y/n]: " setup_token
        
        if [[ ! "${setup_token}" =~ ^[Nn]$ ]]; then
            "${SCRIPT_DIR}/setup_github_token.sh"
            
            # Check if token was set
            if [ -z "${GITHUB_TOKEN:-}" ]; then
                log_error "GITHUB_TOKEN still not set after setup"
                log_error "Export token manually or skip openCenter assets with SKIP_OPENCENTER=true"
                exit 1
            fi
        else
            log_warn "Skipping GitHub token setup"
            log_warn "openCenter assets will not be collected"
            SKIP_OPENCENTER=true
        fi
    else
        log_info "GITHUB_TOKEN is set"
    fi
}

collect_opencenter_assets() {
    if [ "${SKIP_OPENCENTER}" = "true" ]; then
        log_warn "Skipping openCenter asset collection (SKIP_OPENCENTER=true)"
        return
    fi
    
    log_step "Step 3: Collecting openCenter Assets"
    
    if [ ! -f "${SCRIPT_DIR}/collect_opencenter_assets.sh" ]; then
        log_error "collect_opencenter_assets.sh not found"
        exit 1
    fi
    
    log_info "Running openCenter asset collection..."
    "${SCRIPT_DIR}/collect_opencenter_assets.sh" 2>&1 | tee -a "${BUILD_LOG}"
    
    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        log_info "openCenter assets collected successfully"
    else
        log_error "openCenter asset collection failed"
        exit 1
    fi
}

clone_kubespray_offline() {
    if [ "${SKIP_KUBESPRAY_OFFLINE}" = "true" ]; then
        log_warn "Skipping kubespray-offline (SKIP_KUBESPRAY_OFFLINE=true)"
        return
    fi
    
    log_step "Step 4: Cloning kubespray-offline"
    
    KUBESPRAY_OFFLINE_DIR="${PROJECT_ROOT}/build/kubespray-offline"
    
    if [ -d "${KUBESPRAY_OFFLINE_DIR}/.git" ]; then
        log_info "kubespray-offline already cloned, pulling latest..."
        cd "${KUBESPRAY_OFFLINE_DIR}"
        git fetch origin
        git checkout main
        git pull origin main
    else
        log_info "Cloning kubespray-offline..."
        mkdir -p "${PROJECT_ROOT}/build"
        git clone -b main https://github.com/tmurakam/kubespray-offline.git "${KUBESPRAY_OFFLINE_DIR}"
    fi
    
    log_info "kubespray-offline ready at: ${KUBESPRAY_OFFLINE_DIR}"
}

run_kubespray_offline_download() {
    if [ "${SKIP_KUBESPRAY_OFFLINE}" = "true" ]; then
        log_warn "Skipping kubespray-offline download"
        return
    fi
    
    log_step "Step 5: Running kubespray-offline Asset Download"
    
    KUBESPRAY_OFFLINE_DIR="${PROJECT_ROOT}/build/kubespray-offline"
    
    if [ ! -f "${KUBESPRAY_OFFLINE_DIR}/download-all.sh" ]; then
        log_error "kubespray-offline/download-all.sh not found"
        exit 1
    fi
    
    # Merge openCenter images before download
    log_info "Merging openCenter platform service images..."
    if [ -f "${SCRIPT_DIR}/merge_opencenter_images.sh" ]; then
        "${SCRIPT_DIR}/merge_opencenter_images.sh" 2>&1 | tee -a "${BUILD_LOG}"
        
        if [ ${PIPESTATUS[0]} -ne 0 ]; then
            log_error "Failed to merge openCenter images"
            exit 1
        fi
    else
        log_warn "merge_opencenter_images.sh not found, skipping image merge"
    fi
    
    cd "${KUBESPRAY_OFFLINE_DIR}"
    
    log_info "Starting kubespray-offline download (this may take 30-60 minutes)..."
    log_info "Downloading Kubernetes binaries, images, packages, and wheels..."
    log_info "Including openCenter platform service images (20+ services)..."
    
    ./download-all.sh 2>&1 | tee -a "${BUILD_LOG}"
    
    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        log_info "kubespray-offline download completed successfully"
        
        # Show download summary
        if [ -d "outputs" ]; then
            log_info "Downloaded assets:"
            du -sh outputs/* 2>/dev/null | while read size dir; do
                echo "  - $(basename $dir): $size"
            done | tee -a "${BUILD_LOG}"
        fi
    else
        log_error "kubespray-offline download failed"
        exit 1
    fi
    
    cd "${PROJECT_ROOT}"
}

organize_assets() {
    log_step "Step 6: Organizing Assets for Zarf"
    
    log_info "Creating asset directories..."
    mkdir -p "${PROJECT_ROOT}/assets"
    
    # Copy kubespray-offline outputs to assets
    if [ -d "${PROJECT_ROOT}/build/kubespray-offline/outputs" ]; then
        log_info "Copying kubespray-offline outputs to assets..."
        
        # Create symlinks or copy (depending on size)
        if [ ! -L "${PROJECT_ROOT}/assets/kubespray-offline-outputs" ]; then
            ln -sf "${PROJECT_ROOT}/build/kubespray-offline/outputs" \
                   "${PROJECT_ROOT}/assets/kubespray-offline-outputs"
            log_info "Linked kubespray-offline outputs"
        fi
    fi
    
    # Copy openCenter assets
    if [ -d "${PROJECT_ROOT}/assets/gitops-base" ]; then
        log_info "openCenter GitOps base: $(du -sh ${PROJECT_ROOT}/assets/gitops-base | cut -f1)"
    fi
    
    if [ -d "${PROJECT_ROOT}/build/opencenter-images" ]; then
        log_info "openCenter images: $(du -sh ${PROJECT_ROOT}/build/opencenter-images | cut -f1)"
    fi
    
    log_info "Assets organized"
}

generate_zarf_yaml() {
    log_step "Step 7: Validating zarf.yaml"
    
    if [ ! -f "${PROJECT_ROOT}/zarf.yaml" ]; then
        log_error "zarf.yaml not found at ${PROJECT_ROOT}/zarf.yaml"
        log_error "This file is required for Zarf package creation"
        exit 1
    fi
    
    log_info "zarf.yaml found"
    
    # Validate basic YAML syntax
    if command -v yq &> /dev/null; then
        if yq eval '.' "${PROJECT_ROOT}/zarf.yaml" > /dev/null 2>&1; then
            log_info "zarf.yaml syntax valid"
        else
            log_error "zarf.yaml has invalid YAML syntax"
            exit 1
        fi
    elif python3 -c "import yaml" 2>/dev/null; then
        if python3 -c "import yaml; yaml.safe_load(open('${PROJECT_ROOT}/zarf.yaml'))" > /dev/null 2>&1; then
            log_info "zarf.yaml syntax valid"
        else
            log_error "zarf.yaml has invalid YAML syntax"
            exit 1
        fi
    else
        log_warn "Cannot validate YAML syntax (yq or PyYAML not available)"
    fi
    
    log_info "zarf.yaml ready"
}

create_zarf_package() {
    if [ "${SKIP_ZARF}" = "true" ]; then
        log_warn "Skipping Zarf package creation (SKIP_ZARF=true)"
        return
    fi
    
    log_step "Step 8: Creating Zarf Package"
    
    if ! command -v zarf &> /dev/null; then
        log_error "Zarf CLI not found"
        log_error "Install Zarf: curl -sL https://get.zarf.dev | bash"
        exit 1
    fi
    
    cd "${PROJECT_ROOT}"
    
    mkdir -p dist
    
    log_info "Creating Zarf package (this may take 10-30 minutes)..."
    log_info "Using podman as container runtime..."
    
    ZARF_CONFIG="${HOME}/.config/zarf/zarf-config.toml"
    mkdir -p "$(dirname "${ZARF_CONFIG}")"
    
    # Configure Zarf to use podman
    cat > "${ZARF_CONFIG}" << 'EOF'
[package]
[package.create]
[package.create.set]
container_runtime = "podman"
EOF
    
    zarf package create . --confirm 2>&1 | tee -a "${BUILD_LOG}"
    
    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        log_info "Zarf package created successfully"
        
        # Find the created package
        PACKAGE=$(find dist -name "zarf-package-*.tar.zst" -type f -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)
        
        if [ -n "${PACKAGE}" ]; then
            PACKAGE_SIZE=$(du -h "${PACKAGE}" | cut -f1)
            log_info "Package: ${PACKAGE}"
            log_info "Size: ${PACKAGE_SIZE}"
        fi
    else
        log_error "Zarf package creation failed"
        exit 1
    fi
}

generate_checksums() {
    log_step "Step 9: Generating Checksums"
    
    cd "${PROJECT_ROOT}/dist"
    
    PACKAGE=$(find . -name "zarf-package-*.tar.zst" -type f -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)
    
    if [ -z "${PACKAGE}" ]; then
        log_error "No Zarf package found in dist/"
        exit 1
    fi
    
    log_info "Generating SHA256 checksum..."
    sha256sum "${PACKAGE}" > "${PACKAGE}.sha256"
    
    log_info "Generating MD5 checksum..."
    md5sum "${PACKAGE}" > "${PACKAGE}.md5"
    
    log_info "Checksums generated:"
    cat "${PACKAGE}.sha256" | tee -a "${BUILD_LOG}"
    
    cd "${PROJECT_ROOT}"
}

inspect_package() {
    log_step "Step 10: Inspecting Package"
    
    cd "${PROJECT_ROOT}/dist"
    
    PACKAGE=$(find . -name "zarf-package-*.tar.zst" -type f -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)
    
    if [ -z "${PACKAGE}" ]; then
        log_error "No Zarf package found"
        return
    fi
    
    log_info "Inspecting package contents..."
    zarf package inspect "${PACKAGE}" 2>&1 | tee -a "${BUILD_LOG}"
    
    log_info "Generating SBOM..."
    zarf package inspect "${PACKAGE}" --sbom-out="${PROJECT_ROOT}/dist" 2>&1 | tee -a "${BUILD_LOG}"
    
    cd "${PROJECT_ROOT}"
}

generate_build_summary() {
    log_step "Build Summary"
    
    BUILD_END_TIME=$(date +%s)
    BUILD_DURATION=$((BUILD_END_TIME - BUILD_START_TIME))
    BUILD_DURATION_MIN=$((BUILD_DURATION / 60))
    BUILD_DURATION_SEC=$((BUILD_DURATION % 60))
    
    echo "" | tee -a "${BUILD_LOG}"
    echo "╔═══════════════════════════════════════════════════════════════╗" | tee -a "${BUILD_LOG}"
    echo "║                     BUILD COMPLETE                            ║" | tee -a "${BUILD_LOG}"
    echo "╚═══════════════════════════════════════════════════════════════╝" | tee -a "${BUILD_LOG}"
    echo "" | tee -a "${BUILD_LOG}"
    
    log_info "Build duration: ${BUILD_DURATION_MIN}m ${BUILD_DURATION_SEC}s"
    log_info "Build log: ${BUILD_LOG}"
    
    if [ -d "${PROJECT_ROOT}/dist" ]; then
        log_info "Output directory: ${PROJECT_ROOT}/dist"
        echo "" | tee -a "${BUILD_LOG}"
        log_info "Built artifacts:"
        ls -lh "${PROJECT_ROOT}/dist" | tail -n +2 | tee -a "${BUILD_LOG}"
    fi
    
    echo "" | tee -a "${BUILD_LOG}"
    log_info "Next steps:"
    echo "  1. Verify package integrity:" | tee -a "${BUILD_LOG}"
    echo "     cd dist && sha256sum -c zarf-package-*.tar.zst.sha256" | tee -a "${BUILD_LOG}"
    echo "" | tee -a "${BUILD_LOG}"
    echo "  2. Transfer to Zone B (Airlock):" | tee -a "${BUILD_LOG}"
    echo "     cp dist/zarf-package-*.tar.zst /media/usb/" | tee -a "${BUILD_LOG}"
    echo "" | tee -a "${BUILD_LOG}"
    echo "  3. Deploy in Zone C (Field):" | tee -a "${BUILD_LOG}"
    echo "     See docs/how-to/deploy/deploy-baremetal-cluster.md" | tee -a "${BUILD_LOG}"
    echo "" | tee -a "${BUILD_LOG}"
}

cleanup_on_error() {
    log_error "Build failed!"
    log_error "Check build log: ${BUILD_LOG}"
    exit 1
}

# Main execution
main() {
    # Setup error handling
    trap cleanup_on_error ERR
    
    # Create build directory and log
    mkdir -p "${PROJECT_ROOT}/build"
    
    print_header
    
    check_prerequisites
    setup_python_environment
    check_github_token
    collect_opencenter_assets
    clone_kubespray_offline
    run_kubespray_offline_download
    organize_assets
    generate_zarf_yaml
    create_zarf_package
    generate_checksums
    inspect_package
    generate_build_summary
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-opencenter)
            SKIP_OPENCENTER=true
            shift
            ;;
        --skip-kubespray-offline)
            SKIP_KUBESPRAY_OFFLINE=true
            shift
            ;;
        --skip-zarf)
            SKIP_ZARF=true
            shift
            ;;
        --non-interactive)
            NON_INTERACTIVE=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --skip-opencenter         Skip openCenter asset collection"
            echo "  --skip-kubespray-offline  Skip kubespray-offline download"
            echo "  --skip-zarf               Skip Zarf package creation"
            echo "  --non-interactive         Run without prompts (fail on missing config)"
            echo "  --help                    Show this help message"
            echo ""
            echo "Environment variables:"
            echo "  GITHUB_TOKEN              GitHub Personal Access Token"
            echo "  ALL_TAGS                  Fetch all image tags (default: true)"
            echo "  SKIP_OPENCENTER           Skip openCenter assets (default: false)"
            echo "  SKIP_KUBESPRAY_OFFLINE    Skip kubespray-offline (default: false)"
            echo "  SKIP_ZARF                 Skip Zarf packaging (default: false)"
            echo "  NON_INTERACTIVE           Run without prompts (default: false)"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

main "$@"

