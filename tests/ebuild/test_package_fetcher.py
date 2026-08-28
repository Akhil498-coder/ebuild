# SPDX-License-Identifier: MIT
# Copyright (c) 2026 EoS Project

"""PackageFetcher extraction: Python 3.8+ compatibility and path traversal."""

from __future__ import annotations

import io
import tarfile
import zipfile
from pathlib import Path

import pytest

from ebuild.packages.fetcher import FetchError, PackageFetcher


def _write_targz(path: Path, files: dict[str, bytes]) -> None:
    with tarfile.open(path, "w:gz") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))


def _write_zip(path: Path, files: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)


def test_extract_targz_succeeds_on_running_python(tmp_path):
    """filter='data' is 3.12+; this must still extract on 3.8–3.11."""
    archive = tmp_path / "pkg.tar.gz"
    _write_targz(archive, {"hello.txt": b"hello ebuild"})
    dest = tmp_path / "out"

    PackageFetcher(tmp_path / "dl")._extract(archive, dest)

    assert (dest / "hello.txt").read_bytes() == b"hello ebuild"


def test_extract_zip_succeeds(tmp_path):
    archive = tmp_path / "pkg.zip"
    _write_zip(archive, {"hello.txt": b"hello zip"})
    dest = tmp_path / "out"

    PackageFetcher(tmp_path / "dl")._extract(archive, dest)

    assert (dest / "hello.txt").read_bytes() == b"hello zip"


def test_extract_tar_rejects_path_traversal(tmp_path):
    archive = tmp_path / "evil.tar.gz"
    _write_targz(archive, {"../escaped.txt": b"pwned"})
    dest = tmp_path / "out"
    dest.mkdir()

    with pytest.raises(FetchError, match="path traversal"):
        PackageFetcher(tmp_path / "dl")._extract(archive, dest)

    assert not (tmp_path / "escaped.txt").exists()


def test_extract_zip_rejects_path_traversal(tmp_path):
    archive = tmp_path / "evil.zip"
    _write_zip(archive, {"../escaped.txt": b"pwned"})
    dest = tmp_path / "out"
    dest.mkdir()

    with pytest.raises(FetchError, match="path traversal"):
        PackageFetcher(tmp_path / "dl")._extract(archive, dest)

    assert not (tmp_path / "escaped.txt").exists()


def test_extract_zip_rejects_sibling_prefix_path(tmp_path):
    """'/tmp/extract' must not match '/tmp/extract-evil' via startswith()."""
    dest = tmp_path / "extract"
    dest.mkdir()
    sibling = tmp_path / "extract-evil.txt"
    archive = tmp_path / "evil.zip"
    # namelist entry that resolves to a sibling of dest via ".."
    _write_zip(archive, {"../extract-evil.txt": b"pwned"})

    with pytest.raises(FetchError, match="path traversal"):
        PackageFetcher(tmp_path / "dl")._extract(archive, dest)

    assert not sibling.exists()


def test_extract_rejects_unknown_format(tmp_path):
    archive = tmp_path / "pkg.rar"
    archive.write_bytes(b"not-an-archive")

    with pytest.raises(FetchError, match="Unsupported archive format"):
        PackageFetcher(tmp_path / "dl")._extract(archive, tmp_path / "out")
