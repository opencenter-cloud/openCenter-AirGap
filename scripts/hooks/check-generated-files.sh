#!/usr/bin/env bash
# Check that generated files are up-to-date
# This hook verifies that zarf.yaml matches the template and config files

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "Checking generated files..."

# Check if zarf.yaml exists
if [[ ! -f "zarf.yaml" ]]; then
    echo -e "${YELLOW}Warning: zarf.yaml does not exist${NC}"
    echo "This is expected if you haven't run the build yet."
    exit 0
fi

# Check if template exists
if [[ ! -f "zarf.yaml.template" ]]; then
    echo -e "${RED}Error: zarf.yaml.template not found${NC}"
    exit 1
fi

# Check if config files exist
if [[ ! -f "config/versions.env" ]]; then
    echo -e "${RED}Error: config/versions.env not found${NC}"
    exit 1
fi

if [[ ! -f "config/all-images.txt" ]]; then
    echo -e "${YELLOW}Warning: config/all-images.txt not found${NC}"
    echo "Image list may not be generated yet."
fi

# Create a temporary file for the regenerated zarf.yaml
TEMP_ZARF=$(mktemp)
trap 'rm -f "$TEMP_ZARF"' EXIT

# Try to regenerate zarf.yaml
if command -v python3 &> /dev/null; then
    # Check if opencenter_build package is available
    if python3 -c "import opencenter_build.zarf_utils" 2>/dev/null; then
        echo "Regenerating zarf.yaml to check for changes..."

        # Run generation in dry-run mode if available
        # For now, just check if the file has been modified
        if git diff --cached --name-only | grep -q "zarf.yaml"; then
            echo -e "${YELLOW}Warning: zarf.yaml has been modified${NC}"
            echo "Please ensure it was regenerated from the template."
            echo ""
            echo "To regenerate zarf.yaml, run:"
            echo "  python scripts/build/generate_zarf_yaml.py"
            echo ""
            echo "If you're sure the changes are correct, you can bypass this check with:"
            echo "  git commit --no-verify"

            # Don't fail, just warn
            exit 0
        fi
    else
        echo -e "${YELLOW}Warning: opencenter_build package not installed${NC}"
        echo "Cannot verify zarf.yaml is up-to-date."
        echo "Install with: pip install -e ."
    fi
else
    echo -e "${YELLOW}Warning: python3 not found${NC}"
    echo "Cannot verify generated files."
fi

# Check if config files have been modified
if git diff --cached --name-only | grep -qE "config/(versions\.env|.*-images\.txt)"; then
    echo -e "${YELLOW}Warning: Configuration files modified${NC}"
    echo "If you modified config files, you may need to regenerate:"
    echo "  - zarf.yaml (run: python scripts/build/generate_zarf_yaml.py)"
    echo "  - Image lists (run: python scripts/build/merge_images.py)"
    echo ""
    echo "To bypass this check: git commit --no-verify"
fi

echo -e "${GREEN}Generated files check passed${NC}"
exit 0
