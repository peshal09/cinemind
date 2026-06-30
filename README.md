# CineMind

A **full-stack** AI movie companion built on the MovieLens dataset — semantic search,
grounded retrieval-augmented Q&A, personalized explanations, and a multi-agent "film
concierge." A Python + FastAPI backend (Postgres/pgvector, Redis, a pluggable LLM layer —
Google Gemini) with a **Next.js 14 + TypeScript** frontend that makes the agents' reasoning
visible ("show your work").

> Captured, real outputs from the running system live in
> [`docs/demo-outputs.md`](docs/demo-outputs.md).

## What it does

- **Recommendations** — collaborative (SVD), content-based (TF-IDF), and hybrid
  models, plus a popularity baseline for cold-start users.
- **Semantic search** — natural-language queries (`"a slow-burn thriller with a
  twist"`) over `gte-small` embeddings in pgvector. Retrieval by *meaning*, not
  title keywords (hit-rate@10 **96%**).
- **Grounded RAG Q&A** (`/ask`) — answers only from retrieved movie context, with
  validated citations and an "I don't know" groundedness guard (groundedness
  **100%** on the eval set).
- **Personalized explanations** (`/why`) — a short, cited "why you'd like this,"
  grounded in the user's actual rating history.
- **Multi-agent concierge** (`/concierge`) — a deterministic 4-agent pipeline
  (preference → retrieval → critic → explainer) that turns a free-text request into
  a ranked, explained shortlist, with a per-agent **trace** and graceful fallback.
- **Conversational web UI** (`frontend/`) — a Next.js chat that renders the concierge's
  explained picks (with movie posters) and a **visualization of the 4-agent trace**, plus
  auth and a semantic-search mode.

## Architecture

```
  Next.js 14 UI          ┌──────────────────────── FastAPI ────────────────────────┐
  (frontend/) ─ JWT ─▶   │  /auth  /recommend  /search/semantic  /ask  /why         │
                         │  /ratings  /movies/{id}/similar  /concierge              │
                         └───┬───────────────┬──────────────┬───────────────┬──────┘
                             │               │              │               │
                    recommenders      embeddings +     RAG (retrieve →   multi-agent
                    (SVD/TF-IDF/        pgvector ANN    ground → cite)    concierge
                     hybrid)            (gte-small)                       (4 agents)
                             │               │              │               │
                         Postgres + pgvector  ·  Redis cache  ·  LLM (Gemini, resilient)
```

**The concierge pipeline** threads one explicit `ConciergeState` through four agents
and records what each did:

```
request + user ─▶ Preference ─▶ Retrieval ─▶ Critic ─▶ Explainer ─▶ ranked, explained picks + trace
                  (intent)      (candidates)  (filter+rank) (why)
                       └──────────── any agent throws ──────────▶ Phase-3 recommender fallback
```

### Engineering notes
- **LLM resilience** — retry transient errors with backoff, fail-fast on quota
  (429), fall back across models; failures degrade to a clean `503`, never a raw 500.
- **Caching** — `/ask` and `/why` responses cached in Redis (HIT/MISS logged,
  invalidated on re-rating / re-embedding).
- **Grounding** — tolerant citation matching (case/year/article-insensitive) so
  valid citations aren't dropped.

## API

All recommendation/personalization endpoints are JWT-protected (`Authorization: Bearer <token>`).

| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/register`, `/auth/login` | Create an account / get a JWT |
| `GET`  | `/auth/me` | The current user |
| `GET`  | `/recommend?model=&k=` | Personalized recommendations (cached, cold-start aware) |
| `GET`  | `/movies/{id}/similar` | Movies similar to a given movie |
| `POST` | `/ratings` | Rate a movie (invalidates that user's caches) |
| `POST` | `/search/semantic` | Embedding search over the catalog |
| `POST` | `/ask` | Grounded RAG Q&A with citations |
| `GET`  | `/recommendations/{id}/why` | Personalized, cited explanation |
| `POST` | `/concierge` | Multi-agent ranked + explained shortlist (with trace) |

## Tech stack

**Backend:** Python 3.11 · FastAPI · SQLAlchemy · PostgreSQL + **pgvector** · Redis ·
sentence-transformers (`thenlper/gte-small`, 384-d) · Google Gemini (`google-genai`) ·
scikit-learn · Docker Compose · pytest.

**Frontend:** Next.js 14 (App Router) · TypeScript · Tailwind CSS · shadcn/ui.

## Project layout

```
app/
├── auth/            # JWT register/login/me, password hashing, deps
├── cache/           # Redis client: feed + LLM response caching, invalidation
├── concierge/       # multi-agent pipeline: state, preference, retrieval,
│                    #   critic, explainer, orchestrator, router
├── data/            # MovieLens loader (CSV/DB indirection)
├── db/              # SQLAlchemy models, engine/session, seed
├── embeddings/      # gte-small model + backfill (+ HNSW index)
├── enrichment/      # TMDB metadata enrichment (overview/keywords/cast)
├── eval/            # retrieval hit-rate + RAG groundedness metrics
├── llm/             # provider interface, Gemini provider, resilience
├── rag/             # /ask (grounded Q&A) and /why (explanations)
├── recommenders/    # collaborative, content, hybrid, popularity
├── main.py          # FastAPI app + router wiring + model lifespan
├── ratings.py       # /ratings
└── search.py        # /search/semantic
docs/                # demo-outputs.md (real captures) · BACKLOG.md (publish-readiness)
tests/               # pytest suite (58 tests)
frontend/            # Next.js 14 web app (App Router, TS, Tailwind, shadcn/ui)
```

## Setup & running (Docker)

One command brings up Postgres (pgvector), Redis, and the API; the entrypoint seeds
the MovieLens data (movies, ratings, users) idempotently.

```bash
cp .env.example .env        # then fill GEMINI_API_KEY and TMDB_API_KEY
docker compose up -d --build
```

The seed loads titles + genres only. To enable semantic search, `/ask`, and the
concierge, enrich with TMDB metadata and build the embeddings (one-time, ~minutes):

```bash
docker compose exec api python -m app.enrichment.tmdb        # overview/keywords/cast
docker compose exec api python -m app.embeddings.backfill    # embeddings + HNSW index
```

The API is then at `http://localhost:8000` (e.g. `GET /` for the banner). Example:

```bash
# register + login to get a token, then:
curl -s -X POST http://localhost:8000/concierge \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"request":"a mind-bending sci-fi like Inception but funnier, from the 90s","k":4}'
```

### Configuration (`.env`)
`GEMINI_API_KEY`, `GEMINI_MODEL` (default `gemini-2.5-flash`), `GEMINI_FALLBACK_MODELS`,
`TMDB_API_KEY`, `ASK_SIMILARITY_THRESHOLD` (0.83 for gte-small), `SEARCH_KEYWORD_WEIGHT`,
`SECRET_KEY`, plus DB/Redis URLs. See `.env.example`.

## Frontend

A Next.js 14 (App Router) + TypeScript + Tailwind + shadcn/ui web app in `frontend/` — the
conversational concierge (explained picks with posters, the agent-trace "show your work"
view, auth, and a semantic-search mode). It talks to the API over HTTP with a configurable
base URL, so it runs independently of the backend.

```bash
cd frontend
cp .env.local.example .env.local   # NEXT_PUBLIC_API_BASE (default http://localhost:8000)
npm install
npm run dev                        # http://localhost:3000
```

See [`frontend/README.md`](frontend/README.md) for details.

## Evaluation

```bash
docker compose exec api python -m app.eval.retrieval
```

| Metric | Value |
|---|---|
| Retrieval hit-rate@10 | **96%** |
| RAG groundedness | **100%** (8/8 in-domain) |

## Tests

```bash
docker compose exec api python -m pytest tests/ -q   # 58 passing
```

## Roadmap

- ✅ **Phase 1** — recommenders + FastAPI surface
- ✅ **Phase 2** — Postgres/Redis, JWT auth, ratings, Docker, CORS
- ✅ **Phase 3** — embeddings + semantic search, RAG `/ask`, `/why`, eval
- ✅ **Phase 4a** — multi-agent concierge (`/concierge`) with trace + fallback
- ✅ **Frontend** — Next.js 14 conversational UI: auth, concierge chat + agent-trace view,
  semantic search, movie posters
- ⏭️ **Phase 4b** — conversational memory + LLM-driven tool routing ("more like that")
- ⏭️ **Deploy** (Vercel + hosted backend) and the publish-readiness items in
  [`docs/BACKLOG.md`](docs/BACKLOG.md)
- ⏭️ **Runtime/rating constraints** — add `runtime`/`vote_average` (schema + TMDB re-enrich)

## Attribution

Data provided by [MovieLens](https://grouplens.org/datasets/movielens/) (GroupLens)
and [TMDB](https://www.themoviedb.org/). This product uses the TMDB API but is not
endorsed or certified by TMDB.
