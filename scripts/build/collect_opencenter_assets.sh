#!/bin/bash
set -euo pipefail

# Collect openCenter-specific assets (GitOps base and container images)
# Requires GITHUB_TOKEN environment variable for private packages

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Source version configuration
source "${PROJECT_ROOT}/config/versions.env"

# Options
<<<<<<< HEAD
ALL_TAGS="${ALL_TAGS:-true}"  # Set to false to only pull latest tags
=======
ALL_TAGS="${ALL_TAGS:-false}"  # Set to true to pull all version tags (slow, may hit rate limits)
>>>>>>> c44a6e4 (feat: implement build determinism validation and complete image list generation)
# Output directories
GITOPS_BASE_DIR="${PROJECT_ROOT}/assets/gitops-base"
IMAGES_DIR="${PROJECT_ROOT}/build/opencenter-images"
IMAGE_LIST="${PROJECT_ROOT}/build/opencenter-image-list.txt"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    if ! command -v git &> /dev/null; then
        log_error "git is not installed"
        exit 1
    fi
    
    if ! command -v podman &> /dev/null && ! command -v docker &> /dev/null; then
        log_error "Neither podman nor docker is installed"
        exit 1
    fi
    
    # Determine container runtime
    if command -v podman &> /dev/null; then
        CONTAINER_RUNTIME="podman"
    else
        CONTAINER_RUNTIME="docker"
    fi
    
    log_info "Using container runtime: ${CONTAINER_RUNTIME}"
    
    if [ -z "${GITHUB_TOKEN:-}" ]; then
        log_warn "GITHUB_TOKEN not set. Private packages may not be accessible."
        log_warn "Set GITHUB_TOKEN to download private container images:"
        log_warn "  export GITHUB_TOKEN=ghp_xxxxxxxxxxxx"
    else
        log_info "GITHUB_TOKEN is set"
    fi
}

# Clone openCenter GitOps base repository
clone_gitops_base() {
    log_info "Cloning openCenter GitOps base repository..."
    
    mkdir -p "${GITOPS_BASE_DIR}"
    
    if [ -d "${GITOPS_BASE_DIR}/.git" ]; then
        log_info "Repository already exists, pulling latest changes..."
        cd "${GITOPS_BASE_DIR}"
        git fetch origin
        git checkout "${OPENCENTER_GITOPS_BASE_VERSION}"
        git pull origin "${OPENCENTER_GITOPS_BASE_VERSION}"
    else
        log_info "Cloning ${OPENCENTER_GITOPS_BASE_REPO}..."
        git clone -b "${OPENCENTER_GITOPS_BASE_VERSION}" \
            "${OPENCENTER_GITOPS_BASE_REPO}" \
            "${GITOPS_BASE_DIR}"
    fi
    
    log_info "GitOps base cloned to: ${GITOPS_BASE_DIR}"
}

