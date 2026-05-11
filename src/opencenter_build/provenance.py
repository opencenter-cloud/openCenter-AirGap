"""SLSA Provenance attestation generator.

Produces an in-toto Statement v1 with SLSA Provenance v1 predicate,
conforming to https://slsa.dev/spec/v1.0/provenance.

The attestation links the final Zarf package (subject) to all resolved
dependencies (artifacts collected during build), build environment metadata,
and timing information.

This provides a machine-verifiable, standards-compliant provenance document
suitable for security audits and supply chain verification.
"""

import hashlib
import json
import os
import platform
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from opencenter_build.downloader import ProvenanceLog


# SLSA/in-toto type URIs
INTOTO_STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
SLSA_PROVENANCE_TYPE = "https://slsa.dev/provenance/v1"
BUILD_TYPE = "https://opencenter.io/airgap-build/v1"
BUILDER_ID = "https://opencenter.io/airgap-builder/v1"


@dataclass
class ProvenanceSubject:
    """Package subject for the attestation.

    Attributes:
        name: Package filename
        sha256: SHA256 digest of the package
        sha512: SHA512 digest of the package (optional)
    """

    name: str
    sha256: str
    sha512: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to in-toto subject format."""
        digest: dict[str, str] = {"sha256": self.sha256}
        if self.sha512:
            digest["sha512"] = self.sha512
        return {"name": self.name, "digest": digest}


@dataclass
class ResolvedDependency:
    """A single resolved dependency in the build.

    Attributes:
        uri: Canonical URI for the dependency (download URL or git+URL)
        digest: Content digest (sha256, gitCommit, etc.)
        name: Human-readable name
        download_location: Actual URL used to fetch the artifact
        media_type: MIME type if known
    """

    uri: str
    digest: dict[str, str]
    name: str
    download_location: str = ""
    media_type: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to SLSA resolvedDependencies format."""
        dep: dict[str, Any] = {
            "uri": self.uri,
            "digest": self.digest,
            "name": self.name,
        }
        if self.download_location:
            dep["downloadLocation"] = self.download_location
        if self.media_type:
            dep["mediaType"] = self.media_type
        return dep


@dataclass
class BuildMetadata:
    """Build execution metadata.

    Attributes:
        invocation_id: Unique build identifier
        started_on: Build start time (ISO 8601)
        finished_on: Build finish time (ISO 8601)
    """

    invocation_id: str
    started_on: str = ""
    finished_on: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to SLSA runDetails.metadata format."""
        meta: dict[str, Any] = {"invocationId": self.invocation_id}
        if self.started_on:
            meta["startedOn"] = self.started_on
        if self.finished_on:
            meta["finishedOn"] = self.finished_on
        return meta


@dataclass
class SLSAProvenance:
    """Complete SLSA Provenance v1 attestation.

    Attributes:
        subjects: Package files being attested
        dependencies: All resolved build dependencies
        build_metadata: Build timing and identification
        build_config: Build configuration parameters
        builder_version: Version of the build tool
    """

    subjects: list[ProvenanceSubject] = field(default_factory=list)
    dependencies: list[ResolvedDependency] = field(default_factory=list)
    build_metadata: BuildMetadata | None = None
    build_config: dict[str, Any] = field(default_factory=dict)
    builder_version: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to complete in-toto Statement v1 format."""
        return {
            "_type": INTOTO_STATEMENT_TYPE,
            "subject": [s.to_dict() for s in self.subjects],
            "predicateType": SLSA_PROVENANCE_TYPE,
            "predicate": {
                "buildDefinition": {
                    "buildType": BUILD_TYPE,
                    "externalParameters": self.build_config,
                    "resolvedDependencies": [
                        d.to_dict() for d in self.dependencies
                    ],
                    "internalParameters": {
                        "platform": platform.platform(),
                        "python_version": platform.python_version(),
                        "hostname": platform.node(),
                    },
                },
                "runDetails": {
                    "builder": {
                        "id": BUILDER_ID,
                        "version": {"opencenter-airgap": self.builder_version},
                    },
                    "metadata": (
                        self.build_metadata.to_dict()
                        if self.build_metadata
                        else {}
                    ),
                },
            },
        }


