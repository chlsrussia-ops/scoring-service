from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from scoring_service.config import Settings
from scoring_service.contracts import ScoreRequest
from scoring_service.diagnostics import configure_logging
from scoring_service.executor import execute
from scoring_service.serializer import deserialize, serialize


def _load_payload_from_json_arg(raw: str) -> dict[str, Any]:
    data = deserialize(raw)
    if not isinstance(data, dict):
        raise ValueError("JSON payload must be an object")
    return data


def _load_payload_from_file(path: str) -> dict[str, Any]:
    content = Path(path).read_text(encoding="utf-8")
    data = deserialize(content)
    if not isinstance(data, dict):
        raise ValueError("JSON file must contain an object")
    return data


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scoring pipeline CLI")
    parser.add_argument("--json", help='Inline JSON object, example: --json \'{"a": 1}\'')
    parser.add_argument("--file", help="Path to JSON file")
    parser.add_argument("--request-id", default="cli-request")
    parser.add_argument("--source", default="cli")
    parser.add_argument("--pretty", action="store_true", help="Pretty print JSON result")
    return parser


def build_default_payload() -> dict[str, Any]:
    return {
        "amount": 120,
        "discount": 5.5,
        "comment": "excellent customer profile",
        "tags": ["vip", "repeat"],
        "metadata": {"region": "eu", "segment": "gold"},
        "approved": True,
    }


def run(argv: list[str] | None = None) -> int:
    settings = Settings.from_env()
    configure_logging(settings.log_level)

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.json and args.file:
        raise ValueError("Use only one of --json or --file")

    if not args.json and not args.file:
        payload = build_default_payload()
    elif args.json:
        payload = _load_payload_from_json_arg(args.json)
    else:
        payload = _load_payload_from_file(args.file)

    request = ScoreRequest(
        payload=payload,
        request_id=args.request_id,
        source=args.source,
    )

    result, decision = execute(request, settings)

    response = {
        "result": result,
        "review": {
            "approved": decision.approved,
            "label": decision.label,
            "reason": decision.reason,
        },
    }

    indent = settings.pretty_json_indent if args.pretty else settings.pretty_json_indent
    print(serialize(response, indent=indent))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(run())
