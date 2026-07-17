"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { getToken } from "./lib/api";

const FEATURES = [
  {
    icon: "💬",
    title: "Ask Anything",
    body: "Query your sales, customers, invoices, and expenses in plain English or Urdu. No SQL, no spreadsheets.",
  },
  {
    icon: "📊",
    title: "Instant Reports & Charts",
    body: "Generate PDF reports, Excel exports, and visual charts with a single request.",
  },
  {
    icon: "📧",
    title: "Smart Email",
    body: "Draft and send professional emails. Send bulk reminders to all overdue clients at once — with one approval.",
  },
  {
    icon: "📱",
    title: "WhatsApp Ready",
    body: "Manage your business right from WhatsApp. Ask questions, get reports, approve actions — on the go.",
  },
  {
    icon: "📈",
    title: "Profit & Loss + Alerts",
    body: "See your P&L instantly. Get automatic alerts for overdue invoices, low stock, and expense spikes.",
  },
  {
    icon: "🎙️",
    title: "Voice Input",
    body: "Too busy to type? Just speak. Your voice becomes action.",
  },
];

const STEPS = [
  { n: "1", title: "Ask", body: "Type or speak your request: “Show me June's overdue invoices.”" },
  {
    n: "2",
    title: "AGI-CORE works",
    body: "The system plans, queries your data, and prepares the result — checking everything before it reaches you.",
  },
  {
    n: "3",
    title: "You approve",
    body: "Review and approve important actions. The AI does the work; you stay in control.",
  },
];

const STATS = [
  { big: "5 min", small: "Average time saved per report (vs 3 hours manually)" },
  { big: "10+ tools", small: "Data, reports, charts, email, and more" },
  { big: "24/7", small: "Available on web and WhatsApp" },
];

