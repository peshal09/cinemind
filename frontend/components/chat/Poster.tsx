import { Film } from "lucide-react";
import Image from "next/image";

import { cn, posterUrl } from "@/lib/utils";

/** A movie poster with a graceful fallback when TMDB has no image.
 *  The parent sets the box size + aspect via className; this fills it. */
export function Poster({
  path,
  alt,
  size = "w342",
  sizes = "200px",
  className,
}: {
  path: string | null | undefined;
  alt: string;
  size?: "w92" | "w185" | "w342" | "w500";
  sizes?: string;
  className?: string;
}) {
  const url = posterUrl(path, size);
  return (
    <div className={cn("relative overflow-hidden bg-secondary", className)}>
      {url ? (
        <Image src={url} alt={alt} fill sizes={sizes} className="object-cover" />
      ) : (
        <div className="flex h-full w-full items-center justify-center text-muted-foreground/40">
          <Film className="h-1/3 w-1/3" />
        </div>
      )}
    </div>
  );
}
