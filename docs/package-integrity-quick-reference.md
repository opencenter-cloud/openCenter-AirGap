# Package Integrity Quick Reference

## Build Phase Commands

```bash
# After creating Zarf package
cd dist/

# Option 1: Complete workflow (recommended)
../scripts/build/package_integrity.sh all zarf-package-*.tar.zst

# Option 2: With signing
../scripts/build/package_integrity.sh all zarf-package-*.tar.zst -k /path/to/cosign.key

# Option 3: Individual steps
../scripts/build/package_integrity.sh generate zarf-package-*.tar.zst
../scripts/build/package_integrity.sh sign zarf-package-*.tar.zst -k cosign.key
../scripts/build/package_integrity.sh verify zarf-package-*.tar.zst
```

## Deployment Phase Commands

```bash
# On bastion, before deploying
cd /opt/packages/

# Verify package integrity
python3 /path/to/verify_package.py zarf-package-*.tar.zst

# If verification passes, deploy
zarf package deploy zarf-package-*.tar.zst --confirm
```

## Files to Transfer

**Required:**
- `zarf-package-*.tar.zst` (package)
- `zarf-package-*.tar.zst.checksums.json` (manifest)

**Optional (if signed):**
- `zarf-package-*.tar.zst.sig` (signature)
- `cosign.pub` (public key)

## Exit Codes

- `0` = Success
- `1` = Verification failed
- `130` = Interrupted by user

## Troubleshooting

**Checksum mismatch:**
```bash
# Re-transfer package from build system
scp build-host:dist/zarf-package-*.tar.zst* .
```

**Signature verification failed:**
```bash
# Verify you have the correct public key
ls -l cosign.pub

# Skip signature verification if needed
python3 verify_package.py zarf-package-*.tar.zst --skip-signature
```

**Manifest not found:**
```bash
# Specify manifest explicitly
python3 verify_package.py zarf-package-*.tar.zst -m /path/to/checksums.json
```

## Security Notes

- **SHA256** is the primary integrity check (cryptographically strong)
- **MD5** detects accidental corruption (fast but weak)
- **Cosign signature** provides authentication and non-repudiation
- Always verify before deploying in production
- Never skip verification in production environments
