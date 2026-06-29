import { ConciergeView } from "@/components/chat/ConciergeView";
import { AuthControl } from "@/components/rail/AuthControl";

export default function Home() {
  return (
    <div className="flex h-dvh flex-col">
      <header className="flex items-center justify-between border-b border-border px-6 py-3">
        <span className="font-serif text-lg font-semibold">
          Cine<span className="text-primary">Mind</span>
        </span>
        <AuthControl />
      </header>
      <ConciergeView />
    </div>
  );
}
