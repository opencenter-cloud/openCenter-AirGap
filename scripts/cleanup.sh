#!/bin/bash
#
# Cleanup Script for openCenter AirGap
#
# Removes build artifacts, downloaded assets, and temporary files to reclaim disk space.
# This script is safe to run between builds or when switching versions.
#
# Usage:
#   ./scripts/cleanup.sh [options]
#
# Options:
#   --all              Remove everything (build artifacts, assets, dist packages)
#   --build            Remove build artifacts only (build/ directory)
#   --assets           Remove organized assets only (assets/ directory)
#   --dist             Remove distribution packages only (dist/ directory)
#   --venv             Remove Python virtual environment (venv/ directory)
#   --dry-run          Show what would be removed without deleting
#   --help             Show this help message
#
# Examples:
#   ./scripts/cleanup.sh --all              # Clean everything
#   ./scripts/cleanup.sh --build --assets   # Clean build and assets only
#   ./scripts/cleanup.sh --dry-run --all    # Preview what would be deleted
#
# What Gets Removed:
#
#   --build:
#     • build/kubespray-offline/outputs/    (K8s images, binaries, packages)
#     • build/kubespray-offline/.download/  (Download cache)
#     • Preserves: kubespray-offline git repo and configuration
#
#   --assets:
#     • assets/k8s-binaries/                (Organized K8s binaries)
#     • assets/kubespray/                   (Extracted Kubespray)
#     • assets/playbook/                    (Ansible playbooks)
#     • assets/python-wheels/               (PyPI mirror)
#     • assets/repos/                       (Apt repository)
#     • assets/target-scripts/              (Bastion setup scripts)
#     • assets/terraform-mirror/            (Terraform providers)
#     • Preserves: assets/terraform/ (Terraform configs)
#
#   --dist:
#     • dist/*.tar.zst                      (Zarf packages)
#     • dist/*.checksums                    (Checksum manifests)
#     • dist/*.sig                          (Cosign signatures)
#     • dist/*.txt                          (Inspection/SBOM outputs)
#
#   --venv:
#     • venv/                               (Python virtual environment)
#     • Preserves: requirements.txt
#
#   --all:
#     • All of the above
#
# What Gets Preserved:
#   • Source code (scripts/, docs/, config/)
#   • Git repository (.git/)
#   • Configuration files (config/versions.env, zarf.yaml)
#   • kubespray-offline git repository (build/kubespray-offline/.git)
#   • kubespray-offline configuration (build/kubespray-offline/target-scripts/config.sh)
#   • Documentation (docs/, README.md)
#

set -euo pipefail

# Determine project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Cleanup targets
CLEAN_BUILD=false
CLEAN_ASSETS=false
CLEAN_DIST=false
CLEAN_VENV=false
DRY_RUN=false

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[CLEANUP]${NC} $*"
}

warn() {
    echo -e "${YELLOW}[CLEANUP]${NC} $*"
}

error() {
    echo -e "${RED}[CLEANUP]${NC} $*" >&2
}

info() {
    echo -e "${BLUE}[CLEANUP]${NC} $*"
}

# Parse arguments
parse_args() {
    if [ $# -eq 0 ]; then
        error "No options specified. Use --help for usage information."
        exit 1
    fi

    while [[ $# -gt 0 ]]; do
        case $1 in
            --all)
                CLEAN_BUILD=true
                CLEAN_ASSETS=true
                CLEAN_DIST=true
                CLEAN_VENV=true
                shift
                ;;
            --build)
                CLEAN_BUILD=true
                shift
                ;;
            --assets)
                CLEAN_ASSETS=true
                shift
                ;;
            --dist)
                CLEAN_DIST=true
                shift
                ;;
            --venv)
                CLEAN_VENV=true
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --help)
                grep '^#' "$0" | head -80 | grep -v '#!/bin/bash' | sed 's/^# //' | sed 's/^#//'
                exit 0
                ;;
            *)
                error "Unknown option: $1"
                echo "Use --help for usage information"
                exit 1
                ;;
        esac
    done
}

