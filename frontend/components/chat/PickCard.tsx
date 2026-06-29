import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import type { Pick } from "@/lib/types";
import { cleanTitle, parseYear } from "@/lib/utils";

export function PickCard({ pick, rank }: { pick: Pick; rank: number }) {
  const year = parseYear(pick.title);
  const match = Math.max(0, Math.min(1, pick.score));

  return (
    <Card className="flex flex-col gap-3 border-border bg-gradient-to-b from-card to-secondary/40 p-4 transition-colors hover:border-primary/40">
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

      {pick.why && (
        <p className="text-sm leading-relaxed text-foreground/90">{pick.why}</p>
      )}

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
    </Card>
  );
}
