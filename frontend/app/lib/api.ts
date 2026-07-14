// Lightweight client auth: JWT in localStorage + a fetch wrapper that attaches
// the Authorization header and bounces to /login on 401. All API calls are
// relative (Next.js rewrites proxy them to the backend).

const TOKEN_KEY = "agi_token";
const USER_KEY = "agi_user";

export type User = { id: number | string; name: string; email: string; role: string };

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function getUser(): User | null {
  if (typeof window === "undefined") return null;
  try {
    return JSON.parse(localStorage.getItem(USER_KEY) || "null");
  } catch {
    return null;
  }
}

export function setAuth(token: string, user: User) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export function logout() {
  clearAuth();
  if (typeof window !== "undefined") window.location.href = "/login";
}

export async function authFetch(path: string, opts: RequestInit = {}): Promise<Response> {
  const token = getToken();
  const headers: Record<string, string> = { ...(opts.headers as Record<string, string>) };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(path, { ...opts, headers });
  if (res.status === 401 && typeof window !== "undefined") {
    clearAuth();
    const p = window.location.pathname;
    if (!p.startsWith("/login") && !p.startsWith("/signup")) window.location.href = "/login";
  }
  return res;
}
