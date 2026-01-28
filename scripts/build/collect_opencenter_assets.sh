#!/bin/bash
set -euo pipefail

# Collect openCenter-specific assets (GitOps base and container images)
# Requires GITHUB_TOKEN environment variable for private packages

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Source version configuration
source "${PROJECT_ROOT}/config/versions.env"

# Options
ALL_TAGS="${ALL_TAGS:-false}"  # Set to true to pull all version tags (slow, may hit rate limits)
# Output directories
GITOPS_BASE_DIR="${PROJECT_ROOT}/assets/opencenter-gitops-base"
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

    if ! command -v skopeo &> /dev/null; then
        log_error "skopeo is not installed"
        log_error "Install: apt-get install skopeo (Ubuntu/Debian) or dnf install skopeo (Fedora/RHEL)"
        exit 1
    fi

    log_info "Using skopeo: $(skopeo --version | head -1)"

    if ! command -v jq &> /dev/null; then
        log_error "jq is not installed"
        exit 1
    fi

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
    if [ "${SKIP_OPENCENTER_PRIVATE_REGISTRY:-false}" = "true" ]; then
        log_info "Skipping ghcr.io/opencenter-cloud private registry image list"
        return 0
    fi

    log_info "Fetching openCenter container image list..."

    if [ -z "${GITHUB_TOKEN:-}" ]; then
        log_error "GITHUB_TOKEN required to list packages from ghcr.io/opencenter-cloud"
        log_error "Set GITHUB_TOKEN or use SKIP_OPENCENTER_PRIVATE_REGISTRY=true"
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

        # Check if we should get all tags or just latest
        if [ "${ALL_TAGS}" = "false" ]; then
            TAGS=$(echo "${VERSIONS}" | jq -r '.[0].metadata.container.tags[0]' 2>/dev/null)
            log_info "Fetching latest tag only for ${package}"
        else
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

# Copy OCI artifacts (Helm charts) using skopeo
copy_oci_artifacts() {
    if [ "${SKIP_OPENCENTER_PRIVATE_REGISTRY:-false}" = "true" ]; then
        log_info "Skipping ghcr.io/opencenter-cloud private registry OCI artifacts"
        return 0
    fi

    log_info "Copying OCI artifacts (Helm charts) using skopeo..."

    if [ ! -f "${IMAGE_LIST}" ]; then
        log_warn "Image list not found: ${IMAGE_LIST}, skipping OCI artifact copy"
        return 0
    fi

    if [ -z "${GITHUB_TOKEN:-}" ]; then
        log_error "GITHUB_TOKEN required to copy OCI artifacts from ghcr.io/opencenter-cloud"
        log_error "Set GITHUB_TOKEN or use SKIP_OPENCENTER_PRIVATE_REGISTRY=true"
        exit 1
    fi

    mkdir -p "${IMAGES_DIR}"

    local copied_count=0
    local failed_count=0
    local skipped_count=0

    # Copy each OCI artifact
    while IFS= read -r image; do
        if [ -z "${image}" ]; then
            continue
        fi

        # Skip non-opencenter-cloud images
        if [[ ! "${image}" =~ ^ghcr\.io/opencenter-cloud/ ]]; then
            log_info "Skipping non-private image: ${image}"
            ((skipped_count++))
            continue
        fi

        log_info "Inspecting: ${image}"

        # Inspect to determine artifact type
        if ! skopeo inspect --creds="USERNAME:${GITHUB_TOKEN}" "docker://${image}" 2>&1 | tee -a "${BUILD_LOG:-/dev/null}"; then
            log_warn "Failed to inspect: ${image}, skipping..."
            ((failed_count++))
            continue
        fi

        # Extract artifact name for directory structure
        IMAGE_NAME=$(echo "${image}" | sed 's|ghcr.io/opencenter-cloud/||' | sed 's|:|_|g')
        ARTIFACT_DIR="${IMAGES_DIR}/${IMAGE_NAME}"

        log_info "Copying to: ${ARTIFACT_DIR}"

        # Copy using skopeo to OCI layout directory
        if skopeo copy \
            --src-creds="USERNAME:${GITHUB_TOKEN}" \
            --dest-oci-accept-uncompressed-layers \
            "docker://${image}" \
            "oci:${ARTIFACT_DIR}:latest" 2>&1 | tee -a "${BUILD_LOG:-/dev/null}"; then
            log_info "Successfully copied: ${image}"
            ((copied_count++))
        else
            log_warn "Failed to copy: ${image}, continuing..."
            ((failed_count++))
        fi
    done < "${IMAGE_LIST}"

    log_info "OCI artifacts - copied: ${copied_count}, failed: ${failed_count}, skipped: ${skipped_count}"
    log_info "Artifacts saved to: ${IMAGES_DIR}"
}

# Pull container images
pull_opencenter_images() {
    log_info "Skipping direct image pull - using skopeo for OCI artifacts"
    log_info "Reason: GitHub packages contain Helm charts (OCI artifacts)"
    log_info "Container images will be collected from GitOps manifests instead"

    if [ ! -f "${IMAGE_LIST}" ]; then
        log_info "No image list to process"
        return 0
    fi

    log_info "Image list available at: ${IMAGE_LIST}"

    return 0
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
        SAVED_COUNT=$(find "${IMAGES_DIR}" -type d -name "index.json" | wc -l)
        TOTAL_SIZE=$(du -sh "${IMAGES_DIR}" 2>/dev/null | cut -f1)
        log_info "Saved OCI artifacts: ${SAVED_COUNT} (${TOTAL_SIZE})"
    fi
}

# Check if step already completed (idempotency)
check_completion_marker() {
    local marker_file="${PROJECT_ROOT}/build/.completed/collect_opencenter_assets"

    if [ -f "${marker_file}" ]; then
        log_info "Step already completed (marker found: ${marker_file})"
        log_info "Skipping openCenter asset collection"
        log_info "To force re-run, delete: ${marker_file}"
        return 0  # Already completed
    fi

    return 1  # Not completed
}

# Create completion marker
create_completion_marker() {
    local marker_dir="${PROJECT_ROOT}/build/.completed"
    local marker_file="${marker_dir}/collect_opencenter_assets"

    mkdir -p "${marker_dir}"
    date -Iseconds > "${marker_file}"

    log_info "Created completion marker: ${marker_file}"
}

# Main execution
main() {
    log_info "Starting openCenter asset collection..."

    # Check if already completed
    if check_completion_marker; then
        exit 0
    fi

    check_prerequisites
    clone_gitops_base

    if fetch_opencenter_images; then
        log_info "Helm chart list generated successfully"
    else
        log_error "Failed to generate Helm chart list"
        return 1
    fi

    # Copy OCI artifacts using skopeo
    if copy_oci_artifacts; then
        log_info "OCI artifacts copied successfully"
    else
        log_warn "OCI artifact copy had errors, continuing..."
    fi

    extract_images_from_manifests
    merge_image_lists
    generate_summary

    # Create completion marker on success
    create_completion_marker

    log_info "openCenter asset collection complete!"
}

main "$@"