class ProvenanceGenerator:
    """Generates SLSA provenance attestations from build artifacts.

    Combines data from:
    - The provenance download log (build/provenance/downloads.ndjson)
    - The final Zarf package (subject)
    - Build configuration (config/versions.env)
    - Git state (commit SHA, branch)
    """

    def __init__(
        self,
        provenance_dir: Path | None = None,
        project_root: Path | None = None,
    ) -> None:
        """Initialize generator.

        Args:
            provenance_dir: Directory containing provenance log.
                Defaults to build/provenance/.
            project_root: Project root directory.
                Defaults to current working directory.
        """
        if provenance_dir is None:
            provenance_dir = Path("build/provenance")
        if project_root is None:
            project_root = Path.cwd()

        self.provenance_dir = provenance_dir
        self.project_root = project_root
        self.log = ProvenanceLog(provenance_dir)

    def generate(
        self,
        package_path: Path,
        build_id: str | None = None,
        started_on: str | None = None,
        versions_env: dict[str, str] | None = None,
    ) -> SLSAProvenance:
        """Generate SLSA provenance for a Zarf package.

        Args:
            package_path: Path to the final Zarf package
            build_id: Build identifier (auto-generated if not provided)
            started_on: Build start time ISO string
            versions_env: Build configuration from versions.env

        Returns:
            Complete SLSAProvenance attestation
        """
        finished_on = datetime.now(timezone.utc).isoformat()

        if build_id is None:
            build_id = f"build-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

        if started_on is None:
            started_on = finished_on

        provenance = SLSAProvenance()

        # Subject: the Zarf package
        provenance.subjects = [self._create_subject(package_path)]

        # Dependencies: from provenance log
        provenance.dependencies = self._collect_dependencies()

        # Build metadata
        provenance.build_metadata = BuildMetadata(
            invocation_id=build_id,
            started_on=started_on,
            finished_on=finished_on,
        )

        # Build config
        provenance.build_config = self._build_config(versions_env)

        # Builder version
        provenance.builder_version = self._get_tool_version()

        return provenance

    def export(
        self,
        provenance: SLSAProvenance,
        output_path: Path | None = None,
    ) -> Path:
        """Export provenance attestation to JSON file.

        Args:
            provenance: Provenance attestation to export
            output_path: Output file path. Defaults to
                dist/<package>.provenance.json

        Returns:
            Path to written file
        """
        if output_path is None:
            output_path = self.provenance_dir / "provenance.json"

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(provenance.to_dict(), f, indent=2)

        return output_path

    def _create_subject(self, package_path: Path) -> ProvenanceSubject:
        """Create attestation subject from package file.

        Args:
            package_path: Path to package file

        Returns:
            ProvenanceSubject with digests
        """
        sha256 = self._sha256(package_path)
        sha512 = self._sha512(package_path)

        return ProvenanceSubject(
            name=package_path.name,
            sha256=sha256,
            sha512=sha512,
        )

    def _collect_dependencies(self) -> list[ResolvedDependency]:
        """Collect all resolved dependencies from provenance log.

        Returns:
            List of ResolvedDependency objects
        """
        dependencies: list[ResolvedDependency] = []
        seen_urls: set[str] = set()

        records = self.log.read_all()

        for record in records:
            if not record.success or not record.url:
                continue

            # Deduplicate by URL
            if record.url in seen_urls:
                continue
            seen_urls.add(record.url)

            # Determine URI scheme
            uri = record.url
            if uri.startswith("git+") or uri.endswith(".git"):
                uri = f"git+{record.url}" if not uri.startswith("git+") else uri

            digest: dict[str, str] = {}
            if record.sha256:
                digest["sha256"] = record.sha256

            dep = ResolvedDependency(
                uri=uri,
                digest=digest,
                name=record.artifact,
                download_location=record.resolved_url or record.url,
            )
            dependencies.append(dep)

        return dependencies

    def _build_config(self, versions_env: dict[str, str] | None) -> dict[str, Any]:
        """Build configuration parameters.

        Args:
            versions_env: Parsed versions.env

        Returns:
            Configuration dict for the attestation
        """
        config: dict[str, Any] = {}

        # Git state
        git_info = self._get_git_info()
        if git_info:
            config["source"] = git_info

        # Versions
        if versions_env:
            config["versions"] = versions_env

        return config

    def _get_git_info(self) -> dict[str, str] | None:
        """Get current git state.

        Returns:
            Dict with commit, branch, remote info, or None
        """
        try:
            commit = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
            )
            branch = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
            )
            remote = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
            )

            if commit.returncode == 0:
                return {
                    "commit": commit.stdout.strip(),
                    "branch": branch.stdout.strip() if branch.returncode == 0 else "",
                    "remote": remote.stdout.strip() if remote.returncode == 0 else "",
                }
        except FileNotFoundError:
            pass

        return None

    def _get_tool_version(self) -> str:
        """Get opencenter-airgap tool version.

        Returns:
            Version string or 'dev'
        """
        try:
            from importlib.metadata import version
            return version("opencenter-airgap")
        except Exception:
            return "dev"

    @staticmethod
    def _sha256(file_path: Path) -> str:
        """Calculate SHA256 of a file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()

    @staticmethod
    def _sha512(file_path: Path) -> str:
        """Calculate SHA512 of a file."""
        sha512_hash = hashlib.sha512()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha512_hash.update(chunk)
        return sha512_hash.hexdigest()
