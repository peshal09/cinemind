import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import type { Pick } from "@/lib/types";
import { cleanTitle, parseYear } from "@/lib/utils";
import { Poster } from "./Poster";

export function PickCard({ pick, rank }: { pick: Pick; rank: number }) {
  const year = parseYear(pick.title);
  const match = Math.max(0, Math.min(1, pick.score));

  return (
    <Card className="flex gap-4 border-border bg-gradient-to-b from-card to-secondary/40 p-3 transition-colors hover:border-primary/40">
      <Poster
        path={pick.poster_path}
        alt={cleanTitle(pick.title)}
        size="w185"
        sizes="96px"
        className="aspect-[2/3] w-24 shrink-0 rounded-lg"
      />

      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="font-serif text-lg font-semibold leading-tight">
              {cleanTitle(pick.title)}
            </h3>
            {year && (
              <span className="text-sm tabular-nums text-muted-foreground">{year}</span>
            )}
          </div>
          <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
            #{rank}
          </span>
        </div>

        <div className="flex items-center gap-2" title="Relative match score">
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-background">
            <div
              className="h-full rounded-full bg-primary transition-[width] duration-500 ease-arthouse"
              style={{ width: `${match * 100}%` }}
            />
          </div>
          <span className="text-xs tabular-nums text-muted-foreground">
            {match.toFixed(2)}
          </span>
        </div>

        {pick.why ? (
          <p className="text-sm leading-relaxed text-foreground/90">{pick.why}</p>
        ) : pick.overview ? (
          // No personalized reason — show the plot synopsis (muted) instead of a blank card.
          <p className="text-sm leading-relaxed text-muted-foreground">{pick.overview}</p>
        ) : null}

        {pick.based_on.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
            <span>Because you liked:</span>
            {pick.based_on.map((b, i) => (
              <Badge key={i} variant="outline" className="font-normal">
                {cleanTitle(b)}
              </Badge>
            ))}
          </div>
        )}
      </div>
    </Card>
  );
}
