"use client";

import { useEffect, useRef, useState } from "react";

// Relative — Next.js rewrites (next.config.ts) proxy these to the backend, so
// the app works from a single URL both locally and on Render.
const API_URL = "";

/* ----------------------------- Radial hub config ----------------------------- */
// One node per real agent / tool in the system. Positions are computed on an
// ellipse (rx=25%, ry=40%) so the ring looks circular in a 16:10 container.
const RX = 25;
const RY = 40;

type NodeDef = { id: string; label: string; sub: string; angle: number };

const NODES: NodeDef[] = [
  { id: "planner", label: "PLANNER", sub: "plan", angle: 90 },
  { id: "memory", label: "MEMORY", sub: "recall", angle: 60 },
  { id: "router", label: "ROUTER", sub: "classify", angle: 30 },
  { id: "worker", label: "WORKER", sub: "execute", angle: 0 },
  { id: "database", label: "DATABASE", sub: "sql", angle: -30 },
  { id: "report", label: "REPORT", sub: "pdf", angle: -60 },
  { id: "email", label: "EMAIL", sub: "draft", angle: -90 },
  { id: "qa", label: "QA", sub: "guardrails", angle: -120 },
  { id: "resilience", label: "RESILIENCE", sub: "retry", angle: -150 },
  { id: "approval", label: "APPROVAL", sub: "human", angle: 180 },
  { id: "tracer", label: "TRACER", sub: "observe", angle: 150 },
  { id: "feedback", label: "FEEDBACK", sub: "learn", angle: 120 },
];

function pos(angle: number) {
  const r = (angle * Math.PI) / 180;
  return { x: 50 + RX * Math.cos(r), y: 50 - RY * Math.sin(r) };
}
const NODE_POS: Record<string, { x: number; y: number }> = Object.fromEntries(
  NODES.map((n) => [n.id, pos(n.angle)])
);

// Map a Phase 9 span name -> which node lights up.
function spanToNode(name: string): string | null {
  if (name === "router") return "router";
  if (name === "planner") return "planner";
  if (name === "fast_track" || name.startsWith("step:")) return "worker";
  if (name === "tool:query_sales") return "database";
  if (name === "tool:generate_report") return "report";
  if (name === "tool:draft_email") return "email";
  if (name.startsWith("retry:")) return "resilience";
  if (name === "qa") return "qa";
  if (name === "approval") return "approval";
  return null; // supervisor / response / others -> handled separately
}

type Pulse = { id: number; fx: number; fy: number; tx: number; ty: number; color: string };

/* ------------------------------- Chat types --------------------------------- */
type PendingApproval = {
  approval_id: string;
  action: string;
  details: Record<string, string>;
  risk_reason: string;
};

type FileOut = { name: string; url: string; type: string };

