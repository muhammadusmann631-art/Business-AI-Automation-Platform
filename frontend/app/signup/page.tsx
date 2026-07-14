"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function Signup() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) return setError("Enter a valid email.");
    if (password.length < 8) return setError("Password must be at least 8 characters.");
    if (password !== confirm) return setError("Passwords do not match.");
    setBusy(true);
    try {
      const res = await fetch("/api/auth/signup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, email, password }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(typeof data?.detail === "string" ? data.detail : "Signup failed");
      router.replace("/login?created=1");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Signup failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-full items-center justify-center bg-[#050807] px-4 py-8 font-sans text-emerald-50/90">
      <div className="w-full max-w-sm">
        <div className="mb-6 text-center">
          <div className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-2xl border border-emerald-500/30 bg-emerald-500/10 text-2xl shadow-lg shadow-emerald-500/10">
            ✦
          </div>
          <h1 className="text-xl font-bold tracking-[0.2em] text-emerald-300">AGI · CORE</h1>
          <p className="mt-1 text-xs text-emerald-200/40">Create your account</p>
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
          {[
            { label: "Name", v: name, set: setName, type: "text", ph: "Your name" },
            { label: "Email", v: email, set: setEmail, type: "email", ph: "you@example.com" },
            { label: "Password", v: password, set: setPassword, type: "password", ph: "min 8 chars" },
            { label: "Confirm Password", v: confirm, set: setConfirm, type: "password", ph: "repeat password" },
          ].map((f) => (
            <label key={f.label} className="block">
              <span className="mb-1 block text-[10px] font-semibold uppercase tracking-wide text-emerald-300/50">
                {f.label}
              </span>
              <input
                type={f.type}
                required
                value={f.v}
                onChange={(e) => f.set(e.target.value)}
                placeholder={f.ph}
                className="w-full rounded-lg border border-emerald-500/20 bg-black/30 px-3 py-2 text-sm text-emerald-50 outline-none focus:border-emerald-400/50"
              />
            </label>
          ))}
          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-lg bg-gradient-to-br from-emerald-400 to-teal-500 px-4 py-2.5 text-sm font-semibold text-black shadow-lg shadow-emerald-500/25 transition hover:from-emerald-300 hover:to-teal-400 active:scale-95 disabled:opacity-40"
          >
            {busy ? "Creating…" : "Create Account"}
          </button>
          <p className="pt-1 text-center text-xs text-emerald-200/40">
            Already have an account?{" "}
            <a href="/login" className="font-semibold text-emerald-300 hover:text-emerald-200">
              Sign In
            </a>
          </p>
        </form>
      </div>
    </main>
  );
}
