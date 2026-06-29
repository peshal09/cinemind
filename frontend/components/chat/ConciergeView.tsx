"use client";

import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { ApiError, api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Composer } from "./Composer";
import { Turn, type TurnData, type TurnKind } from "./Turn";

const EXAMPLES = [
  "a mind-bending sci-fi like Inception but funnier, from the 90s",
  "cozy feel-good films for a rainy Sunday",
  "a slow-burn crime drama about family",
];

const RECENTS_KEY = "cinemind:recents";

export function ConciergeView() {
  const { user, token, loading } = useAuth();
  const [mode, setMode] = useState<TurnKind>("concierge");
  const [turns, setTurns] = useState<TurnData[]>([]);
  const [recents, setRecents] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const counter = useRef(0);

  useEffect(() => {
    try {
      const stored = JSON.parse(window.localStorage.getItem(RECENTS_KEY) ?? "[]");
      if (Array.isArray(stored)) setRecents(stored.filter((x) => typeof x === "string"));
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [turns]);

  function rememberRecent(q: string) {
    setRecents((prev) => {
      const next = [q, ...prev.filter((x) => x !== q)].slice(0, 8);
      window.localStorage.setItem(RECENTS_KEY, JSON.stringify(next));
      return next;
    });
  }

  async function ask(text: string) {
    if (busy) return;
    if (mode === "concierge" && !token) return; // composer is disabled in this state
    const id = `t${counter.current++}`;
    rememberRecent(text);
    setTurns((prev) => [...prev, { id, kind: mode, request: text, status: "loading" }]);
    setBusy(true);
    try {
      if (mode === "search") {
        const res = await api.search(text, 10);
        setTurns((prev) =>
          prev.map((t) =>
            t.id === id ? { ...t, status: "done", results: res.results } : t,
          ),
        );
      } else {
        const res = await api.concierge(text, 5, token!);
        setTurns((prev) =>
          prev.map((t) => (t.id === id ? { ...t, status: "done", response: res } : t)),
        );
      }
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Request failed";
      setTurns((prev) =>
        prev.map((t) => (t.id === id ? { ...t, status: "error", error: msg } : t)),
      );
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  }

  const signedIn = !!user;
  // Concierge needs auth; semantic search is public.
  const composerDisabled = busy || loading || (mode === "concierge" && !signedIn);

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-3xl space-y-8 px-4 py-8 sm:px-6">
          {turns.length === 0 ? (
            <EmptyState
              mode={mode}
              signedIn={signedIn}
              recents={recents}
              onPick={ask}
            />
          ) : (
            turns.map((t) => <Turn key={t.id} turn={t} />)
          )}
        </div>
      </div>

      <Composer
        mode={mode}
        onModeChange={setMode}
        disabled={composerDisabled}
        placeholder={
          mode === "search"
            ? "Search the catalog by meaning…"
            : signedIn
              ? "What are you in the mood for?"
              : "Sign in (top right) to ask the concierge"
        }
        onSubmit={ask}
      />
    </div>
  );
}

function EmptyState({
  mode,
  signedIn,
  recents,
  onPick,
}: {
  mode: TurnKind;
  signedIn: boolean;
  recents: string[];
  onPick: (text: string) => void;
}) {
  const canRun = mode === "search" || signedIn;
  return (
    <div className="mx-auto max-w-xl py-[8vh] text-center">
      <p className="text-xs uppercase tracking-[0.2em] text-primary">
        Every pick, explained
      </p>
      <h1 className="mt-3 font-serif text-4xl font-semibold sm:text-5xl">
        What are you in the mood for?
      </h1>
      <p className="mt-4 text-muted-foreground">
        Describe a vibe, a theme, a half-remembered plot. The concierge reasons in
        four steps and shows its work — or switch to plain semantic search.
      </p>

      {canRun ? (
        <div className="mt-7 flex flex-wrap justify-center gap-2">
          {EXAMPLES.map((e) => (
            <button
              key={e}
              onClick={() => onPick(e)}
              className="rounded-full border border-border bg-card px-4 py-2 text-sm text-muted-foreground transition-colors hover:border-primary/60 hover:text-foreground"
            >
              {e}
            </button>
          ))}
        </div>
      ) : (
        <p className="mt-7 text-sm text-muted-foreground">
          Sign in (top right) to begin — or switch to Search below (no sign-in
          needed).
        </p>
      )}

      {recents.length > 0 && (
        <div className="mt-8">
          <p className="text-xs uppercase tracking-[0.14em] text-muted-foreground/70">
            Recent
          </p>
          <div className="mt-2 flex flex-wrap justify-center gap-1.5">
            {recents.slice(0, 6).map((r) => (
              <button
                key={r}
                onClick={() => canRun && onPick(r)}
                disabled={!canRun}
                className="max-w-[16rem] truncate rounded-full border border-border/60 px-3 py-1 text-xs text-muted-foreground transition-colors hover:text-foreground disabled:opacity-50"
                title={r}
              >
                {r}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
