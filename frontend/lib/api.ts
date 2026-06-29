// Typed fetch client for the CineMind API. Base URL is configurable so the same
// build works against local dev and a deployed backend.

import type {
  AuthUser,
  ConciergeResponse,
  SearchResponse,
  TokenResponse,
} from "./types";

export const API_BASE = (
  process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000"
).replace(/\/+$/, "");

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(
  path: string,
  opts: { method?: string; body?: unknown; token?: string | null } = {},
): Promise<T> {
  const { method = "GET", body, token } = opts;
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  let data: unknown = null;
  try {
    data = await res.json();
  } catch {
    /* non-JSON response */
  }

  if (!res.ok) {
    const detail =
      (data as { detail?: unknown })?.detail ?? res.statusText ?? "Request failed";
    throw new ApiError(
      res.status,
      typeof detail === "string" ? detail : JSON.stringify(detail),
    );
  }
  return data as T;
}

export const api = {
  register: (username: string, password: string) =>
    request<AuthUser>("/auth/register", {
      method: "POST",
      body: { username, password },
    }),
  login: (username: string, password: string) =>
    request<TokenResponse>("/auth/login", {
      method: "POST",
      body: { username, password },
    }),
  me: (token: string) => request<AuthUser>("/auth/me", { token }),
  search: (query: string, k = 10) =>
    request<SearchResponse>("/search/semantic", {
      method: "POST",
      body: { query, k },
    }),
  concierge: (request_: string, k: number, token: string) =>
    request<ConciergeResponse>("/concierge", {
      method: "POST",
      body: { request: request_, k },
      token,
    }),
};
