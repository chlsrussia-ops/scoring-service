from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from scoring_service.config import Settings
from scoring_service.contracts import ScoreRequest
from scoring_service.diagnostics import configure_logging
from scoring_service.executor import execute_response
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
    parser.add_argument("--json", help="Inline JSON object")
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
    settings = Settings()
    configure_logging(settings.log_level, json_logs=settings.log_json)

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

    response = execute_response(request, settings)
    indent = settings.pretty_json_indent if args.pretty else None
    print(serialize(response, indent=indent or 2))
    return 0 if response.result.ok else 1


if __name__ == "__main__":
    raise SystemExit(run())
