# scoring-service v2

Ultra production-grade scoring starter: CLI + FastAPI + Docker + CI.

## Quick start
```bash
cp .env.example .env
pip install -e ".[dev]"
make check
make api
```

## API
- `GET  /health`
- `GET  /ready`
- `POST /v1/score`
