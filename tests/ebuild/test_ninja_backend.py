import json
from types import SimpleNamespace

from ebuild.build.ninja_backend import NinjaBackend
from ebuild.core.config import ProjectConfig, TargetConfig


def _shared_library_config(tmp_path, target_cflags=None):
    return ProjectConfig(
        name="shared-example",
        version="1.0.0",
        source_dir=tmp_path,
        targets=[
            TargetConfig(
                name="example",
                target_type="shared_library",
                sources=["example.c"],
                cflags=target_cflags or [],
            )
        ],
    )


def test_shared_library_uses_shared_link_rule(tmp_path):
    config = ProjectConfig(
        name="shared-example",
        version="1.0.0",
        source_dir=tmp_path,
        targets=[
            TargetConfig(
                name="example",
                target_type="shared_library",
                sources=["example.c"],
            )
        ],
    )
    toolchain = SimpleNamespace(cc="cc", cxx="c++", ar="ar")

    NinjaBackend(config, tmp_path / "build", toolchain).generate()

    ninja_file = (tmp_path / "build" / "build.ninja").read_text(encoding="utf-8")
    assert "rule link_shared\n  command = $cc -shared" in ninja_file
    assert "build " in ninja_file
    assert ": link_shared " in ninja_file


def test_cflags_consistent_between_ninja_and_compile_commands(tmp_path):
    """Verify that the refactored _resolve_target_cflags produces identical
    flags in both build.ninja and compile_commands.json."""
    config = ProjectConfig(
        name="consistency-test",
        version="1.0.0",
        source_dir=tmp_path,
        targets=[
            TargetConfig(
                name="app",
                target_type="executable",
                sources=["main.c"],
                includes=["include"],
                defines=["DEBUG=1", "VERSION=2"],
                cflags=["-O2"],
            )
        ],
    )
    toolchain = SimpleNamespace(cc="gcc", cxx="g++", ar="ar", cflags=["-Wall"], ldflags=[])

    NinjaBackend(config, tmp_path / "build", toolchain).generate()

    # Parse compile_commands.json
    cc_json = json.loads((tmp_path / "build" / "compile_commands.json").read_text())
    assert len(cc_json) == 1
    cc_command = cc_json[0]["command"]

    # Parse build.ninja cflags line
    ninja_text = (tmp_path / "build" / "build.ninja").read_text()
    for line in ninja_text.splitlines():
        if line.strip().startswith("cflags ="):
            ninja_cflags = line.strip().replace("cflags = ", "")
            break
    else:
        raise AssertionError("No cflags line found in build.ninja")

    # All flags in ninja should appear in compile_commands
    for flag in ninja_cflags.split():
        assert flag in cc_command, f"Flag {flag!r} in build.ninja but not compile_commands.json"


def test_sysroot_propagated_to_cflags(tmp_path):
    """Sysroot should appear in both cflags and ldflags."""
    config = ProjectConfig(
        name="sysroot-test",
        version="1.0.0",
        source_dir=tmp_path,
        targets=[
            TargetConfig(
                name="app",
                target_type="executable",
                sources=["main.c"],
            )
        ],
    )
    toolchain = SimpleNamespace(
        cc="arm-none-eabi-gcc", cxx="arm-none-eabi-g++", ar="arm-none-eabi-ar",
        cflags=[], ldflags=[], sysroot="/opt/arm-sysroot",
    )

    backend = NinjaBackend(config, tmp_path / "build", toolchain)
    cflags = backend._resolve_target_cflags(config.targets[0])
    ldflags = backend._get_toolchain_ldflags()
    assert "--sysroot=/opt/arm-sysroot" in cflags
    assert "--sysroot=/opt/arm-sysroot" in ldflags


def test_resolve_target_cflags_includes_packages(tmp_path):
    """Package include dirs must be included in resolved cflags."""
    from ebuild.build.ninja_backend import PackagePaths

    config = ProjectConfig(
        name="pkg-test",
        version="1.0.0",
        source_dir=tmp_path,
        targets=[
            TargetConfig(
                name="app",
                target_type="executable",
                sources=["main.c"],
                uses=["libfoo"],
            )
        ],
    )
    toolchain = SimpleNamespace(cc="gcc", cxx="g++", ar="ar")
    pkg_paths = {
        "libfoo": PackagePaths(include_dirs=[tmp_path / "libfoo" / "include"]),
    }

    backend = NinjaBackend(config, tmp_path / "build", toolchain, package_paths=pkg_paths)
    cflags = backend._resolve_target_cflags(config.targets[0])
    assert any("libfoo" in str(f) for f in cflags)
