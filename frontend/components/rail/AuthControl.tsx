"use client";

import { useState } from "react";
import { toast } from "sonner";

import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";

type Mode = "login" | "register";

export function AuthControl() {
  const { user, loading, login, register, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<Mode>("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  if (loading) {
    return <div className="h-9 w-24 animate-pulse rounded-md bg-muted" />;
  }

  if (user) {
    return (
      <div className="flex items-center gap-3 text-sm">
        <span className="text-muted-foreground">
          Signed in as{" "}
          <span className="font-medium text-foreground">{user.username}</span>
        </span>
        <Button variant="ghost" size="sm" onClick={logout}>
          Sign out
        </Button>
      </div>
    );
  }

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    try {
      if (mode === "login") await login(username.trim(), password);
      else await register(username.trim(), password);
      toast.success(mode === "login" ? "Welcome back" : "Account created");
      setOpen(false);
      setPassword("");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button className="bg-primary text-primary-foreground hover:bg-primary/90">
          Sign in
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle className="font-serif text-2xl">
            {mode === "login" ? "Welcome back" : "Create your account"}
          </DialogTitle>
          <DialogDescription>
            {mode === "login"
              ? "Sign in to get personalized, explained picks."
              : "Register to start building your taste profile."}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={onSubmit} className="space-y-3">
          <div className="space-y-1.5">
            <label htmlFor="username" className="text-sm text-muted-foreground">
              Username
            </label>
            <Input
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              minLength={3}
              required
            />
          </div>
          <div className="space-y-1.5">
            <label htmlFor="password" className="text-sm text-muted-foreground">
              Password
            </label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              minLength={6}
              required
            />
          </div>
          <Button
            type="submit"
            disabled={busy}
            className="w-full bg-primary text-primary-foreground hover:bg-primary/90"
          >
            {busy ? "…" : mode === "login" ? "Sign in" : "Create account"}
          </Button>
        </form>

        <p className="text-center text-sm text-muted-foreground">
          {mode === "login" ? (
            <>
              New here?{" "}
              <button
                type="button"
                className="text-primary underline-offset-2 hover:underline"
                onClick={() => setMode("register")}
              >
                Create an account
              </button>
            </>
          ) : (
            <>
              Have an account?{" "}
              <button
                type="button"
                className="text-primary underline-offset-2 hover:underline"
                onClick={() => setMode("login")}
              >
                Sign in
              </button>
            </>
          )}
        </p>
      </DialogContent>
    </Dialog>
  );
}
