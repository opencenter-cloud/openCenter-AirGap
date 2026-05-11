#!/bin/bash
# Shared download library with provenance tracking
#
# Provides download_artifact() as a drop-in replacement for raw curl calls.
# Every download is recorded in build/provenance/downloads.ndjson with:
#   - Original URL
#   - Resolved URL (after redirects)
#   - HTTP status code
#   - SHA256 checksum of downloaded file
#   - File size
#   - Timestamp
#
# Usage:
#   source scripts/lib/download.sh
#   init_provenance
#   download_artifact "https://example.com/file.tar.gz" "/dest/file.tar.gz"
#   download_artifact "https://example.com/bin" "/dest/bin" "https://example.com/bin.sha256"

set -euo pipefail

# Provenance output directory
PROVENANCE_DIR="${PROVENANCE_DIR:-build/provenance}"
PROVENANCE_FILE="${PROVENANCE_DIR}/downloads.ndjson"

# Initialize provenance tracking
# Creates the provenance directory and ensures the ndjson file exists.
init_provenance() {
    mkdir -p "${PROVENANCE_DIR}"
    # Touch file to ensure it exists for appending
    touch "${PROVENANCE_FILE}"
}

# Download a single artifact with provenance recording.
#
# Args:
#   $1: URL to download
#   $2: Destination path
#   $3: (optional) Checksum URL for verification
#   $4: (optional) Artifact name (defaults to basename of dest)
#
# Returns:
#   0 on success, 1 on failure
#
# Side effects:
#   Appends a JSON line to PROVENANCE_FILE
download_artifact() {
    local url="$1"
    local dest="$2"
    local checksum_url="${3:-}"
    local artifact_name="${4:-$(basename "${dest}")}"

    # Ensure provenance dir exists
    mkdir -p "${PROVENANCE_DIR}"

    local http_code=""
    local resolved_url=""
    local sha256=""
    local file_size=""
    local timestamp=""
    local checksum_verified="false"
    local download_success="true"

    timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)

    # Create destination directory
    mkdir -p "$(dirname "${dest}")"

    # Download with HTTP status capture
    http_code=$(curl -fsSL -o "${dest}" -w '%{http_code}' "${url}" 2>/dev/null) || {
        download_success="false"
        http_code="${http_code:-000}"
    }

    # Resolve effective URL (follows redirects)
    resolved_url=$(curl -fsSL -o /dev/null -w '%{url_effective}' "${url}" 2>/dev/null) || {
        resolved_url="${url}"
    }

    # Calculate SHA256 if file was downloaded
    if [[ -f "${dest}" ]]; then
        sha256=$(sha256sum "${dest}" 2>/dev/null | awk '{print $1}' || shasum -a 256 "${dest}" 2>/dev/null | awk '{print $1}' || echo "")
        file_size=$(stat -f%z "${dest}" 2>/dev/null || stat -c%s "${dest}" 2>/dev/null || echo "0")
    else
        sha256=""
        file_size="0"
    fi

    # Verify checksum if URL provided
    if [[ -n "${checksum_url}" && -f "${dest}" ]]; then
        local expected_checksum=""
        expected_checksum=$(curl -fsSL "${checksum_url}" 2>/dev/null | awk '{print $1}') || true

        if [[ -n "${expected_checksum}" && "${expected_checksum}" == "${sha256}" ]]; then
            checksum_verified="true"
        elif [[ -n "${expected_checksum}" ]]; then
            checksum_verified="false"
            download_success="false"
        fi
    fi

    # Write provenance record (JSON line)
    printf '{"artifact":"%s","url":"%s","resolved_url":"%s","dest":"%s","sha256":"%s","size_bytes":%s,"http_code":%s,"checksum_url":"%s","checksum_verified":%s,"success":%s,"timestamp":"%s"}\n' \
        "${artifact_name}" \
        "${url}" \
        "${resolved_url}" \
        "${dest}" \
        "${sha256}" \
        "${file_size}" \
        "${http_code}" \
        "${checksum_url}" \
        "${checksum_verified}" \
        "${download_success}" \
        "${timestamp}" \
        >> "${PROVENANCE_FILE}"

    if [[ "${download_success}" == "true" ]]; then
        return 0
    else
        return 1
    fi
}

# Download and extract a tar archive with provenance recording.
#
# Args:
#   $1: URL to download
#   $2: Destination directory for extraction
#   $3: (optional) tar extract arguments (e.g., specific file to extract)
#   $4: (optional) Artifact name
#   $5: (optional) Checksum URL
#
# Returns:
#   0 on success, 1 on failure
download_and_extract() {
    local url="$1"
    local dest_dir="$2"
    local tar_args="${3:-}"
    local artifact_name="${4:-$(basename "${url}")}"
    local checksum_url="${5:-}"

    local timestamp=""
    local http_code=""
    local resolved_url=""
    local download_success="true"

    timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)

    # Ensure provenance dir and dest dir exist
    mkdir -p "${PROVENANCE_DIR}"
    mkdir -p "${dest_dir}"

    # Download to temp file first for checksum calculation
    local tmp_file
    tmp_file=$(mktemp)
    trap "rm -f '${tmp_file}'" RETURN

    http_code=$(curl -fsSL -o "${tmp_file}" -w '%{http_code}' "${url}" 2>/dev/null) || {
        download_success="false"
        http_code="${http_code:-000}"
    }

    resolved_url=$(curl -fsSL -o /dev/null -w '%{url_effective}' "${url}" 2>/dev/null) || {
        resolved_url="${url}"
    }

    local sha256=""
    local file_size="0"

    if [[ -f "${tmp_file}" && -s "${tmp_file}" ]]; then
        sha256=$(sha256sum "${tmp_file}" 2>/dev/null | awk '{print $1}' || shasum -a 256 "${tmp_file}" 2>/dev/null | awk '{print $1}' || echo "")
        file_size=$(stat -f%z "${tmp_file}" 2>/dev/null || stat -c%s "${tmp_file}" 2>/dev/null || echo "0")

        # Extract
        if [[ -n "${tar_args}" ]]; then
            tar xz -C "${dest_dir}" ${tar_args} < "${tmp_file}" || download_success="false"
        else
            tar xz -C "${dest_dir}" < "${tmp_file}" || download_success="false"
        fi
    else
        download_success="false"
    fi

    # Write provenance record
    printf '{"artifact":"%s","url":"%s","resolved_url":"%s","dest":"%s","sha256":"%s","size_bytes":%s,"http_code":%s,"checksum_url":"%s","checksum_verified":false,"success":%s,"timestamp":"%s"}\n' \
        "${artifact_name}" \
        "${url}" \
        "${resolved_url}" \
        "${dest_dir}" \
        "${sha256}" \
        "${file_size}" \
        "${http_code}" \
        "${checksum_url}" \
        "${download_success}" \
        "${timestamp}" \
        >> "${PROVENANCE_FILE}"

    if [[ "${download_success}" == "true" ]]; then
        return 0
    else
        return 1
    fi
}

# Export functions for use in sourcing scripts
export -f init_provenance
export -f download_artifact
export -f download_and_extract
export PROVENANCE_DIR
export PROVENANCE_FILE
