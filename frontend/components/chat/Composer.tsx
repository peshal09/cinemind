"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

export function Composer({
  disabled,
  placeholder,
  onSubmit,
}: {
  disabled?: boolean;
  placeholder?: string;
  onSubmit: (text: string) => void;
}) {
  const [text, setText] = useState("");

  function send() {
    const t = text.trim();
    if (!t || disabled) return;
    onSubmit(t);
    setText("");
  }

  return (
    <div className="border-t border-border bg-gradient-to-t from-background to-transparent px-4 py-4 sm:px-6">
      <div className="mx-auto flex max-w-3xl items-end gap-2 rounded-2xl border border-border bg-card p-2 pl-4 transition-colors focus-within:border-primary/60">
        <Textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          placeholder={placeholder ?? "What are you in the mood for?"}
          rows={1}
          disabled={disabled}
          className="max-h-40 min-h-0 resize-none border-0 bg-transparent p-0 py-2 text-[15px] shadow-none focus-visible:ring-0"
        />
        <Button
          size="icon"
          aria-label="Send"
          onClick={send}
          disabled={disabled || !text.trim()}
          className="h-10 w-10 shrink-0 bg-primary text-primary-foreground hover:bg-primary/90"
        >
          ↑
        </Button>
      </div>
      <p className="mx-auto mt-2 max-w-3xl text-center text-xs text-muted-foreground/70">
        Enter to send · Shift+Enter for a new line · grounded only in CineMind&apos;s
        catalog
      </p>
    </div>
  );
}
