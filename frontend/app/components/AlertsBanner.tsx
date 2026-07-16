"use client";

import { useCallback, useEffect, useState } from "react";
import { apiJson } from "../lib/api";

type Alert = { id: string; level: "critical" | "warning" | "info"; message: string; details: string[] };

const STYLE: Record<string, { border: string; icon: string; text: string }> = {
  critical: { border: "border-l-rose-500", icon: "🔴", text: "text-rose-200" },
  warning: { border: "border-l-amber-400", icon: "🟡", text: "text-amber-200" },
  info: { border: "border-l-emerald-400", icon: "🟢", text: "text-emerald-200" },
};

export default function AlertsBanner() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await apiJson<{ alerts: Alert[] }>("/api/alerts");
      setAlerts(data?.alerts ?? []);
      setLoaded(true);
    } catch {
      /* keep old on transient failure */
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 60000);
    return () => clearInterval(id);
  }, [load]);

  async function dismiss(id: string) {
    setAlerts((prev) => prev.filter((a) => a.id !== id)); // optimistic
    try {
      await apiJson(`/api/alerts/dismiss/${id}`, { method: "POST" });
    } catch {
      /* ignore */
    }
  }

  if (!loaded) return null;

  return (
    <section className="mb-6">
      <h2 className="mb-2 flex items-center gap-2 text-sm font-bold text-emerald-200">
        <span>⚠️</span> Alerts {alerts.length > 0 && <span className="text-emerald-200/40">({alerts.length} active)</span>}
      </h2>

      {alerts.length === 0 ? (
        <div className="rounded-2xl border border-emerald-500/15 bg-emerald-500/[0.05] px-4 py-3 text-sm text-emerald-300/80">
          ✅ No issues — everything looks good!
        </div>
      ) : (
        <div className="space-y-2">
          {alerts.map((a) => {
            const st = STYLE[a.level];
            const open = expanded === a.id;
            return (
              <div
                key={a.id}
                className={`rounded-xl border border-emerald-500/15 border-l-4 ${st.border} bg-emerald-500/[0.05]`}
              >
                <div className="flex items-center gap-2 px-3 py-2">
                  <button
                    onClick={() => setExpanded(open ? null : a.id)}
                    className={`flex flex-1 items-center gap-2 text-left text-sm ${st.text}`}
                  >
                    <span>{st.icon}</span>
                    <span>{a.message}</span>
                    {a.details.length > 0 && (
                      <span className="text-xs text-emerald-200/30">{open ? "▾" : "▸"}</span>
                    )}
                  </button>
                  <button
                    onClick={() => dismiss(a.id)}
                    className="rounded-md px-2 py-0.5 text-xs text-emerald-200/40 transition hover:bg-emerald-500/10 hover:text-emerald-200"
                    title="Dismiss"
                  >
                    ✕
                  </button>
                </div>
                {open && a.details.length > 0 && (
                  <ul className="list-disc space-y-0.5 border-t border-emerald-500/10 px-8 py-2 text-xs text-emerald-100/70">
                    {a.details.map((d, i) => (
                      <li key={i}>{d}</li>
                    ))}
                  </ul>
                )}
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
