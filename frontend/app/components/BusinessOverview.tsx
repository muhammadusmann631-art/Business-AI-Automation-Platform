"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export type BusinessStats = {
  revenue_trend: { month: string; amount: number }[];
  expense_breakdown: { category: string; amount: number }[];
  top_customers: { name: string; revenue: number }[];
  invoice_status: { status: string; count: number }[];
  summary: {
    total_revenue: number;
    total_expenses: number;
    net_profit: number;
    active_customers: number;
    pending_invoices: number;
    overdue_invoices: number;
  };
  pnl?: {
    period: string;
    revenue: number;
    expenses: { total: number };
    net: number;
    status: "PROFIT" | "LOSS";
    comparison: { previous_period: string; change_percent: number; trend: string };
  } | null;
};

const GREENS = ["#10b981", "#14b8a6", "#059669", "#0d9488", "#34d399", "#2dd4bf"];
const STATUS_COLORS: Record<string, string> = {
  paid: "#10b981",
  pending: "#f5b301",
  overdue: "#f43f5e",
  cancelled: "#64748b",
};

const AXIS = { fill: "#6ee7b7", fontSize: 11 };
const TOOLTIP = {
  contentStyle: {
    background: "#04110d",
    border: "1px solid rgba(16,185,129,0.3)",
    borderRadius: 10,
    color: "#d1fae5",
    fontSize: 12,
  },
};

function money(n: number) {
  return "$" + (n || 0).toLocaleString();
}

function Panel({ title, children, empty }: { title: string; children: React.ReactNode; empty: boolean }) {
  return (
    <div className="rounded-2xl border border-emerald-500/15 bg-emerald-500/[0.05] p-4">
      <h3 className="mb-2 text-xs font-bold uppercase tracking-wide text-emerald-300/70">{title}</h3>
      {empty ? (
        <div className="flex h-[200px] items-center justify-center text-xs text-emerald-200/30">
          No data yet
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={200}>
          {children as React.ReactElement}
        </ResponsiveContainer>
      )}
    </div>
  );
}

