#!/bin/bash
# validate_package_script.sh
# Validates the package build script logic without requiring Zarf

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

echo "Validating package build script..."

# Check script exists and is executable
if [ ! -x "${SCRIPT_DIR}/create_zarf_package.sh" ]; then
    echo "ERROR: create_zarf_package.sh not found or not executable"
    exit 1
fi
echo "✓ Script exists and is executable"

# Check zarf.yaml exists
if [ ! -f "${PROJECT_ROOT}/zarf.yaml" ]; then
    echo "ERROR: zarf.yaml not found"
    exit 1
fi
echo "✓ zarf.yaml exists"

# Check assets directory exists
if [ ! -d "${PROJECT_ROOT}/assets" ]; then
    echo "ERROR: assets directory not found"
    exit 1
fi
echo "✓ assets directory exists"

# Verify zarf.yaml structure
if ! grep -q "kind: ZarfPackageConfig" "${PROJECT_ROOT}/zarf.yaml"; then
    echo "ERROR: zarf.yaml missing ZarfPackageConfig kind"
    exit 1
fi
echo "✓ zarf.yaml has correct kind"

# Check for required components in zarf.yaml
required_components=("bootstrap-tools" "kubespray-core" "k8s-images" "deploy-cluster")
for comp in "${required_components[@]}"; do
    if ! grep -q "name: ${comp}" "${PROJECT_ROOT}/zarf.yaml"; then
        echo "ERROR: Component ${comp} not found in zarf.yaml"
        exit 1
    fi
done
echo "✓ All required components present in zarf.yaml"

# Check dist directory can be created
mkdir -p "${PROJECT_ROOT}/dist"
if [ ! -d "${PROJECT_ROOT}/dist" ]; then
    echo "ERROR: Cannot create dist directory"
    exit 1
fi
echo "✓ dist directory accessible"

# Verify script has all required functions
required_functions=("check_prerequisites" "prepare_dist_dir" "create_package" "verify_package" "generate_checksums")
for func in "${required_functions[@]}"; do
    if ! grep -q "^${func}()" "${SCRIPT_DIR}/create_zarf_package.sh"; then
        echo "ERROR: Function ${func} not found in script"
        exit 1
    fi
done
echo "✓ All required functions present"

# Check script has proper error handling
if ! grep -q "set -euo pipefail" "${SCRIPT_DIR}/create_zarf_package.sh"; then
    echo "ERROR: Script missing error handling (set -euo pipefail)"
    exit 1
fi
echo "✓ Script has proper error handling"

# Verify checksum generation logic
if ! grep -q "md5sum" "${SCRIPT_DIR}/create_zarf_package.sh"; then
    echo "ERROR: MD5 checksum generation missing"
    exit 1
fi
if ! grep -q "sha256sum" "${SCRIPT_DIR}/create_zarf_package.sh"; then
    echo "ERROR: SHA256 checksum generation missing"
    exit 1
fi
echo "✓ Checksum generation logic present"

# Verify size check logic
if ! grep -q "MAX_PACKAGE_SIZE_GB" "${SCRIPT_DIR}/create_zarf_package.sh"; then
    echo "ERROR: Package size check missing"
    exit 1
fi
echo "✓ Package size validation present"

# Verify SBOM check logic
if ! grep -q "sbom" "${SCRIPT_DIR}/create_zarf_package.sh"; then
    echo "ERROR: SBOM verification missing"
    exit 1
fi
echo "✓ SBOM verification logic present"

echo ""
echo "========================================="
echo "Validation complete!"
echo "========================================="
echo ""
echo "Package build script is correctly structured."
echo "All required functions and checks are present."
echo ""
echo "Note: Actual package creation requires Zarf CLI to be installed."
echo "Install Zarf: https://docs.zarf.dev/getting-started/install/"
