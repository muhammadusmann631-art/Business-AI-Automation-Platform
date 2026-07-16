"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiJson, getToken } from "../lib/api";
import BusinessOverview, { type BusinessStats } from "../components/BusinessOverview";
import AlertsBanner from "../components/AlertsBanner";

// Relative — Next.js rewrites proxy these to the backend (see next.config.ts).
const API_URL = "";

type Span = {
  span_id: string;
  name: string;
  input: string | null;
  output: string | null;
  duration_ms: number;
  tokens: number;
  status: string;
  metadata: unknown;
};

type Trace = {
  trace_id: string;
  session_id: string | null;
  message: string | null;
  route: string | null;
  total_duration_ms: number | null;
  total_tokens: number | null;
  status: string | null;
  response: string | null;
  created_at: string | null;
};

type Stats = {
  total_requests: number;
  avg_duration_ms: number;
  total_tokens: number;
  error_rate: number;
  tokens_by_route?: Record<string, { requests: number; tokens: number; avg_ms: number }>;
  slowest_tools?: { tool: string; calls: number; avg_ms: number }[];
};

type FeedbackStats = {
  total: number;
  positive: number;
  negative: number;
  positive_pct: number;
  negative_pct: number;
  by_category?: Record<string, number>;
  common_corrections?: { correction: string; count: number }[];
  recurring_issues?: { category: string; count: number; message: string }[];
};

type FeedbackEntry = {
  feedback_id: string;
  rating: string;
  category: string;
  user_correction: string;
  original_request: string;
  timestamp: string;
};

