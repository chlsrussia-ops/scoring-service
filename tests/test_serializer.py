from scoring_service.serializer import deserialize, serialize


def test_serialize_deserialize_roundtrip() -> None:
    data = {"a": 1, "b": "text", "c": [1, 2, 3]}
    raw = serialize(data)
    parsed = deserialize(raw)
    assert parsed == data
