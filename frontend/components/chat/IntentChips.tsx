import { Badge } from "@/components/ui/badge";
import type { Intent } from "@/lib/types";
import { cleanTitle } from "@/lib/utils";

/** The parsed intent, surfaced as chips — including the honest "noted, not
 *  enforced" badges for constraints we understood but have no data to filter on. */
export function IntentChips({ intent }: { intent: Intent }) {
  const chips: string[] = [];
  intent.genres.forEach((g) => chips.push(g));
  if (intent.decade) chips.push(intent.decade);
  else if (intent.year_min || intent.year_max)
    chips.push(`${intent.year_min ?? "…"}–${intent.year_max ?? "…"}`);
  intent.cast.forEach((c) => chips.push(c));
  intent.similar_to.forEach((s) => chips.push(`like ${cleanTitle(s)}`));

  if (chips.length === 0 && intent.unsupported.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-1.5">
      {chips.map((c, i) => (
        <Badge key={`c${i}`} variant="secondary" className="font-normal">
          {c}
        </Badge>
      ))}
      {intent.unsupported.map((u, i) => (
        <Badge
          key={`u${i}`}
          variant="outline"
          className="border-primary/40 font-normal text-primary/90"
          title="Understood, but there's no data to filter on this yet"
        >
          ⚠ {u} · noted, not enforced
        </Badge>
      ))}
    </div>
  );
}
