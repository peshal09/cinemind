import type { ConciergeResponse } from "@/lib/types";

/** Shown when the pipeline degraded to the Phase-3 recommender (fallback: true). */
export function FallbackBanner({ res }: { res: ConciergeResponse }) {
  return (
    <div className="rounded-lg border border-primary/30 bg-primary/5 px-3 py-2 text-sm text-muted-foreground">
      The concierge hit a snag
      {res.fallback_reason ? ` (${res.fallback_reason})` : ""}, so these picks come
      from the{" "}
      <span className="font-medium text-foreground">
        {res.fallback_model ?? "baseline"}
      </span>{" "}
      recommender.
    </div>
  );
}
