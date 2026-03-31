from scoring_service.caps import apply_caps


def test_apply_caps_without_cap() -> None:
    result = apply_caps(42.0, min_value=0.0, max_value=100.0)
    assert result.value == 42.0
    assert result.capped is False


def test_apply_caps_with_upper_cap() -> None:
    result = apply_caps(142.0, min_value=0.0, max_value=100.0)
    assert result.value == 100.0
    assert result.capped is True


def test_apply_caps_with_lower_cap() -> None:
    result = apply_caps(-3.0, min_value=0.0, max_value=100.0)
    assert result.value == 0.0
    assert result.capped is True
