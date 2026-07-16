"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { apiJson, getToken } from "../lib/api";

// Relative — Next.js rewrites proxy these to the backend (see next.config.ts).
const API_URL = "";

type ImportPreview = {
  filename: string;
  total_rows: number;
  mapping: Record<string, string>;
  columns: string[];
  preview: Record<string, string | number>[];
  errors: string[];
};

type ImportResult = { imported: number; skipped: number; errors: string[]; filename: string };

const TABLES = ["customers", "invoices", "products", "expenses", "sales"] as const;
type Table = (typeof TABLES)[number];

type Row = Record<string, string | number | null>;

export default function Admin() {
  const [table, setTable] = useState<Table>("customers");
  const [columns, setColumns] = useState<string[]>([]);
  const [keyCol, setKeyCol] = useState<string>("id");
  const [rows, setRows] = useState<Row[]>([]);
  const [editing, setEditing] = useState<Row | null>(null); // row being edited (or new)
  const [isNew, setIsNew] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  // CSV/Excel import state
  const fileRef = useRef<HTMLInputElement>(null);
  const pendingFile = useRef<File | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);

  useEffect(() => {
    if (!getToken()) router.replace("/login");
  }, [router]);

  async function onFilePicked(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ""; // allow re-picking the same file
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) return setError("File too large (max 5 MB).");
    pendingFile.current = file;
    setError(null);
    setImportResult(null);
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const data = await apiJson<ImportPreview>(`${API_URL}/api/admin/preview-import/${table}`, {
        method: "POST",
        body: fd,
      });
      setPreview(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Preview failed");
    } finally {
      setBusy(false);
    }
  }

  async function confirmImport() {
    if (!pendingFile.current) return;
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", pendingFile.current);
      const data = await apiJson<ImportResult>(`${API_URL}/api/admin/import/${table}`, {
        method: "POST",
        body: fd,
      });
      setImportResult(data);
      setPreview(null);
      await load(table);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed");
    } finally {
      setBusy(false);
    }
  }

  const load = useCallback(async (t: Table) => {
    setError(null);
    try {
      const data = await apiJson<{ columns: string[]; key: string; rows: Row[] }>(
        `${API_URL}/api/admin/${t}`
      );
      setColumns(data?.columns ?? []);
      setKeyCol(data?.key ?? "id");
      setRows(data?.rows ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't load data.");
    }
  }, []);

  useEffect(() => {
    load(table);
  }, [table, load]);

  function startNew() {
    const blank: Row = {};
    columns.forEach((c) => (blank[c] = ""));
    setEditing(blank);
    setIsNew(true);
  }

  function startEdit(row: Row) {
    setEditing({ ...row });
    setIsNew(false);
  }

  async function save() {
    if (!editing) return;
    setBusy(true);
    setError(null);
    try {
      const payload: Row = {};
      columns.forEach((c) => {
        if (editing[c] !== "" && editing[c] !== null && editing[c] !== undefined)
          payload[c] = editing[c];
      });
      const url = isNew
        ? `${API_URL}/api/admin/${table}`
        : `${API_URL}/api/admin/${table}/${editing[keyCol]}`;
      await apiJson(url, {
        method: isNew ? "POST" : "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ data: payload }),
      });
      setEditing(null);
      await load(table);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed");
    } finally {
      setBusy(false);
    }
  }

  async function remove(row: Row) {
    if (!confirm(`Are you sure you want to delete this ${table} row?`)) return;
    setBusy(true);
    setError(null);
    try {
      await apiJson(`${API_URL}/api/admin/${table}/${row[keyCol]}`, { method: "DELETE" });
      await load(table);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Delete failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-full bg-[#050807] font-sans text-emerald-50/90">
      <header className="sticky top-0 z-20 border-b border-emerald-500/10 bg-[#050807]/80 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-emerald-500/30 bg-emerald-500/10 text-lg">
              🗂️
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-wide text-emerald-300">Admin Panel</h1>
              <p className="text-xs text-emerald-200/40">Level 1 — manage business data</p>
            </div>
          </div>
          <nav className="flex items-center gap-2">
            <a
              href="/"
              className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 px-3 py-2 text-xs font-semibold text-emerald-300/80 transition hover:bg-emerald-500/10"
            >
              ← Chat
            </a>
            <a
              href="/dashboard"
              className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 px-3 py-2 text-xs font-semibold text-emerald-300/80 transition hover:bg-emerald-500/10"
            >
              Dashboard →
            </a>
          </nav>
        </div>
      </header>

      <div className="mx-auto max-w-6xl px-4 py-6">
        {/* Tabs */}
        <div className="mb-4 flex flex-wrap gap-2">
          {TABLES.map((t) => (
            <button
              key={t}
              onClick={() => {
                setEditing(null);
                setTable(t);
              }}
              className={`rounded-xl border px-4 py-2 text-xs font-semibold capitalize transition ${
                table === t
                  ? "border-emerald-400/50 bg-emerald-500/15 text-emerald-200"
                  : "border-emerald-500/15 bg-emerald-500/[0.04] text-emerald-300/60 hover:bg-emerald-500/10"
              }`}
            >
              {t}
            </button>
          ))}
          <input
            ref={fileRef}
            type="file"
            accept=".csv,.xlsx,.xls"
            onChange={onFilePicked}
            className="hidden"
          />
          <button
            onClick={() => fileRef.current?.click()}
            disabled={busy}
            className="ml-auto rounded-xl border border-emerald-500/25 bg-emerald-500/10 px-4 py-2 text-xs font-semibold text-emerald-200 transition hover:bg-emerald-500/15 active:scale-95 disabled:opacity-40"
          >
            📥 Import CSV/Excel
          </button>
          <button
            onClick={startNew}
            className="rounded-xl bg-gradient-to-br from-emerald-400 to-teal-500 px-4 py-2 text-xs font-semibold text-black shadow-md shadow-emerald-500/25 transition hover:from-emerald-300 hover:to-teal-400 active:scale-95"
          >
            + Add New
          </button>
        </div>

        {importResult && (
          <div className="mb-3 rounded-xl border border-emerald-400/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-200">
            ✅ {importResult.imported} rows imported, {importResult.skipped} skipped
            {importResult.errors.length > 0 && (
              <ul className="mt-1 list-disc pl-4 text-amber-300/80">
                {importResult.errors.slice(0, 5).map((er, i) => (
                  <li key={i}>{er}</li>
                ))}
              </ul>
            )}
          </div>
        )}

        {/* Import preview modal */}
        {preview && (
          <div className="fixed inset-0 z-30 flex items-center justify-center bg-black/60 p-4">
            <div className="max-h-[85vh] w-full max-w-2xl overflow-auto rounded-2xl border border-emerald-500/25 bg-[#070c0a] p-5">
              <h3 className="mb-1 text-sm font-bold text-emerald-200">
                Import into {table}
              </h3>
              <p className="mb-3 text-xs text-emerald-200/50">
                {preview.filename} · {preview.total_rows} rows · mapped columns:{" "}
                {preview.columns.join(", ") || "none"}
              </p>
              {preview.errors.length > 0 && (
                <ul className="mb-3 list-disc rounded-lg border border-amber-400/30 bg-amber-500/10 py-2 pl-6 text-xs text-amber-300">
                  {preview.errors.map((er, i) => (
                    <li key={i}>{er}</li>
                  ))}
                </ul>
              )}
              <div className="overflow-x-auto rounded-lg border border-emerald-500/15">
                <table className="w-full text-left text-xs">
                  <thead className="border-b border-emerald-500/15 text-emerald-300/60">
                    <tr>
                      {preview.columns.map((c) => (
                        <th key={c} className="px-2 py-1.5 capitalize">{c}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {preview.preview.map((row, i) => (
                      <tr key={i} className="border-b border-emerald-500/[0.07]">
                        {preview.columns.map((c) => (
                          <td key={c} className="px-2 py-1.5 text-emerald-50/80">
                            {String(row[c] ?? "")}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="mt-4 flex gap-2">
                <button
                  onClick={confirmImport}
                  disabled={busy || preview.columns.length === 0}
                  className="rounded-lg bg-emerald-500 px-4 py-2 text-xs font-semibold text-black transition hover:bg-emerald-400 disabled:opacity-40"
                >
                  {busy ? "Importing…" : "Confirm Import"}
                </button>
                <button
                  onClick={() => setPreview(null)}
                  className="rounded-lg border border-emerald-500/20 px-4 py-2 text-xs font-semibold text-emerald-300/70 transition hover:bg-emerald-500/10"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}

        {error && (
          <p className="mb-3 rounded-xl border border-rose-400/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-300">
            {error}
          </p>
        )}

        {/* Editor */}
        {editing && (
          <div className="mb-4 rounded-2xl border border-emerald-400/30 bg-emerald-500/[0.06] p-4">
            <h3 className="mb-3 text-sm font-bold text-emerald-200">
              {isNew ? "Add new" : "Edit"} {table} row
            </h3>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {columns.map((c) => (
                <label key={c} className="block">
                  <span className="mb-1 block text-[10px] font-semibold uppercase tracking-wide text-emerald-300/50">
                    {c}
                  </span>
                  <input
                    value={editing[c] ?? ""}
                    onChange={(e) => setEditing({ ...editing, [c]: e.target.value })}
                    className="w-full rounded-lg border border-emerald-500/20 bg-black/30 px-2.5 py-1.5 text-xs text-emerald-50 outline-none focus:border-emerald-400/50"
                  />
                </label>
              ))}
            </div>
            <div className="mt-3 flex gap-2">
              <button
                onClick={save}
                disabled={busy}
                className="rounded-lg bg-emerald-500 px-4 py-2 text-xs font-semibold text-black transition hover:bg-emerald-400 disabled:opacity-40"
              >
                {busy ? "Saving…" : "Save"}
              </button>
              <button
                onClick={() => setEditing(null)}
                className="rounded-lg border border-emerald-500/20 px-4 py-2 text-xs font-semibold text-emerald-300/70 transition hover:bg-emerald-500/10"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Data table */}
        <div className="overflow-x-auto rounded-2xl border border-emerald-500/15 bg-emerald-500/[0.04]">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-emerald-500/15 text-emerald-300/60">
              <tr>
                {columns.map((c) => (
                  <th key={c} className="px-3 py-2 font-semibold capitalize">
                    {c}
                  </th>
                ))}
                <th className="px-3 py-2 text-right font-semibold">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 && (
                <tr>
                  <td colSpan={columns.length + 1} className="px-3 py-6 text-center text-emerald-200/30">
                    No rows.
                  </td>
                </tr>
              )}
              {rows.map((row, i) => (
                <tr
                  key={String(row[keyCol] ?? i)}
                  className="border-b border-emerald-500/[0.07] transition hover:bg-emerald-500/[0.05]"
                >
                  {columns.map((c) => (
                    <td key={c} className="max-w-[220px] truncate px-3 py-2 text-emerald-50/80">
                      {row[c] === null || row[c] === undefined ? (
                        <span className="text-emerald-200/20">—</span>
                      ) : (
                        String(row[c])
                      )}
                    </td>
                  ))}
                  <td className="px-3 py-2 text-right">
                    <button
                      onClick={() => startEdit(row)}
                      className="mr-1 rounded-md border border-emerald-500/25 px-2 py-1 text-[10px] font-semibold text-emerald-300/80 transition hover:bg-emerald-500/10"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => remove(row)}
                      className="rounded-md border border-rose-400/25 px-2 py-1 text-[10px] font-semibold text-rose-300/80 transition hover:bg-rose-500/10"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-[10px] text-emerald-200/30">
          Internal admin tool · unauthenticated (add auth before production).
        </p>
      </div>
    </main>
  );
}
