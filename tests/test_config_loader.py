from __future__ import annotations

import json

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