# Calculate directory size
get_size() {
    local path="$1"
    if [ -d "$path" ]; then
        du -sh "$path" 2>/dev/null | cut -f1
    else
        echo "0"
    fi
}

# Remove directory or file
remove_path() {
    local path="$1"
    local description="$2"
    
    if [ ! -e "$path" ]; then
        info "  $description: Not found (skipping)"
        return 0
    fi
    
    local size=$(get_size "$path")
    
    if [ "$DRY_RUN" = true ]; then
        warn "  [DRY RUN] Would remove: $description ($size)"
    else
        log "  Removing: $description ($size)"
        rm -rf "$path"
    fi
}

# Clean build artifacts
clean_build() {
    log "Cleaning build artifacts..."
    
    local build_dir="${PROJECT_ROOT}/build/kubespray-offline"
    
    if [ ! -d "$build_dir" ]; then
        info "  kubespray-offline not found (skipping)"
        return 0
    fi
    
    remove_path "${build_dir}/outputs" "kubespray-offline outputs"
    remove_path "${build_dir}/.download" "Download cache"
    remove_path "${build_dir}/kubespray" "Extracted Kubespray (build)"
    
    # Clean any tar.gz files in kubespray-offline root
    if [ "$DRY_RUN" = false ]; then
        find "${build_dir}" -maxdepth 1 -name "*.tar.gz" -type f -delete 2>/dev/null || true
    fi
    
    log "Build artifacts cleaned"
}

# Clean organized assets
clean_assets() {
    log "Cleaning organized assets..."
    
    local assets_dir="${PROJECT_ROOT}/assets"
    
    if [ ! -d "$assets_dir" ]; then
        info "  Assets directory not found (skipping)"
        return 0
    fi
    
    remove_path "${assets_dir}/k8s-binaries" "K8s binaries"
    remove_path "${assets_dir}/kubespray" "Kubespray playbooks"
    remove_path "${assets_dir}/playbook" "Ansible playbooks"
    remove_path "${assets_dir}/python-wheels" "Python wheels"
    remove_path "${assets_dir}/repos" "Package repositories"
    remove_path "${assets_dir}/target-scripts" "Target scripts"
    remove_path "${assets_dir}/terraform-mirror" "Terraform provider mirror"
    
    # Note: Preserve assets/terraform/ (Terraform configs)
    
    log "Organized assets cleaned"
}

