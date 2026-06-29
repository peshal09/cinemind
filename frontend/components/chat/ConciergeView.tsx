"use client";

import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { ApiError, api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Composer } from "./Composer";
import { Turn, type TurnData } from "./Turn";

const EXAMPLES = [
  "a mind-bending sci-fi like Inception but funnier, from the 90s",
  "cozy feel-good films for a rainy Sunday",
  "a slow-burn crime drama about family",
];

export function ConciergeView() {
  const { user, token, loading } = useAuth();
  const [turns, setTurns] = useState<TurnData[]>([]);
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const counter = useRef(0);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [turns]);

  async function ask(text: string) {
    if (!token || busy) return;
    const id = `t${counter.current++}`;
    setTurns((prev) => [...prev, { id, request: text, status: "loading" }]);
    setBusy(true);
    try {
      const res = await api.concierge(text, 5, token);
      setTurns((prev) =>
        prev.map((t) => (t.id === id ? { ...t, status: "done", response: res } : t)),
      );
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

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-3xl space-y-8 px-4 py-8 sm:px-6">
          {turns.length === 0 ? (
            <EmptyState signedIn={signedIn} onPick={ask} />
          ) : (
            turns.map((t) => <Turn key={t.id} turn={t} />)
          )}
        </div>
      </div>

      <Composer
        disabled={!signedIn || busy || loading}
        placeholder={
          signedIn
            ? "What are you in the mood for?"
            : "Sign in (top right) to ask the concierge"
        }
        onSubmit={ask}
      />
    </div>
  );
}

function EmptyState({
  signedIn,
  onPick,
}: {
  signedIn: boolean;
  onPick: (text: string) => void;
}) {
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
        four steps and shows its work.
      </p>
      {signedIn ? (
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
          Sign in (top right) to begin.
        </p>
      )}
    </div>
  );
}
