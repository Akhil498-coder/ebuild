# SPDX-License-Identifier: MIT
# Copyright (c) 2026 EoS Project

"""Unit tests for NinjaBackend generator.

Validates that NinjaBackend correctly generates build.ninja and compile_commands.json,
properly propagating toolchain-level cflags, ldflags, and sysroot alongside target-specific
options and dependencies.
"""

from pathlib import Path
import json
import pytest

from ebuild.build.ninja_backend import NinjaBackend, PackagePaths
from ebuild.build.toolchain import ResolvedToolchain
from ebuild.core.config import ProjectConfig, TargetConfig


@pytest.mark.ebuild
class TestNinjaBackend:
    """Tests for NinjaBackend file generation."""

    def test_default_toolchain_generation(self, tmp_path):
        """Verify default host toolchain without extra flags."""
        target = TargetConfig(
            name="app",
            target_type="executable",
            sources=["src/main.c"],
            cflags=["-O2"],
            ldflags=["-lm"],
        )
        config = ProjectConfig(
            name="test_proj",
            version="1.0.0",
            targets=[target],
            source_dir=tmp_path,
        )
        toolchain = ResolvedToolchain(
            cc="gcc",
            cxx="g++",
            ar="ar",
        )

        build_dir = tmp_path / "_build"
        backend = NinjaBackend(config, build_dir, toolchain)
        backend.generate()

        ninja_file = build_dir / "build.ninja"
        assert ninja_file.exists()
        ninja_content = ninja_file.read_text(encoding="utf-8")

        assert "cc = gcc" in ninja_content
        assert "cflags = -O2" in ninja_content
        assert "ldflags = -lm" in ninja_content

        cc_file = build_dir / "compile_commands.json"
        assert cc_file.exists()
        cc_data = json.loads(cc_file.read_text(encoding="utf-8"))
        assert len(cc_data) == 1
        assert cc_data[0]["file"] == "src/main.c"
        assert "gcc -O2 -c src/main.c" in cc_data[0]["command"]

    def test_toolchain_flags_and_sysroot_propagation(self, tmp_path):
        """Verify that toolchain-level cflags, ldflags, and sysroot are emitted."""
        target = TargetConfig(
            name="firmware",
            target_type="executable",
            sources=["src/main.c", "src/startup.c"],
            cflags=["-Wall"],
            ldflags=["-Wl,--gc-sections"],
        )
        config = ProjectConfig(
            name="embedded_app",
            version="0.1.0",
            targets=[target],
            source_dir=tmp_path,
        )
        toolchain = ResolvedToolchain(
            cc="arm-none-eabi-gcc",
            cxx="arm-none-eabi-g++",
            ar="arm-none-eabi-ar",
            prefix="arm-none-eabi-",
            arch="arm",
            sysroot="/opt/toolchains/arm-none-eabi/arm-none-eabi",
            cflags=["-mcpu=cortex-m4", "-mthumb"],
            ldflags=["-T", "linker/stm32f4.ld"],
        )

        build_dir = tmp_path / "_build"
        backend = NinjaBackend(config, build_dir, toolchain)
        backend.generate()

        ninja_file = build_dir / "build.ninja"
        ninja_content = ninja_file.read_text(encoding="utf-8")

        # Verify compiler flags include toolchain cflags, sysroot, and target cflags
        assert "-mcpu=cortex-m4" in ninja_content
        assert "-mthumb" in ninja_content
        assert "--sysroot=/opt/toolchains/arm-none-eabi/arm-none-eabi" in ninja_content
        assert "-Wall" in ninja_content

        # Verify linker flags include toolchain ldflags, sysroot, and target ldflags
        assert "-T linker/stm32f4.ld" in ninja_content or "-T linker/stm32f4.ld" in ninja_content
        assert "-Wl,--gc-sections" in ninja_content

        # Verify compile_commands.json contains toolchain flags and sysroot
        cc_file = build_dir / "compile_commands.json"
        cc_data = json.loads(cc_file.read_text(encoding="utf-8"))
        assert len(cc_data) == 2
        for entry in cc_data:
            cmd = entry["command"]
            assert "arm-none-eabi-gcc" in cmd
            assert "-mcpu=cortex-m4" in cmd
            assert "-mthumb" in cmd
            assert "--sysroot=/opt/toolchains/arm-none-eabi/arm-none-eabi" in cmd
            assert "-Wall" in cmd

    def test_static_library_and_package_paths(self, tmp_path):
        """Verify static library generation and package path integration."""
        lib_target = TargetConfig(
            name="mylib",
            target_type="static_library",
            sources=["src/lib.c"],
            cflags=["-fPIC"],
        )
        app_target = TargetConfig(
            name="myapp",
            target_type="executable",
            sources=["src/app.c"],
            depends=["mylib"],
            uses=["zlib"],
        )
        config = ProjectConfig(
            name="pkg_app",
            version="1.0.0",
            targets=[lib_target, app_target],
            source_dir=tmp_path,
        )
        toolchain = ResolvedToolchain(
            cc="gcc",
            cxx="g++",
            ar="ar",
            cflags=["-O3"],
        )
        pkg_paths = {
            "zlib": PackagePaths(
                include_dirs=[tmp_path / "pkg/include"],
                lib_dirs=[tmp_path / "pkg/lib"],
                libraries=["z"],
            )
        }

        build_dir = tmp_path / "_build"
        backend = NinjaBackend(config, build_dir, toolchain, package_paths=pkg_paths)
        backend.generate()

        ninja_content = (build_dir / "build.ninja").read_text(encoding="utf-8")
        assert "libmylib.a" in ninja_content
        assert "-lz" in ninja_content
        assert "-O3" in ninja_content
