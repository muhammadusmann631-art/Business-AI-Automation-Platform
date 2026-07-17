"use client";

import { useEffect, useState } from "react";
import { getToken, getUser } from "./lib/api";

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

// The full multi-agent architecture, grouped by role.
const AGENT_GROUPS: { group: string; items: { icon: string; name: string; desc: string }[] }[] = [
  {
    group: "Orchestration",
    items: [
      { icon: "🧠", name: "Supervisor", desc: "The manager. Understands your request and coordinates everything." },
      { icon: "🗺️", name: "Planner", desc: "Breaks complex requests into clear, ordered steps." },
      { icon: "🔀", name: "Router", desc: "Decides the fastest path — simple questions get instant answers, complex ones get the full pipeline." },
    ],
  },
  {
    group: "Intelligence",
    items: [
      { icon: "💾", name: "Memory", desc: "Remembers your conversation and preferences across sessions." },
      { icon: "⚙️", name: "Worker", desc: "Executes each step using the right tools." },
    ],
  },
  {
    group: "Data & Tools",
    items: [
      { icon: "🗄️", name: "Database", desc: "Securely queries your sales, customers, invoices, and expenses (read-only)." },
      { icon: "📄", name: "Report", desc: "Generates professional PDF reports." },
      { icon: "📊", name: "Excel", desc: "Exports data to spreadsheets." },
      { icon: "📈", name: "Charts", desc: "Creates visual graphs from your data." },
      { icon: "📧", name: "Email", desc: "Drafts and sends professional emails." },
    ],
  },
  {
    group: "Safety & Quality",
    items: [
      { icon: "🛡️", name: "QA / Reviewer", desc: "Checks every output for accuracy, completeness, and sensitive data before it reaches you." },
      { icon: "✋", name: "Approval", desc: "Pauses risky actions (like sending emails) for your explicit approval." },
      { icon: "♻️", name: "Resilience", desc: "Retries on failure, never loses your work, alerts on problems." },
    ],
  },
  {
    group: "Insight & Learning",
    items: [
      { icon: "🔎", name: "Tracer", desc: "Records every step for full transparency — see exactly what happened." },
      { icon: "🌱", name: "Feedback", desc: "Learns from your corrections to improve over time." },
      { icon: "🔔", name: "Alerts", desc: "Proactively warns you about overdue invoices, low stock, and more." },
    ],
  },
];

export default function Landing() {
  const [loggedIn, setLoggedIn] = useState(false);
  const [name, setName] = useState<string | undefined>();

  // We do NOT redirect logged-in users away — the landing is the front door
  // for everyone. We only adapt the primary button.
  useEffect(() => {
    if (getToken()) {
      setLoggedIn(true);
      setName(getUser()?.name);
    }
  }, []);

  const primaryHref = loggedIn ? "/chat" : "/signup";
  const primaryLabel = loggedIn ? "Enter AGI-CORE →" : "Get Started Free";

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
            {loggedIn ? (
              <>
                {name && (
                  <span className="mr-1 hidden text-xs text-emerald-200/50 sm:inline">
                    Welcome back, {name}
                  </span>
                )}
                <a
                  href="/chat"
                  className="rounded-xl bg-gradient-to-br from-emerald-400 to-teal-500 px-4 py-2 text-xs font-semibold text-black shadow-lg shadow-emerald-500/25 transition hover:from-emerald-300 hover:to-teal-400 active:scale-95"
                >
                  Enter AGI-CORE →
                </a>
              </>
            ) : (
              <>
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
              </>
            )}
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
              href={primaryHref}
              className="rounded-xl bg-gradient-to-br from-emerald-400 to-teal-500 px-6 py-3 text-sm font-semibold text-black shadow-lg shadow-emerald-500/25 transition hover:from-emerald-300 hover:to-teal-400 active:scale-95"
            >
              {primaryLabel}
            </a>
            <a
              href={loggedIn ? "/dashboard" : "/login"}
              className="rounded-xl border border-emerald-500/30 bg-emerald-500/[0.04] px-6 py-3 text-sm font-semibold text-emerald-200 transition hover:bg-emerald-500/10"
            >
              {loggedIn ? "Dashboard" : "Login"}
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

      {/* Inside AGI-CORE — agent showcase */}
      <section className="relative overflow-hidden border-y border-emerald-500/10 bg-emerald-500/[0.02]">
        <div className="hero-glow" />
        <div className="relative mx-auto max-w-6xl px-4 py-16">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-emerald-500/30 bg-emerald-500/10 text-2xl shadow-lg shadow-emerald-500/20">
            ✦
          </div>
          <h2 className="text-center text-2xl font-bold text-emerald-200">
            Inside AGI-CORE — A team of specialized agents
          </h2>
          <p className="mx-auto mt-3 max-w-2xl text-center text-sm text-emerald-100/55">
            Not a simple chatbot. A complete system where each agent has a job — planning,
            remembering, querying, checking, and learning — all working together so you don&apos;t
            have to.
          </p>

          <div className="mt-10 space-y-8">
            {AGENT_GROUPS.map((g) => (
              <div key={g.group}>
                <h3 className="mb-3 text-xs font-semibold uppercase tracking-[0.2em] text-emerald-300/60">
                  {g.group}
                </h3>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {g.items.map((c) => (
                    <div
                      key={c.name}
                      className="feature-card flex gap-3 rounded-xl border border-emerald-500/15 bg-[#070c0a] p-4"
                    >
                      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-emerald-500/10 text-lg">
                        {c.icon}
                      </span>
                      <div>
                        <p className="text-sm font-bold text-emerald-100">{c.name}</p>
                        <p className="mt-0.5 text-xs text-emerald-100/55">{c.desc}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
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
        <h2 className="text-3xl font-bold text-emerald-100">
          {loggedIn ? "Welcome back — ready to dive in?" : "Ready to automate your business work?"}
        </h2>
        <p className="mt-3 text-emerald-100/60">
          {loggedIn ? "Your assistant is standing by." : "Get started in minutes. No credit card required."}
        </p>
        <a
          href={primaryHref}
          className="mt-7 inline-block rounded-xl bg-gradient-to-br from-emerald-400 to-teal-500 px-8 py-3.5 text-sm font-semibold text-black shadow-lg shadow-emerald-500/25 transition hover:from-emerald-300 hover:to-teal-400 active:scale-95"
        >
          {primaryLabel}
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
