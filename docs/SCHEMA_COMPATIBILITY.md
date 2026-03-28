# Schema Compatibility

`RunReport.to_dict()` is versioned by `schema_version`.

## Policy

- Minor/patch releases may add fields.
- Existing keys should remain stable within the same major schema version.
- Breaking structural changes require a schema major bump.

## Consumer guidance

- Always branch logic on `schema_version`.
- Ignore unknown fields for forward compatibility.
- Validate required keys using `preflight.schema.validate_run_payload(...)`.

## Current contract

Current top-level required keys:
- `schema_version`
- `run`
- `dataset`
- `gate`
- `score`
- `summary`
- `findings`

Nested validation includes:
- gate status/reasons
- score object types
- finding severity/domain/signal strength
- evidence metrics object

