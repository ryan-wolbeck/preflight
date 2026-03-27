"""
Load PreflightConfig from JSON/YAML files.
"""

from __future__ import annotations

import json
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any, TypeVar, cast, get_args, get_origin
import types
import typing

from preflight.config import PreflightConfig

T = TypeVar("T")


def load_config_file(path: str) -> PreflightConfig:
    payload = _load_mapping(path)
    if not isinstance(payload, dict):
        raise ValueError("Config file must be a mapping/object.")
    return _dataclass_from_dict(PreflightConfig, payload)


def _load_mapping(path: str) -> Any:
    text = Path(path).read_text(encoding="utf-8")
    lower = path.lower()
    if lower.endswith(".json"):
        return json.loads(text)
    if lower.endswith(".yml") or lower.endswith(".yaml"):
        try:
            import yaml  # type: ignore[import-untyped]
        except Exception as exc:
            raise ValueError("YAML config files require PyYAML installed.") from exc
        return yaml.safe_load(text)
    try:
        return json.loads(text)
    except Exception:
        try:
            import yaml
        except Exception as exc:
            raise ValueError("Unknown config extension and PyYAML unavailable.") from exc
        return yaml.safe_load(text)


def _dataclass_from_dict(cls: type[T], payload: dict[str, Any]) -> T:
    hints = typing.get_type_hints(cls)
    kwargs: dict[str, Any] = {}
    for field in fields(cast(Any, cls)):
        if field.name not in payload:
            continue
        value = payload[field.name]
        anno = hints.get(field.name, field.type)
        kwargs[field.name] = _coerce_value(anno, value)
    return cls(**kwargs)


def _coerce_value(anno: Any, value: Any) -> Any:
    origin = get_origin(anno)
    if origin is None:
        if isinstance(anno, type) and is_dataclass(anno) and isinstance(value, dict):
            return _dataclass_from_dict(anno, value)
        return value

    if origin is dict and isinstance(value, dict):
        return value
    if origin is list and isinstance(value, list):
        inner = get_args(anno)[0]
        return [_coerce_value(inner, item) for item in value]

    # Handle Optional/Union by trying each branch.
    union_type = getattr(types, "UnionType", None)
    if origin is typing.Union or (union_type is not None and origin is union_type):
        for candidate in get_args(anno):
            if candidate is type(None) and value is None:
                return None
            try:
                coerced = _coerce_value(candidate, value)
                return coerced
            except Exception:
                continue
    return value
