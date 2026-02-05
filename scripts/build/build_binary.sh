#!/bin/bash
# Build standalone binary with PyInstaller
#
# This script builds the opencenter-airgap binary for Ubuntu 24.04 AMD64.
# The binary includes all Python dependencies and is self-contained.
#
# Requirements:
# - PyInstaller installed (pip install pyinstaller)
# - UPX installed (apt install upx-ucl) for compression
# - Build on Ubuntu 24.04 AMD64 for target compatibility
#
# Output:
# - dist/opencenter-airgap (standalone binary)
# - Size target: <25MB

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Building opencenter-airgap binary...${NC}"
echo

# Check PyInstaller is installed
if ! command -v pyinstaller &> /dev/null; then
    echo -e "${RED}Error: PyInstaller not found${NC}"
    echo "Install with: pip install pyinstaller"
    exit 1
fi

# Check UPX is installed (optional but recommended for size reduction)
if ! command -v upx &> /dev/null; then
    echo -e "${YELLOW}Warning: UPX not found - binary will be larger${NC}"
    echo "Install with: apt install upx-ucl"
    echo
fi

# Clean previous build
echo "Cleaning previous build..."
rm -rf build/ dist/opencenter-airgap
echo -e "${GREEN}✓${NC} Cleaned build directory"
echo

# Build binary
echo "Building binary with PyInstaller..."
pyinstaller opencenter-airgap.spec

if [ ! -f dist/opencenter-airgap ]; then
    echo -e "${RED}Error: Binary not created${NC}"
    exit 1
fi

echo -e "${GREEN}✓${NC} Binary created: dist/opencenter-airgap"
echo

# Check binary size
BINARY_SIZE=$(stat -f%z dist/opencenter-airgap 2>/dev/null || stat -c%s dist/opencenter-airgap)
BINARY_SIZE_MB=$((BINARY_SIZE / 1024 / 1024))

echo "Binary size: ${BINARY_SIZE_MB}MB"

if [ "$BINARY_SIZE_MB" -gt 25 ]; then
    echo -e "${YELLOW}Warning: Binary size exceeds 25MB target${NC}"
    echo "Consider:"
    echo "  - Installing UPX for compression"
    echo "  - Excluding more unused modules in spec file"
else
    echo -e "${GREEN}✓${NC} Binary size within 25MB target"
fi

echo

# Make binary executable
chmod +x dist/opencenter-airgap
echo -e "${GREEN}✓${NC} Binary is executable"
echo

# Test binary
echo "Testing binary..."
if dist/opencenter-airgap --help > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Binary executes successfully"
else
    echo -e "${RED}Error: Binary failed to execute${NC}"
    exit 1
fi

echo
echo -e "${GREEN}Build complete!${NC}"
echo
echo "Binary location: dist/opencenter-airgap"
echo "Test with: dist/opencenter-airgap --help"
echo "Test version: dist/opencenter-airgap version"
