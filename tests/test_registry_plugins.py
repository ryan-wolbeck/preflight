from __future__ import annotations

from preflight.engine.registry import (
    LEGACY_PLUGIN_GROUP,
    NATIVE_PLUGIN_GROUP,
    default_registry,
    discover_entrypoint_plugins,
    load_entrypoint_checks,
    RegisteredCheck,
)


class _FakeEP:
    def __init__(self, name, value, loaded):
        self.name = name
        self.value = value
        self._loaded = loaded

    def load(self):
        return self._loaded


class _FakeEPs:
    def __init__(self, eps):
        self._eps = eps

    def select(self, group):
        if group == NATIVE_PLUGIN_GROUP:
            return self._eps
        return []


class _FakeMultiGroupEPs:
    def __init__(self, native_eps, legacy_eps):
        self._native = native_eps
        self._legacy = legacy_eps

    def select(self, group):
        if group == NATIVE_PLUGIN_GROUP:
            return self._native
        if group == LEGACY_PLUGIN_GROUP:
            return self._legacy
        return []


def test_load_entrypoint_checks(monkeypatch):
    def plugin_callable(df, context):
        return []

    eps = _FakeEPs([_FakeEP("demo_plugin", "pkg:check", plugin_callable)])
    monkeypatch.setattr("preflight.engine.registry.entry_points", lambda: eps)
    checks = load_entrypoint_checks()
    assert any(check.name == "demo_plugin" and check.kind == "native" for check in checks)


def test_discover_entrypoint_plugins_reports_error(monkeypatch):
    class _BadEP:
        name = "bad_plugin"
        value = "pkg:bad"

        def load(self):
            raise RuntimeError("boom")

    class _FakeEPs2:
        def select(self, group):
            return [_BadEP()] if group == "preflight.checks" else []

    monkeypatch.setattr("preflight.engine.registry.entry_points", lambda: _FakeEPs2())
    diagnostics = discover_entrypoint_plugins()
    assert diagnostics
    assert diagnostics[0]["status"] == "error"


def test_discover_entrypoint_plugins_rejects_legacy_registered_check_in_native_group(monkeypatch):
    legacy_check = RegisteredCheck(
        name="legacy_plugin",
        kind="legacy",
        run_legacy=lambda df, target, cfg: [],
    )
    eps = _FakeEPs([_FakeEP("legacy_plugin", "pkg:legacy", legacy_check)])
    monkeypatch.setattr("preflight.engine.registry.entry_points", lambda: eps)
    diagnostics = discover_entrypoint_plugins(group=NATIVE_PLUGIN_GROUP, plugin_mode="native")
    assert diagnostics
    assert diagnostics[0]["status"] == "error"
    assert "Legacy plugin entry points are disabled" in diagnostics[0]["error"]


def test_load_entrypoint_checks_legacy_group_enabled(monkeypatch):
    def legacy_callable(df, target, cfg):
        return []

    eps = _FakeMultiGroupEPs(
        native_eps=[],
        legacy_eps=[_FakeEP("legacy_plugin", "pkg:legacy", legacy_callable)],
    )
    monkeypatch.setattr("preflight.engine.registry.entry_points", lambda: eps)
    monkeypatch.setenv("PREFLIGHT_ENABLE_LEGACY_PLUGIN_ENTRYPOINTS", "1")
    checks = load_entrypoint_checks()
    assert any(check.name == "legacy_plugin" and check.kind == "legacy" for check in checks)


def test_default_registry_builtin_checks_are_native():
    checks = default_registry()
    builtin = [check for check in checks if check.source == "builtin"]
    assert builtin
    assert all(check.kind == "native" for check in builtin)
