# TrendIntel - Content Intelligence Platform

AI-powered trend intelligence for content, media, and marketing teams.

TrendIntel monitors RSS feeds, Reddit, APIs, and other data sources to detect emerging trends, generate AI-powered summaries, and deliver actionable recommendations to your content team.

## Architecture

- **Backend:** Python 3.11+ / FastAPI / SQLAlchemy / Alembic / Pydantic
- **Frontend:** React 18 / TypeScript / Vite / Tailwind CSS
- **Database:** PostgreSQL 16
- **LLM:** OpenAI-compatible API (with mock provider for demo)
- **Sources:** RSS, Reddit, HTTP JSON API, File/CSV import

## Quick Start

### 1. Backend

```bash
cd /opt/scoring-service
cp .env.example .env
pip install -e ".[dev]"

# Start PostgreSQL (if not running)
docker compose up -d db

# Run migrations
alembic upgrade head

# Start API server
uvicorn scoring_service.api.app:create_app --factory --host 0.0.0.0 --port 8000 --reload
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at http://localhost:5173, proxies API calls to :8000.

### 3. Docker (all-in-one)

```bash
docker compose up --build
```

- API: http://localhost:8020
- Frontend: http://localhost:5173

## Demo Script (3-5 minutes)

### Step 1: Seed demo data
```bash
curl -X POST http://localhost:8000/v1/demo/seed
```
Creates 1200+ events, 21 trends, 15 recommendations, alerts, and 4 data sources.

### Step 2: Sync sources
```bash
curl -X POST http://localhost:8000/v1/demo/sync-sources
```

### Step 3: Run analysis
```bash
curl -X POST http://localhost:8000/v1/demo/run-analysis
```

### Step 4: Generate AI summaries
```bash
curl -X POST http://localhost:8000/v1/demo/generate-ai
```

### Step 5: Open Dashboard
Navigate to http://localhost:5173

### Step 6: Show top trends
Click "Trends" in sidebar. Sort by score. Click any trend for details.

### Step 7: Generate trend AI summary
On trend detail page, click "Generate AI Summary".

### Step 8: View recommendations
Click "Recommendations". Click "AI Enhance" on any item.

### Step 9: Generate executive digest
```bash
curl -X POST http://localhost:8000/v1/llm/digests/generate?tenant_id=demo
```

### Step 10: View alerts
Click "Alerts" in sidebar.

### One-command full pipeline
```bash
curl -X POST http://localhost:8000/v1/demo/run-all
```

## API Endpoints

### Dashboard
- `GET /v1/dashboard/overview` - Summary cards
- `GET /v1/dashboard/activity` - Recent activity
- `GET /v1/dashboard/trends` - Trends list (sort, filter, paginate)
- `GET /v1/dashboard/trends/{id}` - Trend detail with AI summary
- `GET /v1/dashboard/recommendations` - Recommendations list
- `GET /v1/dashboard/alerts` - Alerts list
- `GET /v1/dashboard/sources` - Sources overview

### Sources
- `GET /v1/sources` - List configured sources
- `POST /v1/sources` - Create new source
- `POST /v1/sources/{id}/test` - Test source connection
- `POST /v1/sources/{id}/sync` - Manual sync
- `GET /v1/sources/{id}/health` - Source health

### LLM
- `POST /v1/llm/trends/{id}/generate-summary` - Generate trend summary
- `POST /v1/llm/recommendations/{id}/enhance` - Enhance recommendation
- `POST /v1/llm/digests/generate` - Generate executive digest
- `GET /v1/llm/digests` - List digests
- `GET /v1/llm/generations` - List all LLM generations

### Demo
- `POST /v1/demo/seed` - Seed demo data
- `POST /v1/demo/sync-sources` - Sync all sources
- `POST /v1/demo/run-analysis` - Run trend analysis
- `POST /v1/demo/generate-ai` - Generate all AI summaries
- `POST /v1/demo/dispatch-alerts` - Dispatch alerts
- `POST /v1/demo/run-all` - Full pipeline
- `GET /v1/demo/status` - Demo environment status

### Original (preserved)
- `POST /v1/score` - Scoring endpoint (requires API key)
- `GET /v1/scores` - List recent scores

## LLM Configuration

### Mock mode (default)
No API key needed. Generates realistic summaries from input data.

### OpenAI mode
```env
SCORING_LLM_PROVIDER=openai
SCORING_LLM_API_KEY=sk-your-key-here
SCORING_LLM_MODEL=gpt-4o-mini
```

## Tests

```bash
pytest -v
```

## Product Use Case

**Trend Intelligence for Content/Media/Marketing Teams**

- Monitors RSS, Reddit, APIs for content signals
- Detects rising trends and anomalies
- Generates AI-powered summaries and explanations
- Recommends content actions (publish, escalate, monitor)
- Alerts team about high-priority trends
- Delivers executive briefing digests
