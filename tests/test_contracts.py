import pytest
from pydantic import ValidationError

from scoring_service.contracts import ScoreRequest


def test_score_request_validation_success() -> None:
    req = ScoreRequest(payload={"a": 1}, request_id="r1", source="test")
    assert req.request_id == "r1"


def test_score_request_validation_fails_for_empty_request_id() -> None:
    with pytest.raises(ValidationError):
        ScoreRequest(payload={"a": 1}, request_id="", source="test")


def test_score_request_validation_fails_for_non_dict_payload() -> None:
    with pytest.raises(ValidationError):
        ScoreRequest(payload="bad", request_id="r1", source="test")  # type: ignore[arg-type]
