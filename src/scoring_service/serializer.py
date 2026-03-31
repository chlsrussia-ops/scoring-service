from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel


class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, BaseModel):
            return obj.model_dump(mode="json")
        if isinstance(obj, datetime):
            if obj.tzinfo is None:
                obj = obj.replace(tzinfo=timezone.utc)
            return obj.isoformat()
        if isinstance(obj, set):
            return sorted(obj)
        return super().default(obj)


def serialize(obj: Any, *, indent: int = 2, sort_keys: bool = True) -> str:
    return json.dumps(
        obj,
        cls=EnhancedJSONEncoder,
        indent=indent,
        sort_keys=sort_keys,
        ensure_ascii=False,
    )


def deserialize(data: str) -> Any:
    return json.loads(data)