# Fetch list of container images from GitHub Container Registry
fetch_opencenter_images() {
    log_info "Fetching openCenter container image list..."
    
    if [ -z "${GITHUB_TOKEN:-}" ]; then
        log_error "GITHUB_TOKEN required to list packages"
        log_error "Export GITHUB_TOKEN and re-run:"
        log_error "  export GITHUB_TOKEN=ghp_xxxxxxxxxxxx"
        exit 1
    fi
    
    # GitHub API endpoint for organization packages
    API_URL="https://api.github.com/orgs/opencenter-cloud/packages?package_type=container"
    
    log_info "Querying GitHub API: ${API_URL}"
    
    # Fetch package list
    PACKAGES=$(curl -s -H "Authorization: Bearer ${GITHUB_TOKEN}" \
                    -H "Accept: application/vnd.github+json" \
                    "${API_URL}")
    
    if echo "${PACKAGES}" | grep -q "message"; then
        log_error "Failed to fetch packages from GitHub API"
        echo "${PACKAGES}" | jq -r '.message' 2>/dev/null || echo "${PACKAGES}"
        exit 1
    fi
    
    # Extract package names
    mapfile -t PACKAGE_ARRAY < <(echo "${PACKAGES}" | jq -r '.[].name')
    
    if [ ${#PACKAGE_ARRAY[@]} -eq 0 ]; then
        log_warn "No packages found in opencenter-cloud organization"
        return
    fi
    
    log_info "Found packages:"
    for pkg in "${PACKAGE_ARRAY[@]}"; do
        echo "  - ${pkg}"
    done
    
    # Create image list with all tags
    mkdir -p "$(dirname "${IMAGE_LIST}")"
    > "${IMAGE_LIST}"
    
    for package in "${PACKAGE_ARRAY[@]}"; do
        [ -z "${package}" ] && continue
        
        log_info "Processing package: ${package}"
        
        # Fetch versions for each package
        VERSIONS_URL="https://api.github.com/orgs/opencenter-cloud/packages/container/${package}/versions"
        
        VERSIONS=$(curl -s -H "Authorization: Bearer ${GITHUB_TOKEN}" \
                        -H "Accept: application/vnd.github+json" \
                        "${VERSIONS_URL}")
        
<<<<<<< HEAD
        # Get all tags for all versions (not just latest)
        
=======
>>>>>>> c44a6e4 (feat: implement build determinism validation and complete image list generation)
        # Check if we should get all tags or just latest
        if [ "${ALL_TAGS}" = "false" ]; then
            TAGS=$(echo "${VERSIONS}" | jq -r '.[0].metadata.container.tags[0]' 2>/dev/null)
            log_info "Fetching latest tag only for ${package}"
        else
<<<<<<< HEAD
            log_info "Fetching all tags for ${package}"
        fi
        TAGS=$(echo "${VERSIONS}" | jq -r '.[].metadata.container.tags[]?' 2>/dev/null)
        
        if [ -z "${TAGS}" ]; then
            log_warn "No tags found for ${package}, using 'latest'"
            TAGS="latest"
        fi
        
        # Add all unique tags
        echo "${TAGS}" | sort -u | while read -r tag; do
=======
            TAGS=$(echo "${VERSIONS}" | jq -r '.[].metadata.container.tags[]?' 2>/dev/null)
            log_info "Fetching all tags for ${package}"
        fi
        
        if [ -z "${TAGS}" ] || [ "${TAGS}" = "null" ]; then
            log_warn "No tags found for ${package}, skipping"
            continue
        fi
        
        # Add all unique tags
        mapfile -t TAG_ARRAY < <(echo "${TAGS}" | sort -u)
        log_info "Found ${#TAG_ARRAY[@]} tag(s) for ${package}"
        
        for tag in "${TAG_ARRAY[@]}"; do
>>>>>>> c44a6e4 (feat: implement build determinism validation and complete image list generation)
            if [ "${tag}" != "null" ] && [ -n "${tag}" ]; then
                IMAGE="${OPENCENTER_CONTAINER_REGISTRY}/${package}:${tag}"
                echo "${IMAGE}" >> "${IMAGE_LIST}"
                log_info "Added: ${IMAGE}"
            fi
        done
    done
    
    # Remove duplicates and sort
    sort -u "${IMAGE_LIST}" -o "${IMAGE_LIST}"
    
    log_info "Image list saved to: ${IMAGE_LIST}"
}

# Pull container images
pull_opencenter_images() {
    log_info "Pulling openCenter container images..."
    
    if [ ! -f "${IMAGE_LIST}" ]; then
        log_warn "Image list not found: ${IMAGE_LIST}, skipping image pull"
        return 0
    fi
    
    if [ -z "${GITHUB_TOKEN:-}" ]; then
        log_error "GITHUB_TOKEN required to pull images"
        exit 1
    fi
    
    # Login to GitHub Container Registry
    log_info "Logging in to GitHub Container Registry..."
    if ! echo "${GITHUB_TOKEN}" | ${CONTAINER_RUNTIME} login ghcr.io -u USERNAME --password-stdin 2>&1 | tee -a "${BUILD_LOG:-/dev/null}"; then
        log_error "Failed to login to ghcr.io"
        return 1
    fi
    
    mkdir -p "${IMAGES_DIR}"
    
    # Pull each image
    while IFS= read -r image; do
        if [ -z "${image}" ]; then
            continue
        fi
        
        log_info "Pulling: ${image}"
        
        if ${CONTAINER_RUNTIME} pull "${image}" 2>&1 | tee -a "${BUILD_LOG:-/dev/null}"; then
            log_info "Successfully pulled: ${image}"
            
            # Save image as tar.gz
            IMAGE_NAME=$(echo "${image}" | sed 's|/|_|g' | sed 's|:|_|g')
            IMAGE_FILE="${IMAGES_DIR}/${IMAGE_NAME}.tar.gz"
            
            log_info "Saving to: ${IMAGE_FILE}"
            ${CONTAINER_RUNTIME} save "${image}" | gzip > "${IMAGE_FILE}"
        else
            log_warn "Failed to pull: ${image}, continuing..."
        fi
    done < "${IMAGE_LIST}"
    
    log_info "Images saved to: ${IMAGES_DIR}"
}

# Extract image references from GitOps manifests
extract_images_from_manifests() {
    log_info "Extracting image references from GitOps manifests..."
    
    if [ ! -d "${GITOPS_BASE_DIR}" ]; then
        log_warn "GitOps base directory not found, skipping manifest scan"
        return
    fi
    
    MANIFEST_IMAGES="${PROJECT_ROOT}/build/gitops-manifest-images.txt"
    > "${MANIFEST_IMAGES}"
    
    # Find all YAML files and extract image references
    find "${GITOPS_BASE_DIR}" -type f \( -name "*.yaml" -o -name "*.yml" \) | while read -r file; do
        # Extract image: lines
        grep -h "image:" "${file}" 2>/dev/null | \
            sed 's/.*image:[[:space:]]*//' | \
            sed 's/[[:space:]]*$//' | \
            sed 's/"//g' | \
            sed "s/'//g" | \
            grep -v "^#" | \
            grep -v "^$" >> "${MANIFEST_IMAGES}" || true
    done
    
    # Remove duplicates and sort
    if [ -f "${MANIFEST_IMAGES}" ]; then
        sort -u "${MANIFEST_IMAGES}" -o "${MANIFEST_IMAGES}"
        
        IMAGE_COUNT=$(wc -l < "${MANIFEST_IMAGES}")
        log_info "Found ${IMAGE_COUNT} unique images in manifests"
        log_info "Manifest images saved to: ${MANIFEST_IMAGES}"
    fi
}

# Merge image lists
merge_image_lists() {
    log_info "Merging image lists..."
    
    MERGED_LIST="${PROJECT_ROOT}/build/opencenter-images-merged.txt"
    > "${MERGED_LIST}"
    
    # Combine all image lists
    if [ -f "${IMAGE_LIST}" ]; then
        cat "${IMAGE_LIST}" >> "${MERGED_LIST}"
    fi
    
    if [ -f "${PROJECT_ROOT}/build/gitops-manifest-images.txt" ]; then
        cat "${PROJECT_ROOT}/build/gitops-manifest-images.txt" >> "${MERGED_LIST}"
    fi
    
    # Remove duplicates
    sort -u "${MERGED_LIST}" -o "${MERGED_LIST}"
    
    TOTAL_IMAGES=$(wc -l < "${MERGED_LIST}")
    log_info "Total unique images: ${TOTAL_IMAGES}"
    log_info "Merged list: ${MERGED_LIST}"
}

# Generate summary
generate_summary() {
    log_info "=== Collection Summary ==="
    
    if [ -d "${GITOPS_BASE_DIR}/.git" ]; then
        cd "${GITOPS_BASE_DIR}"
        COMMIT=$(git rev-parse --short HEAD)
        log_info "GitOps base: ${OPENCENTER_GITOPS_BASE_VERSION} (${COMMIT})"
    fi
    
    if [ -f "${IMAGE_LIST}" ]; then
        IMAGE_COUNT=$(wc -l < "${IMAGE_LIST}")
        log_info "Container images: ${IMAGE_COUNT}"
    fi
    
    if [ -d "${IMAGES_DIR}" ]; then
        SAVED_COUNT=$(find "${IMAGES_DIR}" -name "*.tar.gz" | wc -l)
        TOTAL_SIZE=$(du -sh "${IMAGES_DIR}" | cut -f1)
        log_info "Saved images: ${SAVED_COUNT} (${TOTAL_SIZE})"
    fi
}

# Main execution
main() {
    log_info "Starting openCenter asset collection..."
    
    check_prerequisites
    clone_gitops_base
    
    if fetch_opencenter_images; then
        log_info "Image list generated successfully"
    else
        log_error "Failed to generate image list"
        return 1
    fi
    
    if pull_opencenter_images; then
        log_info "Images pulled successfully"
    else
        log_warn "Image pull had errors, continuing..."
    fi
    
    extract_images_from_manifests
    merge_image_lists
    generate_summary
    
    log_info "openCenter asset collection complete!"
}

main "$@"