export default function Landing() {
  const router = useRouter();

  // Logged-in visitors are sent straight to the app. The landing still renders
  // (good for SSR/SEO); the redirect happens right after hydration.
  useEffect(() => {
    if (getToken()) router.replace("/chat");
  }, [router]);

  return (
    <main className="min-h-full bg-[#050807] font-sans text-emerald-50/90">
      <style>{CSS}</style>

      {/* Nav */}
      <header className="sticky top-0 z-20 border-b border-emerald-500/10 bg-[#050807]/80 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-2 text-emerald-300">
            <span className="text-lg">✦</span>
            <span className="text-sm font-semibold tracking-[0.3em]">AGI · CORE</span>
          </div>
          <nav className="flex items-center gap-2">
            <a
              href="/login"
              className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 px-4 py-2 text-xs font-semibold text-emerald-300/80 transition hover:bg-emerald-500/10"
            >
              Login
            </a>
            <a
              href="/signup"
              className="rounded-xl bg-gradient-to-br from-emerald-400 to-teal-500 px-4 py-2 text-xs font-semibold text-black shadow-lg shadow-emerald-500/25 transition hover:from-emerald-300 hover:to-teal-400 active:scale-95"
            >
              Sign Up
            </a>
          </nav>
        </div>
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="hero-glow" />
        <div className="relative mx-auto max-w-4xl px-4 py-24 text-center">
          <div className="fade-up mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-3xl border border-emerald-500/30 bg-emerald-500/10 text-3xl shadow-xl shadow-emerald-500/20">
            ✦
          </div>
          <h1 className="fade-up bg-gradient-to-r from-emerald-300 via-teal-200 to-emerald-300 bg-clip-text text-4xl font-bold leading-tight text-transparent sm:text-5xl">
            AGI-CORE — Your AI Business Assistant
          </h1>
          <p className="fade-up mx-auto mt-5 max-w-2xl text-base text-emerald-100/60 sm:text-lg">
            Ask in plain language. Get reports, charts, emails, and insights — in seconds. The work
            that takes hours, done in minutes.
          </p>
          <div className="fade-up mt-8 flex flex-wrap items-center justify-center gap-3">
            <a
              href="/signup"
              className="rounded-xl bg-gradient-to-br from-emerald-400 to-teal-500 px-6 py-3 text-sm font-semibold text-black shadow-lg shadow-emerald-500/25 transition hover:from-emerald-300 hover:to-teal-400 active:scale-95"
            >
              Get Started Free
            </a>
            <a
              href="/login"
              className="rounded-xl border border-emerald-500/30 bg-emerald-500/[0.04] px-6 py-3 text-sm font-semibold text-emerald-200 transition hover:bg-emerald-500/10"
            >
              Login
            </a>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="mx-auto max-w-6xl px-4 py-16">
        <h2 className="mb-10 text-center text-2xl font-bold text-emerald-200">
          Everything your business needs, in one assistant
        </h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <div
              key={f.title}
              className="feature-card rounded-2xl border border-emerald-500/15 bg-emerald-500/[0.05] p-5"
            >
              <div className="mb-3 flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-500/10 text-xl">
                {f.icon}
              </div>
              <h3 className="mb-1 text-base font-bold text-emerald-100">{f.title}</h3>
              <p className="text-sm text-emerald-100/60">{f.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className="mx-auto max-w-5xl px-4 py-16">
        <h2 className="mb-10 text-center text-2xl font-bold text-emerald-200">How it works</h2>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {STEPS.map((s) => (
            <div
              key={s.n}
              className="rounded-2xl border border-emerald-500/15 bg-emerald-500/[0.05] p-6 text-center"
            >
              <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full border border-emerald-400/40 bg-emerald-500/10 text-sm font-bold text-emerald-300">
                {s.n}
              </div>
              <h3 className="mb-1 text-base font-bold text-emerald-100">{s.title}</h3>
              <p className="text-sm text-emerald-100/60">{s.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Stats */}
      <section className="mx-auto max-w-5xl px-4 py-10">
        <div className="grid grid-cols-1 gap-4 rounded-2xl border border-emerald-500/15 bg-emerald-500/[0.04] p-8 sm:grid-cols-3">
          {STATS.map((s) => (
            <div key={s.big} className="text-center">
              <p className="text-3xl font-bold text-emerald-300">{s.big}</p>
              <p className="mt-1 text-xs text-emerald-100/50">{s.small}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="mx-auto max-w-3xl px-4 py-20 text-center">
        <h2 className="text-3xl font-bold text-emerald-100">Ready to automate your business work?</h2>
        <p className="mt-3 text-emerald-100/60">Get started in minutes. No credit card required.</p>
        <a
          href="/signup"
          className="mt-7 inline-block rounded-xl bg-gradient-to-br from-emerald-400 to-teal-500 px-8 py-3.5 text-sm font-semibold text-black shadow-lg shadow-emerald-500/25 transition hover:from-emerald-300 hover:to-teal-400 active:scale-95"
        >
          Get Started Free
        </a>
      </section>

      {/* Footer */}
      <footer className="border-t border-emerald-500/10 bg-[#04070a]">
        <div className="mx-auto flex max-w-6xl flex-col items-center gap-3 px-4 py-8 text-center sm:flex-row sm:justify-between sm:text-left">
          <div>
            <div className="flex items-center justify-center gap-2 text-emerald-300 sm:justify-start">
              <span>✦</span>
              <span className="text-sm font-semibold tracking-[0.3em]">AGI · CORE</span>
            </div>
            <p className="mt-1 text-xs text-emerald-100/40">Your AI business assistant.</p>
          </div>
          <div className="flex items-center gap-4 text-xs text-emerald-300/70">
            <a href="/login" className="transition hover:text-emerald-200">Login</a>
            <a href="/signup" className="transition hover:text-emerald-200">Sign Up</a>
          </div>
        </div>
        <p className="pb-6 text-center text-[11px] text-emerald-100/30">
          © {new Date().getFullYear()} AGI-CORE. Built with AGI-CORE.
        </p>
      </footer>
    </main>
  );
}

const CSS = `
.hero-glow {
  position: absolute; inset: 0;
  background: radial-gradient(circle at 50% 0%, rgba(16,74,58,0.5), transparent 55%);
  pointer-events: none;
}
@keyframes fadeUp { from { opacity: 0; transform: translateY(14px); } to { opacity: 1; transform: translateY(0); } }
.fade-up { animation: fadeUp 0.6s ease-out both; }
.fade-up:nth-child(2) { animation-delay: 0.05s; }
.fade-up:nth-child(3) { animation-delay: 0.1s; }
.fade-up:nth-child(4) { animation-delay: 0.15s; }
.feature-card { transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease; }
.feature-card:hover {
  transform: translateY(-3px);
  border-color: rgba(16,185,129,0.4);
  box-shadow: 0 10px 30px -10px rgba(16,185,129,0.25);
}
@media (prefers-reduced-motion: reduce) { .fade-up { animation: none; } }
`;
