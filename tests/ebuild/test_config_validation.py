import pytest
import yaml

from ebuild.core.config import ConfigError, load_config


def write_config(tmp_path, data):
    config_path = tmp_path / "build.yaml"
    config_path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return config_path


@pytest.mark.parametrize("invalid_target", ["app", 42, None])
def test_target_definition_must_be_mapping(tmp_path, invalid_target):
    path = write_config(
        tmp_path,
        {"project": {"name": "demo"}, "targets": [invalid_target]},
    )

    with pytest.raises(ConfigError, match="expected a YAML mapping"):
        load_config(path)


@pytest.mark.parametrize("field_name", [
    "sources", "includes", "cflags", "ldflags", "defines", "depends", "uses"
])
def test_target_collection_fields_must_be_lists(tmp_path, field_name):
    target = {"name": "app", "type": "executable", "sources": ["main.c"]}
    target[field_name] = "not-a-list"
    path = write_config(
        tmp_path,
        {"project": {"name": "demo"}, "targets": [target]},
    )

    with pytest.raises(ConfigError, match=rf"field '{field_name}' must be a list"):
        load_config(path)


def test_target_collection_items_must_be_strings(tmp_path):
    path = write_config(
        tmp_path,
        {
            "project": {"name": "demo"},
            "targets": [
                {"name": "app", "type": "executable", "sources": ["main.c", 7]}
            ],
        },
    )

    with pytest.raises(ConfigError, match="must contain only strings"):
        load_config(path)


def test_backend_config_must_be_mapping(tmp_path):
    path = write_config(
        tmp_path,
        {"project": {"name": "demo"}, "backend_config": ["invalid"]},
    )

    with pytest.raises(ConfigError, match="'backend_config' must be a mapping"):
        load_config(path)

def test_duplicate_target_names_raise_config_error(tmp_path):
    path = write_config(
        tmp_path,
        {
            "project": {"name": "demo"},
            "targets": [
                {"name": "app", "type": "executable", "sources": ["main.c"]},
                {"name": "app", "type": "static_library", "sources": ["lib.c"]},
            ],
        },
    )

    with pytest.raises(ConfigError, match="Duplicate target name 'app'"):
        load_config(path)