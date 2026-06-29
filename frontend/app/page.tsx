import { AuthControl } from "@/components/rail/AuthControl";
import { Badge } from "@/components/ui/badge";

export default function Home() {
  return (
    <main className="flex min-h-dvh flex-col">
      <header className="flex items-center justify-between px-6 py-4">
        <span className="font-serif text-lg font-semibold">
          Cine<span className="text-primary">Mind</span>
        </span>
        <AuthControl />
      </header>

      <div className="grid flex-1 place-items-center px-6">
        <div className="max-w-xl text-center">
          <p className="text-xs uppercase tracking-[0.2em] text-primary">
            Every pick, explained
          </p>
          <h1 className="mt-4 font-serif text-6xl font-semibold tracking-tight">
            Cine<span className="text-primary">Mind</span>
          </h1>
          <p className="mx-auto mt-5 max-w-md text-balance text-muted-foreground">
            A conversational film concierge. Describe a vibe; get grounded,
            transparent recommendations — with the reasoning shown.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-2">
            <Badge variant="secondary">Sign in to begin</Badge>
            <Badge variant="secondary">Auth ready</Badge>
            <Badge className="bg-primary text-primary-foreground">FE-2</Badge>
          </div>
          <p className="mt-6 text-sm text-muted-foreground/70">
            The conversational concierge lands in the next phase.
          </p>
        </div>
      </div>
    </main>
  );
}
