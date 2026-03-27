from __future__ import annotations

from preflight.engine.registry import discover_entrypoint_plugins, load_entrypoint_checks


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
        if group == "preflight.checks":
            return self._eps
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
