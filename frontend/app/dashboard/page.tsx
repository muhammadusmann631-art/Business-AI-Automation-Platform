"use client";

import { useCallback, useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

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
      return "bg-emerald-100 text-emerald-700 border-emerald-200";
    case "error":
      return "bg-rose-100 text-rose-700 border-rose-200";
    case "warning":
    case "retry":
    case "pending":
      return "bg-amber-100 text-amber-700 border-amber-200";
    default:
      return "bg-gray-100 text-gray-600 border-gray-200";
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

  const refresh = useCallback(async () => {
    try {
      const [s, t, fs, fr] = await Promise.all([
        fetch(`${API_URL}/api/stats`).then((r) => r.json()),
        fetch(`${API_URL}/api/traces?limit=50`).then((r) => r.json()),
        fetch(`${API_URL}/api/feedback/stats`).then((r) => r.json()),
        fetch(`${API_URL}/api/feedback/recent?limit=20`).then((r) => r.json()),
      ]);
      setStats(s);
      setTraces(t.traces ?? []);
      setFbStats(fs);
      setFbRecent(fr.feedback ?? []);
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
        const full = await fetch(`${API_URL}/api/traces/${traceId}`).then((r) => r.json());
        setSpans((prev) => ({ ...prev, [traceId]: full.spans ?? [] }));
      } catch {
        setSpans((prev) => ({ ...prev, [traceId]: [] }));
      }
    }
  }

  return (
    <main className="min-h-full bg-gradient-to-br from-indigo-100 via-purple-50 to-rose-100 font-sans">
      <header className="sticky top-0 z-10 border-b border-white/40 bg-white/60 backdrop-blur-md">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-3 px-4 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600 text-lg shadow-lg shadow-indigo-500/25">
              📊
            </div>
            <div>
              <h1 className="bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-lg font-bold text-transparent">
                Observability Dashboard
              </h1>
              <p className="text-xs text-gray-500">
                Phase 9 — traces &amp; spans
                {lastRefresh && ` · refreshed ${lastRefresh.toLocaleTimeString()}`}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <a
              href="/"
              className="rounded-xl border border-gray-200 bg-white px-3 py-2 text-xs font-semibold text-gray-600 transition hover:bg-gray-50"
            >
              ← Chat
            </a>
            <button
              onClick={refresh}
              className="rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 px-3 py-2 text-xs font-semibold text-white shadow-md shadow-indigo-500/25 transition hover:from-indigo-600 hover:to-purple-700 active:scale-95"
            >
              Refresh
            </button>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-5xl px-4 py-6">
        {/* Stats */}
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
              className="rounded-2xl border border-white/50 bg-white/80 p-4 shadow-sm"
            >
              <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">
                {k.label}
              </p>
              <p className="mt-1 text-2xl font-bold text-gray-800">{k.value}</p>
            </div>
          ))}
        </div>

        {/* Route + tool breakdown */}
        {stats?.tokens_by_route && Object.keys(stats.tokens_by_route).length > 0 && (
          <div className="mb-6 flex flex-wrap gap-2 text-xs">
            {Object.entries(stats.tokens_by_route).map(([route, r]) => (
              <span
                key={route}
                className="rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 font-medium text-indigo-700"
              >
                {route}: {r.requests} req · {r.tokens.toLocaleString()} tok · {Math.round(r.avg_ms)}ms
              </span>
            ))}
            {stats.slowest_tools?.map((t) => (
              <span
                key={t.tool}
                className="rounded-full border border-purple-200 bg-purple-50 px-3 py-1 font-medium text-purple-700"
              >
                {t.tool}: {Math.round(t.avg_ms)}ms avg ({t.calls})
              </span>
            ))}
          </div>
        )}

        {/* Feedback section */}
        <div className="mb-6 rounded-2xl border border-white/50 bg-white/80 p-4 shadow-sm">
          <div className="mb-3 flex items-center gap-2">
            <span>💬</span>
            <h2 className="text-sm font-bold text-gray-700">Feedback</h2>
            {fbStats && (
              <span className="text-xs text-gray-500">
                {fbStats.total} total · {fbStats.positive_pct}% 👍 · {fbStats.negative_pct}% 👎
              </span>
            )}
          </div>

          {fbStats?.recurring_issues && fbStats.recurring_issues.length > 0 && (
            <div className="mb-3 space-y-1">
              {fbStats.recurring_issues.map((r) => (
                <p
                  key={r.category}
                  className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-1.5 text-xs font-medium text-amber-800"
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
                  className="rounded-full border border-gray-200 bg-gray-50 px-2.5 py-1 font-medium text-gray-600"
                >
                  {cat}: {n}
                </span>
              ))}
            </div>
          )}

          <div className="space-y-1.5">
            {fbRecent.length === 0 && (
              <p className="text-xs text-gray-400">No feedback yet.</p>
            )}
            {fbRecent.map((f) => (
              <div
                key={f.feedback_id}
                className="flex items-center gap-2 rounded-xl border border-gray-100 bg-white px-2.5 py-1.5 text-xs"
              >
                <span>{f.rating === "positive" ? "👍" : "👎"}</span>
                <span
                  className={`rounded-md border px-1.5 py-0.5 font-semibold ${statusColor(
                    f.rating === "positive" ? "success" : "warning"
                  )}`}
                >
                  {f.category}
                </span>
                <span className="flex-1 truncate text-gray-600">
                  {f.user_correction || <span className="text-gray-300">(no comment)</span>}
                </span>
                <span className="shrink-0 truncate text-gray-400" style={{ maxWidth: "30%" }}>
                  {f.original_request}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Trace list */}
        <h2 className="mb-2 text-sm font-bold text-gray-700">Traces</h2>
        <div className="space-y-2">
          {traces.length === 0 && (
            <p className="rounded-2xl border border-white/50 bg-white/70 p-6 text-center text-sm text-gray-500">
              No traces yet. Send a message in the chat to generate one.
            </p>
          )}
          {traces.map((t) => (
            <div
              key={t.trace_id}
              className="overflow-hidden rounded-2xl border border-white/50 bg-white/80 shadow-sm"
            >
              <button
                onClick={() => toggle(t.trace_id)}
                className="flex w-full items-center gap-3 px-4 py-3 text-left transition hover:bg-white"
              >
                <span className="text-gray-400">{expanded === t.trace_id ? "▾" : "▸"}</span>
                <span
                  className={`shrink-0 rounded-lg border px-2 py-0.5 text-xs font-semibold ${statusColor(
                    t.status
                  )}`}
                >
                  {t.status ?? "?"}
                </span>
                <span className="shrink-0 rounded-lg bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600">
                  {t.route ?? "—"}
                </span>
                <span className="flex-1 truncate text-sm text-gray-800">
                  {t.message ?? "(no message)"}
                </span>
                <span className="shrink-0 text-xs text-gray-500">
                  {t.total_duration_ms ?? "—"}ms · {t.total_tokens ?? 0} tok
                </span>
              </button>

              {expanded === t.trace_id && (
                <div className="space-y-1.5 border-t border-gray-100 bg-gray-50/60 px-4 py-3">
                  <p className="mb-2 font-mono text-[11px] text-gray-400">
                    trace {t.trace_id} · {t.created_at}
                  </p>
                  {(spans[t.trace_id] ?? []).map((s) => (
                    <div
                      key={s.span_id}
                      className="rounded-xl border border-gray-100 bg-white p-2.5 text-xs"
                    >
                      <div className="flex items-center gap-2">
                        <span
                          className={`rounded-md border px-1.5 py-0.5 font-semibold ${statusColor(
                            s.status
                          )}`}
                        >
                          {s.status}
                        </span>
                        <span className="font-mono font-semibold text-gray-800">{s.name}</span>
                        <span className="ml-auto text-gray-400">
                          {s.duration_ms}ms{s.tokens ? ` · ${s.tokens} tok` : ""}
                        </span>
                      </div>
                      {s.input && (
                        <p className="mt-1 truncate text-gray-500">
                          <span className="text-gray-400">in:</span> {s.input}
                        </p>
                      )}
                      {s.output && (
                        <p className="mt-0.5 truncate text-gray-600">
                          <span className="text-gray-400">out:</span> {s.output}
                        </p>
                      )}
                    </div>
                  ))}
                  {(spans[t.trace_id] ?? []).length === 0 && (
                    <p className="text-xs text-gray-400">No spans recorded.</p>
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
