#!/bin/bash
#
# Test script for build.sh
# Verifies the build script's basic functionality without running full build
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_SCRIPT="${SCRIPT_DIR}/build.sh"

echo "Testing build.sh script..."
echo ""

# Test 1: Script exists and is executable
echo "Test 1: Script exists and is executable"
if [ -f "$BUILD_SCRIPT" ] && [ -x "$BUILD_SCRIPT" ]; then
    echo "  ✓ PASS: Script exists and is executable"
else
    echo "  ✗ FAIL: Script not found or not executable"
    exit 1
fi

# Test 2: Syntax check
echo "Test 2: Bash syntax check"
if bash -n "$BUILD_SCRIPT"; then
    echo "  ✓ PASS: Syntax is valid"
else
    echo "  ✗ FAIL: Syntax errors found"
    exit 1
fi

# Test 3: Help output
echo "Test 3: Help output"
if "$BUILD_SCRIPT" --help > /dev/null 2>&1; then
    echo "  ✓ PASS: Help output works"
else
    echo "  ✗ FAIL: Help output failed"
    exit 1
fi

# Test 4: Invalid option handling
echo "Test 4: Invalid option handling"
if "$BUILD_SCRIPT" --invalid-option > /dev/null 2>&1; then
    echo "  ✗ FAIL: Should reject invalid options"
    exit 1
else
    echo "  ✓ PASS: Invalid options rejected"
fi

# Test 5: Check required scripts exist
echo "Test 5: Check required scripts exist"
required_scripts=(
    "organize_assets_for_zarf.sh"
    "version_validator.py"
    "generate_zarf_yaml.py"
    "create_zarf_package.sh"
    "checksum_utils.py"
)

all_found=true
for script in "${required_scripts[@]}"; do
    if [ -f "${SCRIPT_DIR}/${script}" ]; then
        echo "  ✓ Found: ${script}"
    else
        echo "  ✗ Missing: ${script}"
        all_found=false
    fi
done

if [ "$all_found" = true ]; then
    echo "  ✓ PASS: All required scripts found"
else
    echo "  ✗ FAIL: Some required scripts missing"
    exit 1
fi

# Test 6: Check Python availability
echo "Test 6: Check Python availability"
if command -v python3 &> /dev/null; then
    python_version=$(python3 --version 2>&1 | awk '{print $2}')
    echo "  ✓ PASS: Python found (version: $python_version)"
else
    echo "  ✗ FAIL: Python not found"
    exit 1
fi

echo ""
echo "All tests passed! ✓"
echo ""
echo "Note: This only tests basic functionality."
echo "Full build requires:"
echo "  - kubespray-offline cloned to build/kubespray-offline/"
echo "  - Internet connectivity"
echo "  - 50GB+ disk space"
echo "  - Zarf CLI installed"
