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


def test_shared_library_sources_compile_with_fpic(tmp_path):
    """Shared library objects need position-independent code or the
    ``-shared`` link step fails with "recompile with -fPIC"."""
    config = _shared_library_config(tmp_path)
    toolchain = SimpleNamespace(cc="cc", cxx="c++", ar="ar")

    NinjaBackend(config, tmp_path / "build", toolchain).generate()

    ninja_file = (tmp_path / "build" / "build.ninja").read_text(encoding="utf-8")
    assert "cflags = -fPIC" in ninja_file

    cc_data = json.loads((tmp_path / "build" / "compile_commands.json").read_text())
    assert "-fPIC" in cc_data[0]["command"]


def test_shared_library_does_not_duplicate_user_fpic(tmp_path):
    config = _shared_library_config(tmp_path, target_cflags=["-fPIC"])
    toolchain = SimpleNamespace(cc="cc", cxx="c++", ar="ar")

    NinjaBackend(config, tmp_path / "build", toolchain).generate()

    ninja_file = (tmp_path / "build" / "build.ninja").read_text(encoding="utf-8")
    assert ninja_file.count("-fPIC") == 1


def test_non_shared_targets_do_not_get_fpic(tmp_path):
    config = ProjectConfig(
        name="mixed",
        version="1.0.0",
        source_dir=tmp_path,
        targets=[
            TargetConfig(name="app", target_type="executable", sources=["app.c"]),
            TargetConfig(name="lib", target_type="static_library", sources=["lib.c"]),
        ],
    )
    toolchain = SimpleNamespace(cc="cc", cxx="c++", ar="ar")

    NinjaBackend(config, tmp_path / "build", toolchain).generate()

    ninja_file = (tmp_path / "build" / "build.ninja").read_text(encoding="utf-8")
    assert "-fPIC" not in ninja_file
