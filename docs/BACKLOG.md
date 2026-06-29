# CineMind — Publish-Readiness Backlog

The app is a **feature-complete prototype** (backend through Phase 4a; frontend FE-1…FE-5
+ posters). This tracks what stands between that and a **polished, shareable** product.

Priorities: **P0** = core value / glaring bugs · **P1** = important polish & robustness ·
**P2** = nice-to-have. **Track 2** = public hosting (only matters if the demo is a live
public link — see the open decision at the bottom).

---

## P0 — core value & glaring bugs

- [ ] **Constraint-aware retrieval** *(the "best movie of 2015" bug)*. Hard constraints
  (year/decade/genre) are applied only in the Critic, *after* semantic retrieval — so if
  the candidate pool has no matching films, the year filter empties it and the Critic
  **relaxes into irrelevant results** (e.g. "best movie of 2015" → films merely *titled*
  "Best …"). Fix: push constraints into the **Retrieval** agent's candidate generation
  (query the DB filtered by year/genre first), rank superlative/quality queries ("best",
  "top") by popularity since there's no theme, and when nothing matches **say so** instead
  of relaxing. Files: `app/concierge/retrieval.py`, `app/concierge/critic.py`.
- [ ] **Rating UI** — the frontend never calls `/ratings`, so every user is permanently
  cold-start and the personalization/`/why` story is unreachable. Add a way to rate movies
  (e.g. on a movie detail view) → builds a taste profile.
- [ ] **Seeded demo account** (DP-2) — a user pre-rated on ~15 well-known films so
  personalized picks + "Because you liked…" explanations shine out of the box. Seed script
  + a one-click "try the demo account" affordance.
- [ ] **Explainer explains *all* picks** *(observed `explained: 2/5`)*. With no taste the
  prompt is weak and the model half-fills the JSON. Enforce "explain every candidate," or
  add a per-pick fallback so no card is left without a reason. File: `app/concierge/explainer.py`.
- [ ] **Movie detail view** — poster/cards are dead-ends. Click → overview, genres, cast
  (all already in the DB), and the rating control. Needs a small `GET /movies/{id}` endpoint.

## P1 — polish & robustness

- [ ] **Show the plot (overview) in search results** — the `overview` exists in the DB
  (9,620/9,742 movies) but the API doesn't return it. Small change: add `Movie.overview`
  to `/search/semantic` results (and the concierge `Pick`), exactly like `poster_path` was
  added; then render it (e.g. an expandable line under each result). Also feeds the movie
  detail view (P0). Files: `app/search.py`, `app/concierge/{state,explainer}.py`, frontend
  `SearchResults`/`PickCard`.
- [ ] **New chat / clear thread** — the conversation grows forever with no reset.
- [ ] **Session handling** — a JWT expiring mid-session shows an error toast but leaves the
  user "logged in"; auto-logout on 401.
- [ ] **Latency UX** — `/concierge` is ~10s behind a static skeleton. Add progress, or
  stream the agent trace as agents run (turns the wait into the showpiece). Needs a
  streaming endpoint.
- [ ] **Catalog-scope messaging** — the dataset stops at **2018**; recent-movie queries
  return nothing silently. Add a note + better empty states.
- [ ] **Mobile + a11y audit** — basics are in place but untested on a device / screen reader.
- [ ] **Poster loading** — blur placeholders, avoid layout shift.
- [ ] **Meta** — real favicon, page title, social-share (OG) image.
- [ ] **TMDB attribution** (required by TMDB terms when using their images/data) + a short
  "what is this?" blurb (portfolio demo, MovieLens data, 2018 cutoff).

## P2 — nice-to-have

- [ ] "My taste" rail (deferred from FE-5) — surface the user's liked films.
- [ ] Conversation **memory** / multi-turn refinement ("more like that") — backend Phase 4b.
- [ ] Streaming agent trace (pairs with the latency item).
- [ ] Frontend tests (component / e2e).

## Track 2 — public hosting (only if going live-public)

- [ ] Deploy backend (API + Postgres/pgvector + Redis) + load data into the cloud DB.
- [ ] **FE-6** — Vercel deploy (root dir `frontend/`, `NEXT_PUBLIC_API_BASE`).
- [ ] Rate limiting + **LLM spend cap** + abuse protection (open registration + uncapped
  Gemini calls = cost/abuse exposure).

---

## Open decision (gates Track 2 and the priority order)

**Who is the demo for?** — *guided/recorded* (you present it; polish P0/P1, skip hosting),
*live public* (do Track 2 + safety), or *clone-and-run* (great docs + one-command setup).
This choice decides whether the hosting/safety items matter at all.

> Highest-leverage path regardless of audience: P0 makes the product *work and impress*
> (relevant picks, real personalization, no embarrassing answers); hosting only makes it
> *reachable*.
