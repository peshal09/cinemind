import { Badge } from "@/components/ui/badge";

export default function Home() {
  return (
    <main className="grid min-h-dvh place-items-center px-6">
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
          <Badge variant="secondary">Next.js 14</Badge>
          <Badge variant="secondary">Tailwind</Badge>
          <Badge variant="secondary">shadcn/ui</Badge>
          <Badge className="bg-primary text-primary-foreground">scaffold ready</Badge>
        </div>
        <p className="mt-6 text-sm text-muted-foreground/70">
          Chat, auth, and the agent trace land in the next phases.
        </p>
      </div>
    </main>
  );
}
