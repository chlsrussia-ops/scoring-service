"""Declarative policy rule evaluation engine.

Supports safe operators: eq, neq, gt, gte, lt, lte, in, contains, between, exists, not_exists.
No eval/exec — purely data-driven.
"""
from __future__ import annotations

from typing import Any


OPERATORS: dict[str, Any] = {
    "eq": lambda v, target: v == target,
    "neq": lambda v, target: v != target,
    "gt": lambda v, target: _num(v) > _num(target),
    "gte": lambda v, target: _num(v) >= _num(target),
    "lt": lambda v, target: _num(v) < _num(target),
    "lte": lambda v, target: _num(v) <= _num(target),
    "in": lambda v, target: v in target if isinstance(target, (list, tuple, set)) else False,
    "contains": lambda v, target: target in v if isinstance(v, (str, list, tuple, set)) else False,
    "between": lambda v, target: (
        isinstance(target, (list, tuple))
        and len(target) == 2
        and _num(target[0]) <= _num(v) <= _num(target[1])
    ),
    "exists": lambda v, target: v is not None,
    "not_exists": lambda v, target: v is None,
}


def _num(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def evaluate_condition(data: dict[str, Any], field: str, operator: str, value: Any) -> bool:
    """Evaluate a single condition against a data dict."""
    actual = _resolve_field(data, field)
    op_fn = OPERATORS.get(operator)
    if op_fn is None:
        return False
    try:
        return bool(op_fn(actual, value))
    except Exception:
        return False


def _resolve_field(data: dict[str, Any], field: str) -> Any:
    """Resolve dotted field path: 'a.b.c' -> data['a']['b']['c']."""
    parts = field.split(".")
    current: Any = data
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def evaluate_rule(
    data: dict[str, Any],
    conditions: list[dict[str, Any]],
) -> tuple[bool, list[dict[str, Any]]]:
    """Evaluate all conditions (AND logic). Returns (matched, details)."""
    details: list[dict[str, Any]] = []
    all_matched = True
    for cond in conditions:
        field = cond.get("field", "")
        operator = cond.get("operator", "eq")
        value = cond.get("value")
        matched = evaluate_condition(data, field, operator, value)
        details.append({
            "field": field,
            "operator": operator,
            "expected": value,
            "actual": _resolve_field(data, field),
            "matched": matched,
        })
        if not matched:
            all_matched = False
    return all_matched, details


def evaluate_policy_rules(
    data: dict[str, Any],
    rules: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Evaluate a list of rules. Return matched rules with details."""
    results: list[dict[str, Any]] = []
    for rule in rules:
        if not rule.get("enabled", True):
            continue
        conditions = rule.get("conditions", [])
        matched, details = evaluate_rule(data, conditions)
        if matched:
            results.append({
                "rule_name": rule.get("name", "unnamed"),
                "action": rule.get("action", "flag"),
                "weight": rule.get("weight", 1.0),
                "conditions_detail": details,
            })
    return results
