# Troubleshooting

## `black` fails in CI with Python parse mismatch

Symptom:
- `Python 3.11 cannot parse code formatted for Python 3.13`

Cause:
- `black` safety check parses with runtime interpreter. If runtime is older than source syntax target, check can fail.

Fix:
- Run formatting in the project conda env (`py313`) before pushing:

```bash
conda run -p ./.conda-envs/preflight-py313 make format
conda run -p ./.conda-envs/preflight-py313 make lint
conda run -p ./.conda-envs/preflight-py313 make test
```

## `pytest` collection on Windows touches `System Volume Information`

Symptom:
- `PermissionError: ... System Volume Information`

Cause:
- Broad collection path from non-repo root.

Fix:
- Keep CI invocation scoped to `tests/` and run from repository root:

```bash
python -m pytest tests/ -v --tb=short -W error
```

## Policy/config errors appear at runtime

Fix:
- Use `--config-file` and/or `--policy-file` with valid JSON.
- Current versions validate early and fail fast on malformed payloads.

Examples of hard failures:
- unknown `fail_on` severities
- all-zero `score_weights`
- invalid suppression date format

## Gate exits unexpectedly

Exit codes:
- `0` -> gate `PASS`
- `2` -> gate `FAIL` (or explicit CLI validation failure)

If you see a CLI exception for unknown gate status, that indicates invalid internal state or a malformed custom integration and should be treated as a bug.

## Plugin check does not load

Checklist:
- Use native entry point group: `preflight.checks`
- Ensure callable signature: `run(df, context) -> list[Finding]`
- If using legacy plugin group (`preflight.checks.legacy`), explicitly set:

```bash
export PREFLIGHT_ENABLE_LEGACY_PLUGIN_ENTRYPOINTS=1
```

