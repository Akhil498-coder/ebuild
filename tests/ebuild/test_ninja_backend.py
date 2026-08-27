from types import SimpleNamespace

from ebuild.build.ninja_backend import NinjaBackend
from ebuild.core.config import ProjectConfig, TargetConfig


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
