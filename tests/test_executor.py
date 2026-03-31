from scoring_service.config import Settings
from scoring_service.contracts import ScoreRequest
from scoring_service.executor import execute


def test_execute_success() -> None:
    req = ScoreRequest(
        payload={"amount": 10, "comment": "hello", "tags": [1, 2]},
        request_id="exec-1",
        source="test",
    )
    result, decision = execute(req, Settings())

    assert result.ok is True
    assert result.used_fallback is False
    assert result.final_score >= 0
    assert decision.label in {"excellent", "approved", "manual_review", "rejected"}


def test_execute_fallback_on_bad_payload_type() -> None:
    settings = Settings()
    req = ScoreRequest.model_construct(
        payload="wrong",  # type: ignore[arg-type]
        request_id="exec-2",
        source="test",
    )
    result, decision = execute(req, settings)

    assert result.ok is False
    assert result.used_fallback is True
    assert result.final_score == 0.0
    assert decision.label == "rejected"
