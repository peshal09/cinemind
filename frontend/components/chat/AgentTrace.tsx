import { Fragment } from "react";

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import type { AgentName, AgentStep } from "@/lib/types";
import { cn, formatMs } from "@/lib/utils";

const AGENT_META: Record<AgentName, { label: string; role: string }> = {
  preference: { label: "Preference", role: "understood your request" },
  retrieval: { label: "Retrieval", role: "gathered candidates" },
  critic: { label: "Critic", role: "filtered & ranked" },
  explainer: { label: "Explainer", role: "wrote the explanations" },
};

/** The per-agent "show your work" timeline: each step's timing, status, and the
 *  internal detail it returned (which varies per agent). */
export function AgentTrace({ trace }: { trace: AgentStep[] }) {
  if (!trace || trace.length === 0) return null;
  const total = trace.reduce((sum, s) => sum + (s.ms || 0), 0);

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card/40">
      <div className="flex items-center justify-between px-4 py-2.5">
        <span className="text-xs font-medium uppercase tracking-[0.12em] text-muted-foreground">
          Show your work · {trace.length} agents
        </span>
        <span className="text-xs tabular-nums text-muted-foreground">
          {formatMs(total)} total
        </span>
      </div>

      <Accordion type="multiple" className="px-2 pb-2">
        {trace.map((step, i) => {
          const meta = AGENT_META[step.agent] ?? { label: step.agent, role: "" };
          return (
            <AccordionItem key={i} value={`${i}`} className="border-border/60">
              <AccordionTrigger className="py-2.5 hover:no-underline">
                <div className="flex w-full items-center gap-3 pr-2 text-left">
                  <span
                    className={cn(
                      "h-2 w-2 shrink-0 rounded-full",
                      step.ok ? "bg-primary" : "bg-destructive",
                    )}
                  />
                  <span className="text-sm font-medium">{meta.label}</span>
                  <span className="truncate text-xs text-muted-foreground">
                    {step.ok ? meta.role : step.error ?? "failed"}
                  </span>
                  <span className="ml-auto shrink-0 text-xs tabular-nums text-muted-foreground">
                    {formatMs(step.ms)}
                  </span>
                </div>
              </AccordionTrigger>
              <AccordionContent>
                <DetailGrid detail={step.detail} />
              </AccordionContent>
            </AccordionItem>
          );
        })}
      </Accordion>
    </div>
  );
}

function humanize(key: string): string {
  return key.replace(/_/g, " ");
}

function DetailGrid({ detail }: { detail: Record<string, unknown> }) {
  const entries = Object.entries(detail ?? {});
  if (entries.length === 0) {
    return <p className="px-3 pb-2 text-xs text-muted-foreground">No details.</p>;
  }
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 px-3 pb-3 text-sm">
      {entries.map(([k, v]) => (
        <Fragment key={k}>
          <dt className="text-muted-foreground">{humanize(k)}</dt>
          <dd className="min-w-0">
            <DetailValue keyName={k} value={v} />
          </dd>
        </Fragment>
      ))}
    </dl>
  );
}

function renderScalar(v: unknown): string {
  if (v === null || v === undefined || v === "") return "—";
  if (Array.isArray(v)) return v.length ? v.map(String).join(", ") : "—";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

function DetailValue({ keyName, value }: { keyName: string; value: unknown }) {
  if (value === null || value === undefined || value === "") {
    return <span className="text-muted-foreground">—</span>;
  }
  if (typeof value === "boolean") return <span>{value ? "yes" : "no"}</span>;
  if (typeof value === "number" || typeof value === "string") {
    return <span className="break-words">{String(value)}</span>;
  }

  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="text-muted-foreground">—</span>;
    const amber = keyName === "noted_not_enforced" || keyName === "unsupported";
    if (value.every((x) => typeof x === "string" || typeof x === "number")) {
      return (
        <div className="flex flex-wrap gap-1">
          {value.map((x, i) => (
            <Badge
              key={i}
              variant="outline"
              className={cn(
                "font-normal",
                amber && "border-primary/40 text-primary/90",
              )}
            >
              {String(x)}
            </Badge>
          ))}
        </div>
      );
    }
    return <code className="text-xs break-all">{JSON.stringify(value)}</code>;
  }

  // a nested object — render one level of key: value inline
  const nested = Object.entries(value as Record<string, unknown>);
  return (
    <div className="flex flex-wrap gap-x-3 gap-y-0.5">
      {nested.map(([k, v]) => (
        <span key={k} className="text-xs">
          <span className="text-muted-foreground">{humanize(k)}:</span>{" "}
          {renderScalar(v)}
        </span>
      ))}
    </div>
  );
}
