"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { setAuth } from "../lib/api";

export default function Login() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof data?.detail === "string" ? data.detail : "Login failed");
      setAuth(data.token, data.user);
      router.replace("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-full items-center justify-center bg-[#050807] px-4 font-sans text-emerald-50/90">
      <div className="w-full max-w-sm">
        <div className="mb-6 text-center">
          <div className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-2xl border border-emerald-500/30 bg-emerald-500/10 text-2xl shadow-lg shadow-emerald-500/10">
            ✦
          </div>
          <h1 className="text-xl font-bold tracking-[0.2em] text-emerald-300">AGI · CORE</h1>
          <p className="mt-1 text-xs text-emerald-200/40">Sign in to continue</p>
        </div>

        <form
          onSubmit={submit}
          className="space-y-3 rounded-2xl border border-emerald-500/15 bg-emerald-500/[0.05] p-6"
        >
          {error && (
            <p className="rounded-lg border border-rose-400/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-300">
              {error}
            </p>
          )}
          <label className="block">
            <span className="mb-1 block text-[10px] font-semibold uppercase tracking-wide text-emerald-300/50">
              Email
            </span>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg border border-emerald-500/20 bg-black/30 px-3 py-2 text-sm text-emerald-50 outline-none focus:border-emerald-400/50"
              placeholder="you@example.com"
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-[10px] font-semibold uppercase tracking-wide text-emerald-300/50">
              Password
            </span>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-emerald-500/20 bg-black/30 px-3 py-2 text-sm text-emerald-50 outline-none focus:border-emerald-400/50"
              placeholder="••••••••"
            />
          </label>
          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-lg bg-gradient-to-br from-emerald-400 to-teal-500 px-4 py-2.5 text-sm font-semibold text-black shadow-lg shadow-emerald-500/25 transition hover:from-emerald-300 hover:to-teal-400 active:scale-95 disabled:opacity-40"
          >
            {busy ? "Signing in…" : "Sign In"}
          </button>
          <p className="pt-1 text-center text-xs text-emerald-200/40">
            Don&apos;t have an account?{" "}
            <a href="/signup" className="font-semibold text-emerald-300 hover:text-emerald-200">
              Sign Up
            </a>
          </p>
        </form>
        <p className="mt-3 text-center text-[10px] text-emerald-200/25">
          Demo admin: admin@agicore.com / admin123
        </p>
      </div>
    </main>
  );
}
