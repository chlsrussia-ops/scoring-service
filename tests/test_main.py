from scoring_service.main import run


def test_run_default() -> None:
    code = run([])
    assert code == 0


def test_run_inline_json() -> None:
    code = run(["--json", '{"amount": 100, "comment": "ok"}', "--pretty"])
    assert code == 0
