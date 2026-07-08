"use client";

import { useEffect, useRef, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

type Message = {
  role: "user" | "assistant" | "error";
  content: string;
};

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const sessionIdRef = useRef<string>("");

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function sendMessage() {
    const text = input.trim();
    if (!text || loading) return;
    if (!sessionIdRef.current) sessionIdRef.current = crypto.randomUUID();

    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch(`${API_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, session_id: sessionIdRef.current }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(
          typeof data?.detail === "string" ? data.detail : "Request failed"
        );
      }
      setMessages((prev) => [...prev, { role: "assistant", content: data.reply }]);
    } catch (err) {
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

  return (
    <main className="flex flex-1 flex-col bg-gradient-to-br from-indigo-100 via-purple-50 to-rose-100 font-sans">
      {/* Header */}
      <header className="sticky top-0 z-10 border-b border-white/40 bg-white/60 backdrop-blur-md">
        <div className="mx-auto flex max-w-3xl items-center gap-3 px-4 py-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600 text-lg shadow-lg shadow-indigo-500/25">
            ✨
          </div>
          <div>
            <h1 className="bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-lg font-bold text-transparent">
              AI Agent System
            </h1>
            <p className="text-xs text-gray-500">Phase 0 — connected to OpenAI</p>
          </div>
        </div>
      </header>

      {/* Messages */}
      <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 px-4 py-6">
        {messages.length === 0 && !loading && (
          <div className="mt-16 flex flex-col items-center gap-3 text-center message-in">
            <div className="flex h-16 w-16 items-center justify-center rounded-3xl bg-gradient-to-br from-indigo-500 to-purple-600 text-3xl shadow-xl shadow-indigo-500/30">
              👋
            </div>
            <h2 className="text-xl font-semibold text-gray-800">
              Hi! I&apos;m your AI assistant.
            </h2>
            <p className="max-w-sm text-sm text-gray-500">
              Type a message below and I&apos;ll reply using OpenAI. This is the
              first working spine of the system.
            </p>
          </div>
        )}

        {messages.map((m, i) => (
          <div
            key={i}
            className={`message-in flex ${
              m.role === "user" ? "justify-end" : "justify-start"
            }`}
          >
            <div
              className={`max-w-[80%] whitespace-pre-wrap rounded-3xl px-4 py-3 text-sm leading-relaxed shadow-md ${
                m.role === "user"
                  ? "rounded-br-lg bg-gradient-to-br from-indigo-500 to-purple-600 text-white shadow-indigo-500/25"
                  : m.role === "assistant"
                    ? "rounded-bl-lg bg-white/90 text-gray-800 shadow-gray-300/40"
                    : "rounded-bl-lg border border-rose-200 bg-rose-50 text-rose-700 shadow-rose-200/40"
              }`}
            >
              {m.content}
            </div>
          </div>
        ))}

        {loading && (
          <div className="message-in flex justify-start">
            <div className="flex items-center gap-1.5 rounded-3xl rounded-bl-lg bg-white/90 px-5 py-4 shadow-md shadow-gray-300/40">
              <span className="typing-dot h-2 w-2 rounded-full bg-indigo-400" />
              <span className="typing-dot h-2 w-2 rounded-full bg-purple-400" />
              <span className="typing-dot h-2 w-2 rounded-full bg-rose-400" />
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input bar */}
      <div className="sticky bottom-0 border-t border-white/40 bg-white/60 pb-4 pt-3 backdrop-blur-md">
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
            placeholder="Type a message…"
            autoFocus
            className="flex-1 rounded-2xl border border-gray-200 bg-white px-4 py-3 text-sm text-gray-800 shadow-sm outline-none transition placeholder:text-gray-400 focus:border-indigo-400 focus:ring-2 focus:ring-indigo-200"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600 px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-indigo-500/25 transition hover:from-indigo-600 hover:to-purple-700 active:scale-95 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Send
          </button>
        </form>
      </div>
    </main>
  );
}
