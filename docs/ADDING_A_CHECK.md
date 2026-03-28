# Adding a Check

`preflight` is policy-first. New checks should be native checks that emit `Finding` objects.

## 1. Implement the check logic

Add a module under `preflight/checks_native/` returning `list[Finding]`:

```python
name = "my_check"

def run(df: pd.DataFrame, context: CheckContext) -> list[Finding]:
    ...
```

## 2. Register it

Add a `RegisteredCheck` entry in `preflight/engine/registry.py`.
Use `kind="native"` and `run_native=...`.

For plugin distribution, expose an entry point:

```toml
[project.entry-points."preflight.checks"]
my_plugin_check = "my_pkg.preflight_plugin:run"
```

Where `run(df, context) -> list[Finding]`.

Legacy plugin fallback (compatibility only) is explicit opt-in:

```toml
[project.entry-points."preflight.checks.legacy"]
my_legacy_check = "my_pkg.legacy_plugin:run"
```

This path is only loaded when `PREFLIGHT_ENABLE_LEGACY_PLUGIN_ENTRYPOINTS=1`.

## 3. Naming and domains

- Use shared check-name/domain constants from `preflight/constants.py` when possible.
- Set a specific `Domain` on each finding.
- Keep `check_id` stable and descriptive (for policy/suppressions).

## 4. Evidence quality

A useful finding should include:
- numeric metrics in `evidence.metrics`
- affected columns
- concrete remediation suggestions

## 5. Tests

Add tests for:
- trigger case
- non-trigger case
- edge case (empty/all-null/small sample)
- deterministic behavior with fixed seed
- policy impact (severity and gate behavior)

## Legacy note

Legacy `preflight/checks/*` modules remain for compatibility with `check()` and `check_split()`.
Do not add new legacy checks unless explicitly required for backwards compatibility.