# Clean distribution packages
clean_dist() {
    log "Cleaning distribution packages..."
    
    local dist_dir="${PROJECT_ROOT}/dist"
    
    if [ ! -d "$dist_dir" ]; then
        info "  Distribution directory not found (skipping)"
        return 0
    fi
    
    # Count files before removal
    local package_count=$(find "${dist_dir}" -name "*.tar.zst" -type f 2>/dev/null | wc -l)
    local total_size=$(get_size "${dist_dir}")
    
    if [ "$package_count" -eq 0 ]; then
        info "  No packages found (skipping)"
        return 0
    fi
    
    if [ "$DRY_RUN" = true ]; then
        warn "  [DRY RUN] Would remove: $package_count package(s) ($total_size total)"
        find "${dist_dir}" -type f 2>/dev/null | while read file; do
            warn "    - $(basename $file)"
        done
    else
        log "  Removing: $package_count package(s) ($total_size total)"
        rm -rf "${dist_dir}"/*
    fi
    
    log "Distribution packages cleaned"
}

# Clean Python virtual environment
clean_venv() {
    log "Cleaning Python virtual environment..."
    
    local venv_dir="${PROJECT_ROOT}/venv"
    
    remove_path "${venv_dir}" "Python venv"
    
    log "Python virtual environment cleaned"
}

# Calculate total space to be freed
calculate_total_space() {
    local total=0
    
    if [ "$CLEAN_BUILD" = true ]; then
        local build_outputs="${PROJECT_ROOT}/build/kubespray-offline/outputs"
        if [ -d "$build_outputs" ]; then
            local size=$(du -sb "$build_outputs" 2>/dev/null | cut -f1)
            total=$((total + size))
        fi
    fi
    
    if [ "$CLEAN_ASSETS" = true ]; then
        local assets_dir="${PROJECT_ROOT}/assets"
        if [ -d "$assets_dir" ]; then
            local size=$(du -sb "$assets_dir" 2>/dev/null | cut -f1)
            total=$((total + size))
        fi
    fi
    
    if [ "$CLEAN_DIST" = true ]; then
        local dist_dir="${PROJECT_ROOT}/dist"
        if [ -d "$dist_dir" ]; then
            local size=$(du -sb "$dist_dir" 2>/dev/null | cut -f1)
            total=$((total + size))
        fi
    fi
    
    if [ "$CLEAN_VENV" = true ]; then
        local venv_dir="${PROJECT_ROOT}/venv"
        if [ -d "$venv_dir" ]; then
            local size=$(du -sb "$venv_dir" 2>/dev/null | cut -f1)
            total=$((total + size))
        fi
    fi
    
    # Convert bytes to human readable
    if [ $total -gt 0 ]; then
        echo "$total" | awk '{ 
            if ($1 > 1073741824) printf "%.2f GB\n", $1/1073741824;
            else if ($1 > 1048576) printf "%.2f MB\n", $1/1048576;
            else if ($1 > 1024) printf "%.2f KB\n", $1/1024;
            else printf "%d bytes\n", $1;
        }'
    else
        echo "0 bytes"
    fi
}

# Main execution
main() {
    log "openCenter AirGap Cleanup Script"
    log "Project root: ${PROJECT_ROOT}"
    echo ""
    
    # Parse arguments
    parse_args "$@"
    
    # Show what will be cleaned
    log "Cleanup targets:"
    [ "$CLEAN_BUILD" = true ] && log "  ✓ Build artifacts (build/kubespray-offline/outputs/)"
    [ "$CLEAN_ASSETS" = true ] && log "  ✓ Organized assets (assets/)"
    [ "$CLEAN_DIST" = true ] && log "  ✓ Distribution packages (dist/)"
    [ "$CLEAN_VENV" = true ] && log "  ✓ Python virtual environment (venv/)"
    echo ""
    
    # Calculate space to be freed
    local space_to_free=$(calculate_total_space)
    info "Estimated space to be freed: $space_to_free"
    echo ""
    
    if [ "$DRY_RUN" = true ]; then
        warn "DRY RUN MODE - No files will be deleted"
        echo ""
    fi
    
    # Confirm if not dry run
    if [ "$DRY_RUN" = false ]; then
        read -p "Continue with cleanup? [y/N] " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            warn "Cleanup cancelled"
            exit 0
        fi
        echo ""
    fi
    
    # Execute cleanup
    [ "$CLEAN_BUILD" = true ] && clean_build
    [ "$CLEAN_ASSETS" = true ] && clean_assets
    [ "$CLEAN_DIST" = true ] && clean_dist
    [ "$CLEAN_VENV" = true ] && clean_venv
    
    echo ""
    if [ "$DRY_RUN" = true ]; then
        log "Dry run complete. No files were deleted."
    else
        log "Cleanup complete!"
        
        # Show what's preserved
        echo ""
        info "Preserved:"
        info "  • Source code (scripts/, docs/, config/)"
        info "  • Git repository (.git/)"
        info "  • Configuration files (config/versions.env, zarf.yaml)"
        [ "$CLEAN_BUILD" = true ] && info "  • kubespray-offline git repo and config"
        info "  • Documentation (docs/, README.md)"
    fi
}

# Run main
main "$@"
