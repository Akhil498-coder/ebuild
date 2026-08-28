# SPDX-License-Identifier: MIT
# Copyright (c) 2026 EoS Project

"""Package fetcher — downloads, verifies, and extracts source archives.

Handles HTTP/HTTPS downloads, SHA-256 checksum verification, and
tar/zip extraction into the package cache directory.
"""

from __future__ import annotations

import hashlib
import tarfile
import zipfile
from pathlib import Path
from urllib.request import urlretrieve

from ebuild.packages.recipe import PackageRecipe


class FetchError(Exception):
    """Raised when a package cannot be fetched or verified."""


class PackageFetcher:
    """Downloads and extracts package source archives.

    Downloads are cached so repeated builds don't re-download.
    Checksums are verified to ensure integrity.
    """

    def __init__(self, download_dir: str | Path) -> None:
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)

    def fetch(self, recipe: PackageRecipe, extract_to: str | Path) -> Path:
        """Fetch a package: download archive, verify checksum, extract.

        Args:
            recipe: The package recipe describing what to fetch.
            extract_to: Directory to extract source into.

        Returns:
            Path to the extracted source directory.

        Raises:
            FetchError: If download or verification fails.
        """
        archive_path = self._download(recipe)
        if recipe.checksum:
            self._verify_checksum(archive_path, recipe.checksum)
        extract_path = Path(extract_to)
        self._extract(archive_path, extract_path)
        return extract_path

    def _download(self, recipe: PackageRecipe) -> Path:
        """Download the source archive if not already cached."""
        if not recipe.url:
            raise FetchError(f"No URL specified for package {recipe.name}")
        if not recipe.url.startswith(("http://", "https://")):
            raise FetchError(
                f"Invalid URL scheme for {recipe.name}: {recipe.url} "
                f"(only http:// and https:// are allowed)"
            )

        filename = self._archive_filename(recipe)
        if not filename:
            raise FetchError(f"Could not derive filename from URL: {recipe.url}")
        archive_path = self.download_dir / filename

        if archive_path.exists():
            return archive_path

        try:
            urlretrieve(recipe.url, str(archive_path))
        except Exception as e:
            archive_path.unlink(missing_ok=True)
            raise FetchError(
                f"Failed to download {recipe.name} v{recipe.version} "
                f"from {recipe.url}: {e}"
            )

        return archive_path

    def _verify_checksum(self, archive_path: Path, checksum: str) -> None:
        """Verify SHA-256 checksum of a downloaded archive."""
        expected = checksum
        if expected.startswith("sha256:"):
            expected = expected[7:]

        sha256 = hashlib.sha256()
        with open(archive_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)

        actual = sha256.hexdigest()
        if actual != expected:
            raise FetchError(
                f"Checksum mismatch for {archive_path.name}:\n"
                f"  expected: {expected}\n"
                f"  actual:   {actual}"
            )

    def _extract(self, archive_path: Path, extract_to: Path) -> None:
        """Extract a tar.gz, tar.bz2, tar.xz, or .zip archive."""
        extract_to.mkdir(parents=True, exist_ok=True)

        name = archive_path.name.lower()
        try:
            if name.endswith((".tar.gz", ".tgz")):
                with tarfile.open(archive_path, "r:gz") as tar:
                    self._extract_tar(tar, extract_to)
            elif name.endswith((".tar.bz2", ".tbz2")):
                with tarfile.open(archive_path, "r:bz2") as tar:
                    self._extract_tar(tar, extract_to)
            elif name.endswith((".tar.xz", ".txz")):
                with tarfile.open(archive_path, "r:xz") as tar:
                    self._extract_tar(tar, extract_to)
            elif name.endswith(".zip"):
                with zipfile.ZipFile(archive_path, "r") as zf:
                    self._extract_zip(zf, extract_to)
            else:
                raise FetchError(f"Unsupported archive format: {archive_path.name}")
        except FetchError:
            raise
        except (tarfile.TarError, zipfile.BadZipFile, OSError) as e:
            raise FetchError(f"Failed to extract {archive_path.name}: {e}")

    @staticmethod
    def _path_is_within(base: Path, target: Path) -> bool:
        """Return True if *target* resolves strictly inside *base*.

        Uses Path.relative_to rather than a string prefix check so that
        ``/tmp/extract-evil`` is not treated as inside ``/tmp/extract``.
        """
        try:
            target.resolve().relative_to(base.resolve())
            return True
        except ValueError:
            return False

    def _extract_tar(self, tar: tarfile.TarFile, extract_to: Path) -> None:
        """Extract a tar archive, compatible with Python 3.8–3.11 and 3.12+.

        ``filter='data'`` (CVE-2007-4559 mitigation) was added in Python 3.12.
        README and pyproject.toml claim support for Python 3.8+, so older
        interpreters must extract without that keyword and with an explicit
        member-path check instead.
        """
        if hasattr(tarfile, "data_filter"):
            try:
                tar.extractall(extract_to, filter="data")
            except Exception as e:
                # 3.12+ raises FilterError / OutsideDestinationError for
                # members that would extract outside extract_to.
                err_name = type(e).__name__
                if "Filter" in err_name or "Outside" in err_name or "Absolute" in err_name:
                    raise FetchError(f"Tar path traversal detected: {e}") from e
                raise
            return

        extract_root = extract_to.resolve()
        for member in tar.getmembers():
            dest = extract_to / member.name
            if not self._path_is_within(extract_root, dest):
                raise FetchError(f"Tar path traversal detected: {member.name}")
            if member.issym() or member.islnk():
                link_dest = dest.parent / member.linkname
                if Path(member.linkname).is_absolute():
                    link_dest = Path(member.linkname)
                if not self._path_is_within(extract_root, link_dest):
                    raise FetchError(
                        f"Tar link path traversal detected: {member.name} -> {member.linkname}"
                    )
        tar.extractall(extract_to)

    def _extract_zip(self, zf: zipfile.ZipFile, extract_to: Path) -> None:
        """Extract a zip archive after rejecting path-traversal members."""
        extract_root = extract_to.resolve()
        for member in zf.namelist():
            if not self._path_is_within(extract_root, extract_to / member):
                raise FetchError(f"Zip path traversal detected: {member}")
        zf.extractall(extract_to)

    def _archive_filename(self, recipe: PackageRecipe) -> str:
        """Derive archive filename from recipe URL."""
        url_path = recipe.url.rstrip("/")
        return url_path.split("/")[-1]

    def is_downloaded(self, recipe: PackageRecipe) -> bool:
        """Check if the archive is already downloaded."""
        filename = self._archive_filename(recipe)
        return (self.download_dir / filename).exists()
