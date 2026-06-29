import { Card } from "@/components/ui/card";
import type { SearchResultItem } from "@/lib/types";
import { cleanTitle, parseYear } from "@/lib/utils";

/** Lighter result rows for semantic search (no LLM reasoning, just ranked matches). */
export function SearchResults({ results }: { results: SearchResultItem[] }) {
  if (results.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No matches — try different words.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {results.map((r, i) => {
        const year = parseYear(r.title);
        const match = Math.max(0, Math.min(1, r.score));
        return (
          <Card
            key={r.movie_id}
            className="flex items-center gap-3 border-border bg-card/60 px-3 py-2.5"
          >
            <span className="w-5 shrink-0 text-xs tabular-nums text-muted-foreground">
              {i + 1}
            </span>
            <div className="min-w-0 flex-1">
              <span className="font-serif text-[15px] font-medium">
                {cleanTitle(r.title)}
              </span>
              {year && (
                <span className="ml-2 text-xs tabular-nums text-muted-foreground">
                  {year}
                </span>
              )}
            </div>
            <div
              className="flex w-28 shrink-0 items-center gap-2"
              title={`semantic ${r.vector_score.toFixed(2)} · title ${r.keyword_score.toFixed(2)}`}
            >
              <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-background">
                <div
                  className="h-full rounded-full bg-primary"
                  style={{ width: `${match * 100}%` }}
                />
              </div>
              <span className="w-9 text-right text-xs tabular-nums text-muted-foreground">
                {match.toFixed(2)}
              </span>
            </div>
          </Card>
        );
      })}
    </div>
  );
}
