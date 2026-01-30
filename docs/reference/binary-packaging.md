# Binary Packaging Reference

doc_type: reference

For platform engineers who need to build and distribute the opencenter-airgap standalone binary.

## Overview

The opencenter-airgap tool is packaged as a standalone binary using PyInstaller. The binary includes all Python dependencies and requires no Python installation on the target system.

## Binary Specifications

- **Name**: opencenter-airgap
- **Target OS**: Ubuntu 24.04 LTS
- **Architecture**: AMD64 (x86_64)
- **Size**: ~12MB (target: <25MB)
- **Format**: Single-file executable
- **Dependencies**: None (all included)

## Building the Binary

### Prerequisites

- Python 3.10+
- PyInstaller: `pip install pyinstaller`
- UPX (optional, for compression): `apt install upx-ucl`

### Build Process

```bash
# Install PyInstaller
pip install pyinstaller

# Build binary
pyinstaller opencenter-airgap.spec

# Output location
ls -lh dist/opencenter-airgap
```

### Build Script

Use the provided build script for automated building:

```bash
./scripts/build/build_binary.sh
```

The script:
1. Checks prerequisites
2. Cleans previous builds
3. Runs PyInstaller
4. Verifies binary size
5. Tests binary execution

## Spec File Configuration

The `opencenter-airgap.spec` file configures PyInstaller:

### Entry Point

```python
a = Analysis(
    [str(src_path / "opencenter_build" / "cli.py")],
    pathex=[str(src_path)],
    ...
)
```

### Hidden Imports

Modules that PyInstaller might miss:

```python
hiddenimports=[
    "opencenter_build",
    "opencenter_build.cli",
    "opencenter_build.config",
    "opencenter_build.state",
    "opencenter_build.scanner",
    "opencenter_build.orchestrator",
    "opencenter_build.zarf_generator",
    "opencenter_build.manifest",
    "opencenter_build.validation",
    "opencenter_build.verifier",
    "opencenter_build.component_manifest",
    "typer",
    "rich",
    "yaml",
    "jsonschema",
    "dotenv",
]
```

### Excluded Modules

Modules excluded to reduce size:

```python
excludes=[
    "pytest",
    "hypothesis",
    "unittest",
    "black",
    "mypy",
    "pylint",
    "tkinter",
    "pdb",
]
```

### Optimization

```python
optimize=2,        # Python bytecode optimization
strip=True,        # Strip symbols
upx=True,          # UPX compression
onefile=True,      # Single-file bundle
```

## Testing the Binary

### Unit Tests

Run binary tests:

```bash
pytest tests/unit/test_binary.py -v
```

Tests verify:
- Binary exists and is executable
- Size is under 25MB
- All commands are available
- Version output is correct
- Binary runs without Python in PATH
- All dependencies are included

### Manual Testing

```bash
# Test help
dist/opencenter-airgap --help

# Test version
dist/opencenter-airgap version

# Test command help
dist/opencenter-airgap init --help
dist/opencenter-airgap scan --help
dist/opencenter-airgap build --help
```

## Distribution

### Package the Binary

```bash
# Create tarball
tar -czf opencenter-airgap-1.0.0-linux-amd64.tar.gz \
    -C dist opencenter-airgap

# Create checksum
sha256sum opencenter-airgap-1.0.0-linux-amd64.tar.gz > \
    opencenter-airgap-1.0.0-linux-amd64.tar.gz.sha256
```

### Installation on Target System

```bash
# Extract binary
tar -xzf opencenter-airgap-1.0.0-linux-amd64.tar.gz

# Move to system path
sudo mv opencenter-airgap /usr/local/bin/

# Verify installation
opencenter-airgap version
```

## Troubleshooting

### Binary Size Exceeds 25MB

1. Install UPX: `apt install upx-ucl`
2. Add more modules to `excludes` in spec file
3. Remove unused encodings

### Missing Dependencies

Add to `hiddenimports` in spec file:

```python
hiddenimports=[
    "missing_module",
]
```

### Binary Fails to Execute

Check for:
- Missing shared libraries: `ldd dist/opencenter-airgap`
- Architecture mismatch: Build on target OS
- Permission issues: `chmod +x dist/opencenter-airgap`

### Import Errors at Runtime

PyInstaller may miss dynamic imports. Add to `hiddenimports`:

```python
hiddenimports=[
    "dynamically_imported_module",
]
```

## Platform-Specific Notes

### Ubuntu 24.04

- Build on Ubuntu 24.04 for best compatibility
- Requires glibc 2.39+
- No additional dependencies needed

### macOS (Development)

- Binary built on macOS targets macOS only
- For Linux targets, build on Linux or use Docker
- Architecture: arm64 (Apple Silicon) or x86_64 (Intel)

### Docker Build (Cross-Platform)

```dockerfile
FROM ubuntu:24.04

RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    upx-ucl

WORKDIR /build
COPY . .

RUN pip install pyinstaller
RUN pyinstaller opencenter-airgap.spec

CMD ["cp", "dist/opencenter-airgap", "/output/"]
```

Build:

```bash
docker build -t opencenter-airgap-builder .
docker run -v $(pwd)/output:/output opencenter-airgap-builder
```

## Continuous Integration

### GitHub Actions Example

```yaml
name: Build Binary

on:
  push:
    tags:
      - 'v*'

jobs:
  build:
    runs-on: ubuntu-24.04

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          pip install pyinstaller
          sudo apt-get install -y upx-ucl

      - name: Build binary
        run: pyinstaller opencenter-airgap.spec

      - name: Test binary
        run: |
          dist/opencenter-airgap --help
          dist/opencenter-airgap version

      - name: Package binary
        run: |
          tar -czf opencenter-airgap-${{ github.ref_name }}-linux-amd64.tar.gz \
              -C dist opencenter-airgap
          sha256sum opencenter-airgap-${{ github.ref_name }}-linux-amd64.tar.gz > \
              opencenter-airgap-${{ github.ref_name }}-linux-amd64.tar.gz.sha256

      - name: Upload artifacts
        uses: actions/upload-artifact@v4
        with:
          name: opencenter-airgap-binary
          path: |
            opencenter-airgap-*.tar.gz
            opencenter-airgap-*.tar.gz.sha256
```

## Version Management

Binary version is read from `src/opencenter_build/__init__.py`:

```python
__version__ = "1.0.0"
```

Update version:
1. Edit `__version__` in `__init__.py`
2. Rebuild binary
3. Verify: `dist/opencenter-airgap version`

## Security Considerations

- Binary includes all dependencies (no external downloads)
- Verify checksums before distribution
- Sign binary with GPG or Cosign
- Scan binary for vulnerabilities

### Signing the Binary

```bash
# GPG signing
gpg --detach-sign --armor dist/opencenter-airgap

# Cosign signing
cosign sign-blob --key cosign.key dist/opencenter-airgap > opencenter-airgap.sig
```

### Verification

```bash
# GPG verification
gpg --verify dist/opencenter-airgap.asc dist/opencenter-airgap

# Cosign verification
cosign verify-blob --key cosign.pub --signature opencenter-airgap.sig dist/opencenter-airgap
```
