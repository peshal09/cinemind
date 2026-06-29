import { Skeleton } from "@/components/ui/skeleton";
import type { ConciergeResponse, SearchResultItem } from "@/lib/types";
import { AgentTrace } from "./AgentTrace";
import { FallbackBanner } from "./FallbackBanner";
import { IntentChips } from "./IntentChips";
import { PickCard } from "./PickCard";
import { SearchResults } from "./SearchResults";

export type TurnKind = "concierge" | "search";

export type TurnData = {
  id: string;
  kind: TurnKind;
  request: string;
  status: "loading" | "done" | "error";
  response?: ConciergeResponse; // concierge
  results?: SearchResultItem[]; // search
  error?: string;
};

export function Turn({ turn }: { turn: TurnData }) {
  const label = turn.kind === "search" ? "Semantic search" : "CineMind";

  return (
    <div className="space-y-4">
      {/* the user's request */}
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-2xl rounded-br-sm border border-border bg-secondary px-4 py-2.5 text-[15px]">
          {turn.request}
        </div>
      </div>

      {/* the response */}
      <div className="space-y-3">
        <div className="flex items-center gap-2 text-xs uppercase tracking-[0.12em] text-primary">
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-primary" />
          {label}
        </div>

        {turn.status === "loading" && <LoadingState kind={turn.kind} />}

        {turn.status === "error" && (
          <p className="text-sm text-destructive-foreground/90">{turn.error}</p>
        )}

        {turn.status === "done" &&
          (turn.kind === "search" ? (
            <SearchResults results={turn.results ?? []} />
          ) : turn.response ? (
            <ConciergeResponseView response={turn.response} />
          ) : null)}
      </div>
    </div>
  );
}

function ConciergeResponseView({ response }: { response: ConciergeResponse }) {
  return (
    <>
      {response.fallback && <FallbackBanner res={response} />}
      {response.intent && <IntentChips intent={response.intent} />}
      {response.picks.length > 0 ? (
        <div className="grid gap-3 sm:grid-cols-2">
          {response.picks.map((p, i) => (
            <PickCard key={p.movie_id} pick={p} rank={i + 1} />
          ))}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">
          No picks found — try rephrasing.
        </p>
      )}
      <AgentTrace trace={response.trace} />
    </>
  );
}

function LoadingState({ kind }: { kind: TurnKind }) {
  if (kind === "search") {
    return (
      <div className="space-y-2">
        {[0, 1, 2, 3, 4].map((i) => (
          <Skeleton key={i} className="h-12 rounded-xl" />
        ))}
      </div>
    );
  }
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
