import { Skeleton } from "@/components/ui/skeleton";
import type { ConciergeResponse } from "@/lib/types";
import { AgentTrace } from "./AgentTrace";
import { FallbackBanner } from "./FallbackBanner";
import { IntentChips } from "./IntentChips";
import { PickCard } from "./PickCard";

export type TurnData = {
  id: string;
  request: string;
  status: "loading" | "done" | "error";
  response?: ConciergeResponse;
  error?: string;
};

export function Turn({ turn }: { turn: TurnData }) {
  return (
    <div className="space-y-4">
      {/* the user's request */}
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-2xl rounded-br-sm border border-border bg-secondary px-4 py-2.5 text-[15px]">
          {turn.request}
        </div>
      </div>

      {/* CineMind's response */}
      <div className="space-y-3">
        <div className="flex items-center gap-2 text-xs uppercase tracking-[0.12em] text-primary">
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-primary" />
          CineMind
        </div>

        {turn.status === "loading" && <LoadingPicks />}

        {turn.status === "error" && (
          <p className="text-sm text-destructive-foreground/90">{turn.error}</p>
        )}

        {turn.status === "done" && turn.response && (
          <>
            {turn.response.fallback && <FallbackBanner res={turn.response} />}
            {turn.response.intent && <IntentChips intent={turn.response.intent} />}
            {turn.response.picks.length > 0 ? (
              <div className="grid gap-3 sm:grid-cols-2">
                {turn.response.picks.map((p, i) => (
                  <PickCard key={p.movie_id} pick={p} rank={i + 1} />
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                No picks found — try rephrasing.
              </p>
            )}
            <AgentTrace trace={turn.response.trace} />
          </>
        )}
      </div>
    </div>
  );
}

function LoadingPicks() {
  return (
    <div className="space-y-3">
      <p className="animate-pulse text-sm text-muted-foreground">
        The agents are working — understanding, retrieving, ranking, explaining…
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-32 rounded-xl" />
        ))}
      </div>
    </div>
  );
}
