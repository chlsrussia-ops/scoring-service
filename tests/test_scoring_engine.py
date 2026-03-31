from scoring_service.config import Settings
from scoring_service.contracts import ScoreRequest
from scoring_service.scoring_engine import compute_breakdown


def test_compute_breakdown_expected_shape() -> None:
    req = ScoreRequest(
        payload={
            "a": 10,
            "b": 20.5,
            "text": "hello",
            "tags": [1, 2, 3],
            "meta": {"x": 1, "y": 2},
            "approved": True,
        },
        request_id="r1",
        source="test",
    )
    result = compute_breakdown(req, Settings())

    assert result.item_count == 6
    assert result.numeric_sum >= 30.5
    assert result.base_score > 0
    assert isinstance(result.bonuses, dict)
    assert result.numeric_fields_count == 2
    assert result.text_fields_count == 1
    assert result.collection_fields_count == 1
    assert result.nested_fields_count == 1
