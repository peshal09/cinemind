// API response shapes for the CineMind backend. Mirrors app/concierge/state.py,
// app/auth, and app/search on the FastAPI side.

export interface AuthUser {
  id: number;
  username: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface SearchResultItem {
  movie_id: number;
  title: string;
  score: number;
  vector_score: number;
  keyword_score: number;
}

export interface SearchResponse {
  query: string;
  k: number;
  results: SearchResultItem[];
}

export interface Intent {
  semantic_query: string;
  genres: string[];
  moods: string[];
  decade: string | null;
  year_min: number | null;
  year_max: number | null;
  min_popularity: number | null;
  cast: string[];
  similar_to: string[];
  exclude_seen: boolean;
  unsupported: string[];
}

export interface Pick {
  movie_id: number;
  title: string;
  score: number;
  why: string;
  based_on: string[];
}

export type AgentName = "preference" | "retrieval" | "critic" | "explainer";

export interface AgentStep {
  agent: AgentName;
  ms: number;
  ok: boolean;
  error: string | null;
  detail: Record<string, unknown>;
}

export interface ConciergeResponse {
  request: string;
  intent: Intent | null;
  picks: Pick[];
  trace: AgentStep[];
  fallback: boolean;
  fallback_reason?: string;
  fallback_model?: string;
}
