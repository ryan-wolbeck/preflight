# Adding a Check

`preflight` now supports a policy-first architecture while still adapting legacy checks.

## 1. Implement the check logic

For now, add a module under `preflight/checks/` returning `list[CheckResult]`:

```python
def run(df: pd.DataFrame, target: str | None = None, config: MyConfig | None = None) -> list[CheckResult]:
    ...
```

## 2. Register it

Add a `RegisteredCheck` entry in `preflight/engine/registry.py`.

For plugin distribution, expose an entry point:

```toml
[project.entry-points."preflight.checks"]
my_plugin_check = "my_pkg.preflight_plugin:run"
```

Where `run(df, context) -> list[Finding]`.

## 3. Domain mapping

If needed, map its category to a `Domain` in `preflight/engine/adapters.py`.

## 4. Evidence quality

A useful finding should include:
- numeric metrics in `details`
- affected columns
- concrete remediation suggestions

## 5. Tests

Add tests for:
- trigger case
- non-trigger case
- edge case (empty/all-null/small sample)
- deterministic behavior with fixed seed
- policy impact (severity and gate behavior)