type Message = {
  role: "user" | "assistant" | "error" | "approval";
  content: string;
  pending?: PendingApproval;
  decided?: "approved" | "rejected";
  traceId?: string;
  feedback?: "sent";
  showCorrection?: boolean;
  files?: FileOut[];
};

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [activeNode, setActiveNode] = useState<string | null>(null);
  const [litNodes, setLitNodes] = useState<Set<string>>(new Set());
  const [pulses, setPulses] = useState<Pulse[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const sessionIdRef = useRef<string>("");
  const pulseId = useRef(0);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  /* --------------------------- animation helpers --------------------------- */
  function spawnPulse(fromId: string, toId: string, color = "#43e0a3") {
    const from = fromId === "core" ? { x: 50, y: 50 } : NODE_POS[fromId];
    const to = toId === "core" ? { x: 50, y: 50 } : NODE_POS[toId];
    if (!from || !to) return;
    const id = ++pulseId.current;
    setPulses((p) => [...p, { id, fx: from.x, fy: from.y, tx: to.x, ty: to.y, color }]);
  }

  async function playPath(nodeIds: string[]) {
    const lit = new Set<string>();
    for (const id of nodeIds) {
      if (!NODE_POS[id]) continue;
      spawnPulse("core", id, id === "feedback" ? "#f5b301" : "#43e0a3");
      setActiveNode(id);
      lit.add(id);
      setLitNodes(new Set(lit));
      await sleep(460);
    }
    // send a pulse back to the core to signal the response is delivered
    if (nodeIds.length) spawnPulse(nodeIds[nodeIds.length - 1], "core", "#7cf3c6");
    setActiveNode(null);
    setTimeout(() => setLitNodes(new Set()), 1600);
  }

  function nodesFromTrace(spans: { name: string }[], route: string | null): string[] {
    const seq: string[] = [];
    const push = (id: string | null) => {
      if (id && seq[seq.length - 1] !== id) seq.push(id);
    };
    push("router");
    if (route === "complex") push("memory");
    for (const s of spans) push(spanToNode(s.name));
    push("tracer"); // everything is observed
    return seq.length > 1 ? seq : route === "complex"
      ? ["router", "memory", "planner", "worker", "qa", "tracer"]
      : ["router", "worker", "tracer"];
  }

  async function animateTrace(traceId: string, route: string | null) {
    try {
      const full = await fetch(`${API_URL}/api/traces/${traceId}`).then((r) => r.json());
      await playPath(nodesFromTrace(full.spans ?? [], route ?? full.route ?? null));
    } catch {
      await playPath(["router", "worker", "tracer"]);
    }
  }

  /* ------------------------------- chat send -------------------------------- */
  async function sendMessage() {
    const text = input.trim();
    if (!text || loading) return;
    if (!sessionIdRef.current) sessionIdRef.current = crypto.randomUUID();

    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setInput("");
    setLoading(true);
    setActiveNode("router"); // core starts "thinking"

    try {
      const res = await fetch(`${API_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, session_id: sessionIdRef.current }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(typeof data?.detail === "string" ? data.detail : "Request failed");
      }
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.reply, traceId: data.trace_id, files: data.files },
      ]);
      if (data.pending_approval) {
        setMessages((prev) => [
          ...prev,
          {
            role: "approval",
            content: "This action needs your approval before it runs.",
            pending: data.pending_approval,
          },
        ]);
      }
      if (data.trace_id) animateTrace(data.trace_id, null);
      else setActiveNode(null);
    } catch (err) {
      setActiveNode(null);
      setMessages((prev) => [
        ...prev,
        {
          role: "error",
          content:
            err instanceof Error && err.message !== "Failed to fetch"
              ? err.message
              : "Couldn't reach the server. Is the backend running on port 8000?",
        },
      ]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  }

  /* ------------------------------- approval --------------------------------- */
  async function decide(index: number, decision: "approved" | "rejected") {
    const msg = messages[index];
    if (!msg?.pending || msg.decided || loading) return;
    setLoading(true);
    setMessages((prev) => prev.map((m, i) => (i === index ? { ...m, decided: decision } : m)));
    if (decision === "approved") spawnPulse("core", "email", "#f5b301");
    try {
      const endpoint = decision === "approved" ? "approve" : "reject";
      const res = await fetch(`${API_URL}/api/${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approval_id: msg.pending.approval_id }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(typeof data?.detail === "string" ? data.detail : "Request failed");
      }
      setMessages((prev) => [...prev, { role: "assistant", content: data.reply }]);
    } catch (err) {
      setMessages((prev) => prev.map((m, i) => (i === index ? { ...m, decided: undefined } : m)));
      setMessages((prev) => [
        ...prev,
        {
          role: "error",
          content:
            err instanceof Error && err.message !== "Failed to fetch"
              ? err.message
              : "Couldn't reach the server. Is the backend running on port 8000?",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  /* ------------------------------- feedback --------------------------------- */
  async function sendFeedback(index: number, rating: "positive" | "negative", correction = "") {
    const msg = messages[index];
    if (!msg?.traceId) return;
    setMessages((prev) =>
      prev.map((m, i) => (i === index ? { ...m, feedback: "sent", showCorrection: false } : m))
    );
    spawnPulse("core", "feedback", "#f5b301");
    setActiveNode("feedback");
    setLitNodes((s) => new Set(s).add("feedback"));
    setTimeout(() => setActiveNode(null), 700);
    setTimeout(() => setLitNodes(new Set()), 1600);
    try {
      await fetch(`${API_URL}/api/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          trace_id: msg.traceId,
          rating,
          correction,
          session_id: sessionIdRef.current,
        }),
      });
    } catch {
      /* best-effort */
    }
  }

  /* --------------------------------- render --------------------------------- */
  return (
    <main className="flex min-h-full flex-col bg-[#050807] font-sans text-emerald-50/90">
      <style>{CSS}</style>

      {/* Header */}
      <header className="sticky top-0 z-20 border-b border-emerald-500/10 bg-[#050807]/80 backdrop-blur-md">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-4 py-3">
          <div className="flex items-center gap-2 text-emerald-300">
            <span className="text-lg">✦</span>
            <span className="text-sm font-semibold tracking-[0.3em]">AGI · CORE</span>
          </div>
          <nav className="flex items-center gap-2">
            <a
              href="/dashboard"
              className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-3 py-1.5 text-xs font-medium text-emerald-300/80 transition hover:bg-emerald-500/10"
            >
              Dashboard →
            </a>
            <a
              href="/admin"
              className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-3 py-1.5 text-xs font-medium text-emerald-300/80 transition hover:bg-emerald-500/10"
            >
              Admin →
            </a>
          </nav>
        </div>
      </header>

      {/* Radial hub */}
      <div className="mx-auto w-full max-w-3xl px-4 pt-4">
        <div className="hub relative w-full overflow-hidden rounded-2xl border border-emerald-500/10">
          <div className="hub-bg" />
          <div className="relative w-full" style={{ aspectRatio: "16 / 10" }}>
            {/* connection lines */}
            <svg
              className="absolute inset-0 h-full w-full"
              viewBox="0 0 100 100"
              preserveAspectRatio="none"
            >
              <ellipse
                cx="50"
                cy="50"
                rx={RX}
                ry={RY}
                fill="none"
                stroke="rgba(52,211,153,0.14)"
                strokeWidth="0.15"
                strokeDasharray="0.6 1.2"
                vectorEffect="non-scaling-stroke"
                className="orbit"
              />
              {NODES.map((n) => {
                const p = NODE_POS[n.id];
                const on = litNodes.has(n.id) || activeNode === n.id;
                return (
                  <line
                    key={n.id}
                    x1="50"
                    y1="50"
                    x2={p.x}
                    y2={p.y}
                    stroke={on ? "rgba(67,224,163,0.7)" : "rgba(52,211,153,0.12)"}
                    strokeWidth={on ? "0.4" : "0.18"}
                    strokeDasharray="0.8 1.1"
                    vectorEffect="non-scaling-stroke"
                    className="flow"
                  />
                );
              })}
            </svg>

            {/* core */}
            <div
              className={`node-core ${activeNode ? "thinking" : ""}`}
              style={{ left: "50%", top: "50%" }}
            >
              <span className="core-label">SYSTEM</span>
              <span className="core-title">AGI-CORE</span>
            </div>

            {/* nodes */}
            {NODES.map((n) => {
              const p = NODE_POS[n.id];
              const isActive = activeNode === n.id;
              const isLit = litNodes.has(n.id);
              return (
                <div
                  key={n.id}
                  className={`node ${isActive ? "active" : ""} ${isLit ? "lit" : ""}`}
                  style={{ left: `${p.x}%`, top: `${p.y}%` }}
                >
                  <span className="node-dot" />
                  <span className="node-label">{n.label}</span>
                </div>
              );
            })}

            {/* traveling pulses */}
            {pulses.map((pl) => (
              <span
                key={pl.id}
                className="pulse"
                style={
                  {
                    "--fx": `${pl.fx}%`,
                    "--fy": `${pl.fy}%`,
                    "--tx": `${pl.tx}%`,
                    "--ty": `${pl.ty}%`,
                    "--c": pl.color,
                  } as React.CSSProperties
                }
                onAnimationEnd={() => setPulses((p) => p.filter((x) => x.id !== pl.id))}
              />
            ))}
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 px-4 py-6">
        {messages.length === 0 && !loading && (
          <p className="mt-6 text-center text-sm text-emerald-200/40">
            Ask about sales, request a PDF report, or draft an email — watch the core route the work.
          </p>
        )}

        {messages.map((m, i) =>
          m.role === "approval" && m.pending ? (
            <div key={i} className="message-in flex justify-start">
              <div className="max-w-[85%] rounded-2xl rounded-bl-md border border-amber-400/30 bg-amber-400/10 px-4 py-3 text-sm shadow-lg shadow-amber-500/5">
                <div className="mb-2 flex items-center gap-2 font-semibold text-amber-300">
                  <span>🔔</span>
                  <span>Approval needed</span>
                </div>
                <p className="mb-2 text-xs text-amber-200/70">{m.pending.risk_reason}</p>
                <div className="mb-3 space-y-1 rounded-xl bg-black/30 p-3 text-emerald-50/80">
                  <p className="text-xs font-semibold uppercase tracking-wide text-emerald-200/40">
                    {m.pending.action.replace(/_/g, " ")}
                  </p>
                  {Object.entries(m.pending.details)
                    .filter(([, v]) => v)
                    .map(([k, v]) => (
                      <p key={k} className="whitespace-pre-wrap">
                        <span className="font-semibold capitalize text-emerald-300/70">{k}:</span> {v}
                      </p>
                    ))}
                </div>
                {m.decided ? (
                  <p
                    className={`text-xs font-semibold ${
                      m.decided === "approved" ? "text-emerald-400" : "text-rose-400"
                    }`}
                  >
                    {m.decided === "approved" ? "✓ Approved" : "✕ Rejected"}
                  </p>
                ) : (
                  <div className="flex gap-2">
                    <button
                      onClick={() => decide(i, "approved")}
                      disabled={loading}
                      className="rounded-lg bg-emerald-500 px-4 py-2 text-xs font-semibold text-black transition hover:bg-emerald-400 active:scale-95 disabled:opacity-40"
                    >
                      Approve
                    </button>
                    <button
                      onClick={() => decide(i, "rejected")}
                      disabled={loading}
                      className="rounded-lg bg-rose-500 px-4 py-2 text-xs font-semibold text-white transition hover:bg-rose-400 active:scale-95 disabled:opacity-40"
                    >
                      Reject
                    </button>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div
              key={i}
              className={`message-in flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                  m.role === "user"
                    ? "rounded-br-md bg-gradient-to-br from-emerald-500 to-teal-600 text-black shadow-lg shadow-emerald-500/20"
                    : m.role === "assistant"
                      ? "rounded-bl-md border border-emerald-500/15 bg-emerald-500/[0.06] text-emerald-50/90"
                      : "rounded-bl-md border border-rose-400/30 bg-rose-500/10 text-rose-200"
                }`}
              >
                {m.content}
                {m.files && m.files.length > 0 && (
                  <div className="mt-3 space-y-2">
                    {m.files.map((f) =>
                      f.type === "chart" || f.type === "image" ? (
                        <a
                          key={f.url}
                          href={`${API_URL}${f.url}`}
                          target="_blank"
                          rel="noreferrer"
                          className="block overflow-hidden rounded-xl border border-emerald-500/25 bg-white"
                          title="Open chart full size"
                        >
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img
                            src={`${API_URL}${f.url}`}
                            alt={f.name}
                            className="w-full"
                          />
                        </a>
                      ) : (
                        <a
                          key={f.url}
                          href={`${API_URL}${f.url}`}
                          target="_blank"
                          rel="noreferrer"
                          download
                          className="flex items-center gap-3 rounded-xl border border-emerald-500/25 bg-emerald-500/[0.06] px-3 py-2.5 transition hover:border-emerald-400/50 hover:bg-emerald-500/10"
                        >
                          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-500/15 text-lg">
                            {f.type === "excel" ? "📊" : "📄"}
                          </span>
                          <span className="min-w-0 flex-1">
                            <span className="block truncate text-xs font-semibold text-emerald-100">
                              {f.name}
                            </span>
                            <span className="block text-[10px] uppercase tracking-wide text-emerald-300/50">
                              {f.type} · click to download
                            </span>
                          </span>
                          <span className="rounded-lg bg-emerald-400 px-3 py-1.5 text-xs font-semibold text-black">
                            Download
                          </span>
                        </a>
                      )
                    )}
                  </div>
                )}
                {m.role === "assistant" && m.traceId && (
                  <div className="mt-2 flex items-center gap-2 border-t border-emerald-500/10 pt-2">
                    {m.feedback === "sent" ? (
                      <span className="text-[11px] font-medium text-emerald-400">
                        Thanks for the feedback!
                      </span>
                    ) : (
                      <>
                        <button
                          onClick={() => sendFeedback(i, "positive")}
                          className="rounded-lg px-1.5 py-0.5 text-sm transition hover:bg-emerald-500/10"
                          title="Good response"
                        >
                          👍
                        </button>
                        <button
                          onClick={() =>
                            setMessages((prev) =>
                              prev.map((x, j) =>
                                j === i ? { ...x, showCorrection: !x.showCorrection } : x
                              )
                            )
                          }
                          className="rounded-lg px-1.5 py-0.5 text-sm transition hover:bg-rose-500/10"
                          title="Needs improvement"
                        >
                          👎
                        </button>
                      </>
                    )}
                    <a
                      href="/dashboard"
                      className="ml-auto font-mono text-[10px] text-emerald-300/40 transition hover:text-emerald-300/80"
                      title="Open the observability dashboard"
                    >
                      trace: {m.traceId}
                    </a>
                  </div>
                )}
                {m.showCorrection && (
                  <form
                    className="mt-2 flex gap-1.5"
                    onSubmit={(e) => {
                      e.preventDefault();
                      const fd = new FormData(e.currentTarget);
                      sendFeedback(i, "negative", String(fd.get("c") ?? ""));
                    }}
                  >
                    <input
                      name="c"
                      autoFocus
                      placeholder="What was wrong? (optional)"
                      className="flex-1 rounded-lg border border-emerald-500/20 bg-black/30 px-2.5 py-1.5 text-xs text-emerald-50 outline-none focus:border-rose-400/50"
                    />
                    <button
                      type="submit"
                      className="rounded-lg bg-rose-500 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-rose-400 active:scale-95"
                    >
                      Send
                    </button>
                  </form>
                )}
              </div>
            </div>
          )
        )}

        {loading && (
          <div className="message-in flex justify-start">
            <div className="flex items-center gap-1.5 rounded-2xl rounded-bl-md border border-emerald-500/15 bg-emerald-500/[0.06] px-5 py-4">
              <span className="typing-dot h-2 w-2 rounded-full bg-emerald-400" />
              <span className="typing-dot h-2 w-2 rounded-full bg-teal-400" />
              <span className="typing-dot h-2 w-2 rounded-full bg-emerald-300" />
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="sticky bottom-0 border-t border-emerald-500/10 bg-[#050807]/80 pb-4 pt-3 backdrop-blur-md">
        <form
          className="mx-auto flex max-w-3xl items-center gap-2 px-4"
          onSubmit={(e) => {
            e.preventDefault();
            sendMessage();
          }}
        >
          <input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Message the core…"
            autoFocus
            className="flex-1 rounded-xl border border-emerald-500/20 bg-emerald-500/[0.04] px-4 py-3 text-sm text-emerald-50 outline-none transition placeholder:text-emerald-200/30 focus:border-emerald-400/50 focus:ring-2 focus:ring-emerald-500/20"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="rounded-xl bg-gradient-to-br from-emerald-400 to-teal-500 px-5 py-3 text-sm font-semibold text-black shadow-lg shadow-emerald-500/25 transition hover:from-emerald-300 hover:to-teal-400 active:scale-95 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Send
          </button>
        </form>
      </div>
    </main>
  );
}

/* --------------------------------- styles ---------------------------------- */
const CSS = `
.hub { background: #04070a; }
.hub-bg {
  position: absolute; inset: 0;
  background:
    radial-gradient(circle at 50% 50%, rgba(16,74,58,0.55), transparent 60%),
    radial-gradient(circle at 50% 50%, rgba(6,20,16,0.9), #04070a 70%);
}
.hub-bg::after {
  content: ""; position: absolute; left: 50%; top: 50%;
  width: 120%; height: 190%; transform: translate(-50%,-50%);
  background: conic-gradient(from 0deg, transparent 0deg, rgba(67,224,163,0.10) 25deg, transparent 60deg);
  animation: sweep 9s linear infinite;
}
@keyframes sweep { to { transform: translate(-50%,-50%) rotate(360deg); } }

.orbit { animation: dash 40s linear infinite; }
.flow { animation: dash 6s linear infinite; }
@keyframes dash { to { stroke-dashoffset: -20; } }

.node-core {
  position: absolute; transform: translate(-50%,-50%);
  width: 96px; height: 96px; border-radius: 9999px;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  background: radial-gradient(circle, rgba(20,90,70,0.6), rgba(8,30,24,0.4));
  border: 1px solid rgba(67,224,163,0.4);
  box-shadow: 0 0 24px 4px rgba(67,224,163,0.18), inset 0 0 22px rgba(67,224,163,0.14);
  animation: corePulse 3.5s ease-in-out infinite;
}
.node-core::before, .node-core::after {
  content: ""; position: absolute; border-radius: 9999px; border: 1px solid rgba(67,224,163,0.18);
}
.node-core::before { inset: -12px; }
.node-core::after { inset: -26px; border-color: rgba(67,224,163,0.10); }
.node-core.thinking {
  border-color: rgba(245,179,1,0.6);
  box-shadow: 0 0 34px 8px rgba(245,179,1,0.22), inset 0 0 22px rgba(245,179,1,0.16);
}
.core-label { font-size: 7px; letter-spacing: 0.28em; color: rgba(167,243,208,0.55); }
.core-title { font-size: 12px; font-weight: 700; letter-spacing: 0.12em; color: #7cf3c6; }
@keyframes corePulse {
  0%,100% { box-shadow: 0 0 20px 3px rgba(67,224,163,0.15), inset 0 0 18px rgba(67,224,163,0.12); }
  50% { box-shadow: 0 0 30px 6px rgba(67,224,163,0.28), inset 0 0 24px rgba(67,224,163,0.2); }
}

.node {
  position: absolute; transform: translate(-50%,-50%);
  display: flex; flex-direction: column; align-items: center; gap: 5px;
  pointer-events: none;
}
.node-dot {
  width: 22px; height: 22px; border-radius: 9999px;
  background: radial-gradient(circle, rgba(124,243,198,0.25), rgba(10,40,32,0.5));
  border: 1px solid rgba(67,224,163,0.45);
  box-shadow: 0 0 8px rgba(67,224,163,0.25);
  display: flex; align-items: center; justify-content: center;
  transition: all 0.3s ease;
}
.node-dot::after {
  content: ""; width: 6px; height: 6px; border-radius: 9999px;
  background: #43e0a3; box-shadow: 0 0 6px #43e0a3;
  animation: twinkle 3s ease-in-out infinite;
}
.node-label {
  font-size: 8px; font-weight: 600; letter-spacing: 0.14em;
  color: rgba(167,243,208,0.5);
  transition: all 0.3s ease;
}
@keyframes twinkle { 0%,100% { opacity: 0.5; } 50% { opacity: 1; } }

.node.lit .node-dot {
  border-color: rgba(67,224,163,0.9);
  box-shadow: 0 0 16px 3px rgba(67,224,163,0.5);
  transform: scale(1.12);
}
.node.lit .node-label { color: #7cf3c6; }
.node.active .node-dot {
  border-color: rgba(245,179,1,0.95);
  background: radial-gradient(circle, rgba(245,179,1,0.4), rgba(60,40,0,0.4));
  box-shadow: 0 0 22px 5px rgba(245,179,1,0.55);
  transform: scale(1.3);
}
.node.active .node-dot::after { background: #ffd24a; box-shadow: 0 0 8px #ffd24a; }
.node.active .node-label { color: #ffd24a; text-shadow: 0 0 10px rgba(245,179,1,0.5); }

.pulse {
  position: absolute; width: 9px; height: 9px; border-radius: 9999px;
  transform: translate(-50%,-50%);
  background: radial-gradient(circle, #eafff5, var(--c));
  box-shadow: 0 0 12px 3px var(--c);
  pointer-events: none;
  animation: travel 0.62s cubic-bezier(0.4,0,0.2,1) forwards;
}
@keyframes travel {
  0%   { left: var(--fx); top: var(--fy); opacity: 0; transform: translate(-50%,-50%) scale(0.4); }
  20%  { opacity: 1; }
  100% { left: var(--tx); top: var(--ty); opacity: 0; transform: translate(-50%,-50%) scale(1.1); }
}

@media (prefers-reduced-motion: reduce) {
  .orbit, .flow, .hub-bg::after, .node-core, .node-dot::after { animation: none; }
}
`;
