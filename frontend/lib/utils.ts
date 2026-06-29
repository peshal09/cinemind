import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** MovieLens titles look like "Inception (2010)" — pull the year out. */
export function parseYear(title: string): string | null {
  const m = /\((\d{4})\)\s*$/.exec(title);
  return m ? m[1] : null;
}

/** "Inception (2010)" -> "Inception" */
export function cleanTitle(title: string): string {
  return title.replace(/\s*\(\d{4}\)\s*$/, "").trim();
}

/** Compact duration for the agent trace. */
export function formatMs(ms: number): string {
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${Math.round(ms)}ms`;
}

/** Build a TMDB poster URL from a stored poster_path (e.g. "/abc.jpg"). */
export function posterUrl(
  path: string | null | undefined,
  size: "w92" | "w185" | "w342" | "w500" = "w342",
): string | null {
  return path ? `https://image.tmdb.org/t/p/${size}${path}` : null;
}
