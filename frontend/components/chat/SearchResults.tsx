import { Card } from "@/components/ui/card";
import type { SearchResultItem } from "@/lib/types";
import { cleanTitle, parseYear } from "@/lib/utils";
import { Poster } from "./Poster";

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
        return (
          <Card
            key={r.movie_id}
            className="flex items-center gap-3 border-border bg-card/60 p-2 pr-3"
          >
            <span className="w-4 shrink-0 text-center text-xs tabular-nums text-muted-foreground">
              {i + 1}
            </span>
            <Poster
              path={r.poster_path}
              alt={cleanTitle(r.title)}
              size="w92"
              sizes="40px"
              className="aspect-[2/3] w-10 shrink-0 rounded"
            />
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
          </Card>
        );
      })}
    </div>
  );
}
