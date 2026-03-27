from __future__ import annotations

import json

import pytest

from preflight.config_loader import load_config_file


def test_load_config_file_json(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "runtime": {
                    "mode": "fast",
                    "sample_rows": 1234,
                    "random_state": 7,
                },
                "enabled_checks": {
                    "leakage": False,
                },
            }
        ),
        encoding="utf-8",
    )
    cfg = load_config_file(str(path))
    assert cfg.runtime.mode == "fast"
    assert cfg.runtime.sample_rows == 1234
    assert cfg.runtime.random_state == 7
    assert cfg.enabled_checks["leakage"] is False


def test_load_config_file_unknown_extension_with_json_payload(tmp_path):
    path = tmp_path / "config.custom"
    path.write_text(json.dumps({"runtime": {"mode": "accurate"}}), encoding="utf-8")
    cfg = load_config_file(str(path))
    assert cfg.runtime.mode == "accurate"


def test_load_config_file_requires_mapping_root(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(["not", "a", "mapping"]), encoding="utf-8")
    with pytest.raises(ValueError, match="mapping/object"):
        load_config_file(str(path))


def test_load_config_file_unknown_extension_without_yaml_support(tmp_path, monkeypatch):
    path = tmp_path / "config.custom"
    path.write_text("runtime: {mode: fast}", encoding="utf-8")

    import builtins

    real_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name == "yaml":
            raise ImportError("yaml missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)
    with pytest.raises(ValueError, match="PyYAML unavailable"):
        load_config_file(str(path))
