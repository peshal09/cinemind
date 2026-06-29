# CineMind — Frontend

The conversational concierge UI for [CineMind](../README.md). Next.js 14 (App
Router) + TypeScript + Tailwind + shadcn/ui, in an arthouse warm-ink / marquee-gold
theme. Talks to the FastAPI backend over HTTP (configurable base URL).

## Develop

```bash
cp .env.local.example .env.local      # NEXT_PUBLIC_API_BASE (default http://localhost:8000)
npm install
npm run dev                           # http://localhost:3000
```

The backend must be running and reachable (e.g. `docker compose up` in the repo
root → API on `:8000`). CORS is already open on the backend (bearer-token auth, no
cookies), so cross-origin works.

## Scripts

- `npm run dev` — dev server
- `npm run build` — production build (what Vercel runs)
- `npm run lint` — ESLint

## Deploy (Vercel)

Create a Vercel project with **Root Directory = `frontend/`**; Next.js is
auto-detected. Set `NEXT_PUBLIC_API_BASE` to your deployed backend URL. (For a
locked-down backend, set its `CORS_ORIGINS` to the Vercel domain.)

## Status

Built incrementally (FE-1 … FE-6):

- ✅ **FE-1** — scaffold, arthouse design system, typed API client (`lib/api.ts`, `lib/types.ts`)
- ✅ **FE-2** — auth: `AuthProvider` (JWT in `localStorage`), login/register dialog, gated state
- ✅ **FE-3** — concierge chat: composer, thread, explained `PickCard`s, intent chips, fallback banner
- ✅ **FE-4** — agent trace ("show your work"): 4-step timeline, timings, status, expandable per-agent detail
- ✅ **FE-5** — semantic search mode (public), recent queries, responsive + a11y polish
- ⏭️ **FE-6** — Vercel deploy
