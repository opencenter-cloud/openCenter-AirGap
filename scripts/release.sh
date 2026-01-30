#!/usr/bin/env bash
# Release script for opencenter-airgap
# Creates a git tag and pushes to trigger GitHub Actions release workflow

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Colors
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

usage() {
    cat <<EOF
Usage: $0 [VERSION]

Create a release tag for opencenter-airgap.

Arguments:
  VERSION    Version to release (e.g., 1.0.0 or v1.0.0)
             If omitted, reads from pyproject.toml

Examples:
  $0 1.0.0
  $0 v1.0.1
  $0  # Uses version from pyproject.toml

EOF
    exit 1
}

get_current_version() {
    grep '^version = ' "${PROJECT_ROOT}/pyproject.toml" | cut -d'"' -f2
}

validate_version() {
    local version="$1"
    if [[ ! "$version" =~ ^v?[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        log_error "Invalid version format: $version"
        log_error "Expected format: X.Y.Z or vX.Y.Z"
        exit 1
    fi
}

check_git_status() {
    if [[ -n "$(git status --porcelain)" ]]; then
        log_error "Working directory is not clean. Commit or stash changes first."
        git status --short
        exit 1
    fi
}

check_remote() {
    if ! git remote get-url origin &>/dev/null; then
        log_error "No git remote 'origin' configured"
        exit 1
    fi
}

tag_exists() {
    local tag="$1"
    git tag -l "$tag" | grep -q "^${tag}$"
}

main() {
    cd "${PROJECT_ROOT}"

    # Parse arguments
    local version="${1:-}"
    if [[ -z "$version" ]]; then
        version="$(get_current_version)"
        log_info "Using version from pyproject.toml: $version"
    fi

    # Normalize version (add 'v' prefix if missing)
    if [[ ! "$version" =~ ^v ]]; then
        version="v${version}"
    fi

    validate_version "$version"
    check_git_status
    check_remote

    # Check if tag already exists
    if tag_exists "$version"; then
        log_error "Tag $version already exists"
        log_info "Existing tags:"
        git tag -l "v*" | tail -5
        exit 1
    fi

    # Confirm release
    log_info "Creating release: $version"
    log_info "Current branch: $(git branch --show-current)"
    log_info "Latest commit: $(git log -1 --oneline)"
    echo
    read -p "Continue? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_warn "Release cancelled"
        exit 0
    fi

    # Create and push tag
    log_info "Creating tag: $version"
    git tag -a "$version" -m "Release $version"

    log_info "Pushing tag to origin"
    git push origin "$version"

    log_info "Release tag created successfully"
    log_info "GitHub Actions will build and publish the release"
    log_info "Monitor progress: https://github.com/$(git remote get-url origin | sed 's/.*github.com[:/]\(.*\)\.git/\1/')/actions"
}

if [[ "${1:-}" == "-h" ]] || [[ "${1:-}" == "--help" ]]; then
    usage
fi

main "$@"