function statusColor(status: string | null | undefined): string {
  switch (status) {
    case "success":
    case "delivered":
      return "bg-emerald-500/15 text-emerald-300 border-emerald-400/30";
    case "error":
      return "bg-rose-500/15 text-rose-300 border-rose-400/30";
    case "warning":
    case "retry":
    case "pending":
      return "bg-amber-500/15 text-amber-300 border-amber-400/30";
    default:
      return "bg-slate-500/15 text-slate-300 border-slate-400/20";
  }
}

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [traces, setTraces] = useState<Trace[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [spans, setSpans] = useState<Record<string, Span[]>>({});
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [fbStats, setFbStats] = useState<FeedbackStats | null>(null);
  const [fbRecent, setFbRecent] = useState<FeedbackEntry[]>([]);
  const [biz, setBiz] = useState<BusinessStats | null>(null);
  const router = useRouter();

  useEffect(() => {
    if (!getToken()) router.replace("/login");
  }, [router]);

  const refresh = useCallback(async () => {
    try {
      const [s, t, fs, fr, bz] = await Promise.all([
        apiJson<Stats>(`${API_URL}/api/stats`),
        apiJson<{ traces: Trace[] }>(`${API_URL}/api/traces?limit=50`),
        apiJson<FeedbackStats>(`${API_URL}/api/feedback/stats`),
        apiJson<{ feedback: FeedbackEntry[] }>(`${API_URL}/api/feedback/recent?limit=20`),
        apiJson<BusinessStats>(`${API_URL}/api/dashboard/business-stats`),
      ]);
      setStats(s);
      setTraces(t.traces ?? []);
      setFbStats(fs);
      setFbRecent(fr.feedback ?? []);
      setBiz(bz);
      setLastRefresh(new Date());
    } catch {
      /* keep old data on transient failures */
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 30000);
    return () => clearInterval(id);
  }, [refresh]);

  async function toggle(traceId: string) {
    if (expanded === traceId) {
      setExpanded(null);
      return;
    }
    setExpanded(traceId);
    if (!spans[traceId]) {
      try {
        const full = await apiJson<{ spans?: Span[] }>(`${API_URL}/api/traces/${traceId}`);
        setSpans((prev) => ({ ...prev, [traceId]: full?.spans ?? [] }));
      } catch {
        setSpans((prev) => ({ ...prev, [traceId]: [] }));
      }
    }
  }

  return (
    <main className="min-h-full bg-[#050807] font-sans text-emerald-50/90">
      <header className="sticky top-0 z-10 border-b border-emerald-500/10 bg-[#050807]/80 backdrop-blur-md">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-3 px-4 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-emerald-500/30 bg-emerald-500/10 text-lg shadow-lg shadow-emerald-500/10">
              📊
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-wide text-emerald-300">
                Observability Dashboard
              </h1>
              <p className="text-xs text-emerald-200/40">
                Phase 9 — traces &amp; spans
                {lastRefresh && ` · refreshed ${lastRefresh.toLocaleTimeString()}`}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <a
              href="/"
              className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 px-3 py-2 text-xs font-semibold text-emerald-300/80 transition hover:bg-emerald-500/10"
            >
              ← Chat
            </a>
            <a
              href="/admin"
              className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 px-3 py-2 text-xs font-semibold text-emerald-300/80 transition hover:bg-emerald-500/10"
            >
              Admin →
            </a>
            <button
              onClick={refresh}
              className="rounded-xl bg-gradient-to-br from-emerald-400 to-teal-500 px-3 py-2 text-xs font-semibold text-black shadow-md shadow-emerald-500/25 transition hover:from-emerald-300 hover:to-teal-400 active:scale-95"
            >
              Refresh
            </button>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-5xl px-4 py-6">
        {/* Smart alerts */}
        <AlertsBanner />

        {/* Business Overview (live charts) */}
        <BusinessOverview stats={biz} />

        {/* Observability stats */}
        <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            { label: "Requests", value: stats?.total_requests ?? "—" },
            {
              label: "Avg response",
              value: stats ? `${Math.round(stats.avg_duration_ms)}ms` : "—",
            },
            { label: "Total tokens", value: stats?.total_tokens?.toLocaleString() ?? "—" },
            {
              label: "Error rate",
              value: stats ? `${Math.round(stats.error_rate * 100)}%` : "—",
            },
          ].map((k) => (
            <div
              key={k.label}
              className="rounded-2xl border border-emerald-500/15 bg-emerald-500/[0.05] p-4"
            >
              <p className="text-xs font-semibold uppercase tracking-wide text-emerald-200/40">
                {k.label}
              </p>
              <p className="mt-1 text-2xl font-bold text-emerald-300">{k.value}</p>
            </div>
          ))}
        </div>

        {/* Route + tool breakdown */}
        {stats?.tokens_by_route && Object.keys(stats.tokens_by_route).length > 0 && (
          <div className="mb-6 flex flex-wrap gap-2 text-xs">
            {Object.entries(stats.tokens_by_route).map(([route, r]) => (
              <span
                key={route}
                className="rounded-full border border-emerald-500/25 bg-emerald-500/10 px-3 py-1 font-medium text-emerald-300"
              >
                {route}: {r.requests} req · {r.tokens.toLocaleString()} tok · {Math.round(r.avg_ms)}ms
              </span>
            ))}
            {stats.slowest_tools?.map((t) => (
              <span
                key={t.tool}
                className="rounded-full border border-teal-500/25 bg-teal-500/10 px-3 py-1 font-medium text-teal-300"
              >
                {t.tool}: {Math.round(t.avg_ms)}ms avg ({t.calls})
              </span>
            ))}
          </div>
        )}

        {/* Feedback section */}
        <div className="mb-6 rounded-2xl border border-emerald-500/15 bg-emerald-500/[0.05] p-4">
          <div className="mb-3 flex items-center gap-2">
            <span>💬</span>
            <h2 className="text-sm font-bold text-emerald-200">Feedback</h2>
            {fbStats && (
              <span className="text-xs text-emerald-200/40">
                {fbStats.total} total · {fbStats.positive_pct}% 👍 · {fbStats.negative_pct}% 👎
              </span>
            )}
          </div>

          {fbStats?.recurring_issues && fbStats.recurring_issues.length > 0 && (
            <div className="mb-3 space-y-1">
              {fbStats.recurring_issues.map((r) => (
                <p
                  key={r.category}
                  className="rounded-lg border border-amber-400/30 bg-amber-500/10 px-3 py-1.5 text-xs font-medium text-amber-300"
                >
                  ⚠️ {r.message}
                </p>
              ))}
            </div>
          )}

          {fbStats?.by_category && Object.keys(fbStats.by_category).length > 0 && (
            <div className="mb-3 flex flex-wrap gap-2 text-xs">
              {Object.entries(fbStats.by_category).map(([cat, n]) => (
                <span
                  key={cat}
                  className="rounded-full border border-emerald-500/20 bg-black/30 px-2.5 py-1 font-medium text-emerald-200/70"
                >
                  {cat}: {n}
                </span>
              ))}
            </div>
          )}

          <div className="space-y-1.5">
            {fbRecent.length === 0 && (
              <p className="text-xs text-emerald-200/30">No feedback yet.</p>
            )}
            {fbRecent.map((f) => (
              <div
                key={f.feedback_id}
                className="flex items-center gap-2 rounded-xl border border-emerald-500/10 bg-black/20 px-2.5 py-1.5 text-xs"
              >
                <span>{f.rating === "positive" ? "👍" : "👎"}</span>
                <span
                  className={`rounded-md border px-1.5 py-0.5 font-semibold ${statusColor(
                    f.rating === "positive" ? "success" : "warning"
                  )}`}
                >
                  {f.category}
                </span>
                <span className="flex-1 truncate text-emerald-100/70">
                  {f.user_correction || <span className="text-emerald-200/20">(no comment)</span>}
                </span>
                <span className="shrink-0 truncate text-emerald-200/30" style={{ maxWidth: "30%" }}>
                  {f.original_request}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Trace list */}
        <h2 className="mb-2 text-sm font-bold text-emerald-200">Traces</h2>
        <div className="space-y-2">
          {traces.length === 0 && (
            <p className="rounded-2xl border border-emerald-500/15 bg-emerald-500/[0.04] p-6 text-center text-sm text-emerald-200/40">
              No traces yet. Send a message in the chat to generate one.
            </p>
          )}
          {traces.map((t) => (
            <div
              key={t.trace_id}
              className="overflow-hidden rounded-2xl border border-emerald-500/15 bg-emerald-500/[0.05]"
            >
              <button
                onClick={() => toggle(t.trace_id)}
                className="flex w-full items-center gap-3 px-4 py-3 text-left transition hover:bg-emerald-500/[0.08]"
              >
                <span className="text-emerald-300/50">{expanded === t.trace_id ? "▾" : "▸"}</span>
                <span
                  className={`shrink-0 rounded-lg border px-2 py-0.5 text-xs font-semibold ${statusColor(
                    t.status
                  )}`}
                >
                  {t.status ?? "?"}
                </span>
                <span className="shrink-0 rounded-lg border border-emerald-500/15 bg-black/30 px-2 py-0.5 text-xs font-medium text-emerald-200/70">
                  {t.route ?? "—"}
                </span>
                <span className="flex-1 truncate text-sm text-emerald-50/90">
                  {t.message ?? "(no message)"}
                </span>
                <span className="shrink-0 text-xs text-emerald-200/40">
                  {t.total_duration_ms ?? "—"}ms · {t.total_tokens ?? 0} tok
                </span>
              </button>

              {expanded === t.trace_id && (
                <div className="space-y-1.5 border-t border-emerald-500/10 bg-black/20 px-4 py-3">
                  <p className="mb-2 font-mono text-[11px] text-emerald-200/30">
                    trace {t.trace_id} · {t.created_at}
                  </p>
                  {(spans[t.trace_id] ?? []).map((s) => (
                    <div
                      key={s.span_id}
                      className="rounded-xl border border-emerald-500/10 bg-emerald-500/[0.04] p-2.5 text-xs"
                    >
                      <div className="flex items-center gap-2">
                        <span
                          className={`rounded-md border px-1.5 py-0.5 font-semibold ${statusColor(
                            s.status
                          )}`}
                        >
                          {s.status}
                        </span>
                        <span className="font-mono font-semibold text-emerald-100">{s.name}</span>
                        <span className="ml-auto text-emerald-200/40">
                          {s.duration_ms}ms{s.tokens ? ` · ${s.tokens} tok` : ""}
                        </span>
                      </div>
                      {s.input && (
                        <p className="mt-1 truncate text-emerald-200/50">
                          <span className="text-emerald-200/30">in:</span> {s.input}
                        </p>
                      )}
                      {s.output && (
                        <p className="mt-0.5 truncate text-emerald-100/60">
                          <span className="text-emerald-200/30">out:</span> {s.output}
                        </p>
                      )}
                    </div>
                  ))}
                  {(spans[t.trace_id] ?? []).length === 0 && (
                    <p className="text-xs text-emerald-200/30">No spans recorded.</p>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}
