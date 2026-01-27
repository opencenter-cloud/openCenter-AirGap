#!/bin/bash
#
# Test script for build.py
# Verifies the build script's basic functionality without running full build
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_SCRIPT="${SCRIPT_DIR}/build.py"

echo "Testing build.py script..."
echo ""

# Test 1: Script exists
echo "Test 1: Script exists"
if [ -f "$BUILD_SCRIPT" ]; then
    echo "  ✓ PASS: Script exists"
else
    echo "  ✗ FAIL: Script not found"
    exit 1
fi

# Test 2: Python syntax check
echo "Test 2: Python syntax check"
if python3 -m py_compile "$BUILD_SCRIPT" 2>/dev/null; then
    echo "  ✓ PASS: Syntax is valid"
else
    echo "  ✗ FAIL: Syntax errors found"
    exit 1
fi

# Test 3: Help output
echo "Test 3: Help output"
if python3 "$BUILD_SCRIPT" --help > /dev/null 2>&1; then
    echo "  ✓ PASS: Help output works"
else
    echo "  ✗ FAIL: Help output failed"
    exit 1
fi

# Test 4: Invalid option handling
echo "Test 4: Invalid option handling"
if python3 "$BUILD_SCRIPT" --invalid-option > /dev/null 2>&1; then
    echo "  ✗ FAIL: Should reject invalid options"
    exit 1
else
    echo "  ✓ PASS: Invalid options rejected"
fi

# Test 5: Check required modules exist
echo "Test 5: Check required modules exist"
required_modules=(
    "build_state.py"
    "build_steps.py"
    "build_executor.py"
)

all_found=true
for module in "${required_modules[@]}"; do
    if [ -f "${SCRIPT_DIR}/${module}" ]; then
        echo "  ✓ Found: ${module}"
    else
        echo "  ✗ Missing: ${module}"
        all_found=false
    fi
done

if [ "$all_found" = true ]; then
    echo "  ✓ PASS: All required modules found"
else
    echo "  ✗ FAIL: Some required modules missing"
    exit 1
fi

# Test 6: Check Python version
echo "Test 6: Check Python version"
if command -v python3 &> /dev/null; then
    python_version=$(python3 --version 2>&1 | awk '{print $2}')
    major=$(echo "$python_version" | cut -d. -f1)
    minor=$(echo "$python_version" | cut -d. -f2)
    
    if [ "$major" -ge 3 ] && [ "$minor" -ge 12 ]; then
        echo "  ✓ PASS: Python $python_version (3.12+ required)"
    else
        echo "  ✗ FAIL: Python $python_version (3.12+ required)"
        exit 1
    fi
else
    echo "  ✗ FAIL: Python not found"
    exit 1
fi

echo ""
echo "All tests passed! ✓"
echo ""
echo "Note: This only tests basic functionality."
echo "Full build requires:"
echo "  - Internet connectivity"
echo "  - 100GB+ disk space"
echo "  - Zarf CLI installed"
echo "  - Container runtime (podman/docker)"
echo "  - Git, jq, skopeo"