export default function BusinessOverview({ stats }: { stats: BusinessStats | null }) {
  if (!stats) return null;
  const s = stats.summary;

  const cards = [
    { label: "Total Revenue", value: money(s.total_revenue), tone: "text-emerald-300" },
    { label: "Total Expenses", value: money(s.total_expenses), tone: "text-amber-300" },
    { label: "Net Profit", value: money(s.net_profit), tone: s.net_profit >= 0 ? "text-emerald-300" : "text-rose-300" },
    { label: "Active Customers", value: String(s.active_customers), tone: "text-teal-300" },
    { label: "Pending Invoices", value: String(s.pending_invoices), tone: "text-amber-300" },
    { label: "Overdue Invoices", value: String(s.overdue_invoices), tone: "text-rose-300" },
  ];

  return (
    <section className="mb-8">
      <h2 className="mb-3 flex items-center gap-2 text-sm font-bold text-emerald-200">
        <span>📊</span> Business Overview
      </h2>

      {stats.pnl && (
        <div
          className={`mb-3 flex flex-wrap items-center gap-x-8 gap-y-2 rounded-2xl border bg-emerald-500/[0.05] px-5 py-4 ${
            stats.pnl.status === "PROFIT" ? "border-emerald-500/30" : "border-rose-500/30"
          }`}
        >
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wide text-emerald-200/40">
              {stats.pnl.period} · P&amp;L
            </p>
            <p className={`text-2xl font-bold ${stats.pnl.status === "PROFIT" ? "text-emerald-300" : "text-rose-300"}`}>
              {stats.pnl.net < 0 ? "-" : ""}${Math.abs(stats.pnl.net).toLocaleString()}{" "}
              <span className="text-sm">{stats.pnl.status === "PROFIT" ? "profit" : "loss"}</span>
            </p>
          </div>
          <div className="text-xs text-emerald-200/60">
            <p>Revenue: <span className="text-emerald-200">{money(stats.pnl.revenue)}</span></p>
            <p>Expenses: <span className="text-amber-200">{money(stats.pnl.expenses.total)}</span></p>
          </div>
          {stats.pnl.comparison.change_percent !== 0 && (
            <div className={`text-xs ${stats.pnl.comparison.trend === "UP" ? "text-emerald-300" : "text-rose-300"}`}>
              {stats.pnl.comparison.trend === "UP" ? "↑" : "↓"}{" "}
              {Math.abs(stats.pnl.comparison.change_percent)}% vs {stats.pnl.comparison.previous_period}
            </div>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <Panel title="Revenue Trend" empty={stats.revenue_trend.length === 0}>
          <LineChart data={stats.revenue_trend} margin={{ top: 5, right: 10, bottom: 0, left: -10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(16,185,129,0.12)" />
            <XAxis dataKey="month" tick={AXIS} tickFormatter={(m: string) => m.slice(0, 3)} />
            <YAxis tick={AXIS} tickFormatter={(v: number) => `${v / 1000}k`} />
            <Tooltip {...TOOLTIP} formatter={(v) => money(Number(v))} />
            <Line type="monotone" dataKey="amount" stroke="#10b981" strokeWidth={2.5} dot={{ r: 3, fill: "#10b981" }} />
          </LineChart>
        </Panel>

        <Panel title="Expense Breakdown" empty={stats.expense_breakdown.length === 0}>
          <PieChart>
            <Pie
              data={stats.expense_breakdown}
              dataKey="amount"
              nameKey="category"
              innerRadius={45}
              outerRadius={75}
              paddingAngle={2}
            >
              {stats.expense_breakdown.map((_, i) => (
                <Cell key={i} fill={GREENS[i % GREENS.length]} stroke="#04110d" />
              ))}
            </Pie>
            <Tooltip {...TOOLTIP} formatter={(v) => money(Number(v))} />
            <Legend wrapperStyle={{ fontSize: 10, color: "#a7f3d0" }} />
          </PieChart>
        </Panel>

        <Panel title="Top 5 Customers" empty={stats.top_customers.length === 0}>
          <BarChart
            data={stats.top_customers}
            layout="vertical"
            margin={{ top: 5, right: 15, bottom: 0, left: 10 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(16,185,129,0.12)" horizontal={false} />
            <XAxis type="number" tick={AXIS} tickFormatter={(v: number) => `${v / 1000}k`} />
            <YAxis type="category" dataKey="name" tick={AXIS} width={90} />
            <Tooltip {...TOOLTIP} formatter={(v) => money(Number(v))} cursor={{ fill: "rgba(16,185,129,0.08)" }} />
            <Bar dataKey="revenue" fill="#14b8a6" radius={[0, 4, 4, 0]} />
          </BarChart>
        </Panel>

        <Panel title="Invoice Status" empty={stats.invoice_status.length === 0}>
          <PieChart>
            <Pie
              data={stats.invoice_status}
              dataKey="count"
              nameKey="status"
              innerRadius={45}
              outerRadius={75}
              paddingAngle={2}
            >
              {stats.invoice_status.map((d, i) => (
                <Cell key={i} fill={STATUS_COLORS[d.status] ?? GREENS[i % GREENS.length]} stroke="#04110d" />
              ))}
            </Pie>
            <Tooltip {...TOOLTIP} />
            <Legend wrapperStyle={{ fontSize: 10, color: "#a7f3d0" }} />
          </PieChart>
        </Panel>
      </div>

      {/* Summary cards */}
      <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {cards.map((c) => (
          <div key={c.label} className="rounded-2xl border border-emerald-500/15 bg-emerald-500/[0.05] p-3">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-emerald-200/40">{c.label}</p>
            <p className={`mt-1 text-lg font-bold ${c.tone}`}>{c.value}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
