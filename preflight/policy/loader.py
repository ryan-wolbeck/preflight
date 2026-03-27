"""
Load declarative policies from JSON/YAML files.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from preflight.model.finding import Domain, Finding, Severity
from preflight.model.policy import Policy, Rule


def load_policy_file(path: str) -> Policy:
    payload = _load_mapping(path)
    if not isinstance(payload, dict):
        raise ValueError("Policy file must define a mapping/object at the root.")

    name = str(payload.get("name", "custom"))
    fail_on = _parse_severity_list(payload.get("fail_on", ["error", "critical"]))
    score_weights = _parse_score_weights(payload.get("score_weights"))
    rules_payload = payload.get("rules", [])
    if not isinstance(rules_payload, list):
        raise ValueError("Policy 'rules' must be a list.")

    rules: list[Rule] = []
    for idx, item in enumerate(rules_payload):
        if not isinstance(item, dict):
            raise ValueError(f"Rule at index {idx} must be an object.")
        rule_id = str(item.get("id", f"rule_{idx}"))
        severity_raw = item.get("severity", "warn")
        severity = _parse_severity(str(severity_raw))
        description = str(item.get("description", ""))
        match = item.get("match", {})
        if not isinstance(match, dict):
            raise ValueError(f"Rule {rule_id!r} match must be an object.")
        rules.append(
            Rule(
                id=rule_id,
                when=_build_matcher(match),
                severity=severity,
                description=description,
            )
        )

    if score_weights is None:
        return Policy(name=name, rules=rules, fail_on=fail_on)
    return Policy(name=name, rules=rules, fail_on=fail_on, score_weights=score_weights)


def _load_mapping(path: str) -> Any:
    text = Path(path).read_text(encoding="utf-8")
    lower = path.lower()
    if lower.endswith(".json"):
        return json.loads(text)
    if lower.endswith(".yml") or lower.endswith(".yaml"):
        try:
            import yaml  # type: ignore[import-untyped]
        except Exception as exc:
            raise ValueError("YAML policy files require PyYAML installed.") from exc
        return yaml.safe_load(text)
    # fallback attempt: JSON first, then YAML
    try:
        return json.loads(text)
    except Exception:
        try:
            import yaml  # type: ignore[import-untyped]
        except Exception as exc:
            raise ValueError("Unknown policy file extension and PyYAML is unavailable.") from exc
        return yaml.safe_load(text)


def _parse_severity(token: str) -> Severity:
    allowed = {severity.value: severity for severity in Severity}
    normalized = token.strip().lower()
    if normalized not in allowed:
        raise ValueError(f"Unsupported severity token: {token!r}")
    return allowed[normalized]


def _parse_severity_list(value: Any) -> set[Severity]:
    if not isinstance(value, list):
        raise ValueError("'fail_on' must be a list of severities.")
    return {_parse_severity(str(item)) for item in value}


def _parse_score_weights(value: Any) -> dict[Severity, float] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("'score_weights' must be an object.")
    out: dict[Severity, float] = {}
    for key, val in value.items():
        sev = _parse_severity(str(key))
        if not isinstance(val, (float, int)):
            raise ValueError(f"score_weights[{key!r}] must be numeric.")
        out[sev] = float(val)
    return out


def _build_matcher(match: dict[str, Any]):
    domain_token = match.get("domain")
    signal = match.get("signal_strength")
    signal_in = match.get("signal_strength_in")
    check_id_contains = match.get("check_id_contains")
    tag = match.get("tag")

    domain = None
    if isinstance(domain_token, str):
        domain = Domain(domain_token)

    signal_allowed: set[str] | None = None
    if isinstance(signal, str):
        signal_allowed = {signal}
    elif isinstance(signal_in, list):
        signal_allowed = {str(item) for item in signal_in}

    check_id_fragment = str(check_id_contains) if isinstance(check_id_contains, str) else None
    tag_value = str(tag) if isinstance(tag, str) else None

    def _predicate(finding: Finding) -> bool:
        if domain is not None and finding.domain != domain:
            return False
        if signal_allowed is not None and finding.signal_strength not in signal_allowed:
            return False
        if check_id_fragment is not None and check_id_fragment not in finding.check_id:
            return False
        if tag_value is not None and tag_value not in finding.tags:
            return False
        return True

    return _predicate
