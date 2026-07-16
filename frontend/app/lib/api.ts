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
  return fetch(path, { ...opts, headers });
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

// The ONE wrapper every authenticated request should use. It:
//  - always attaches the auth token (via authFetch),
//  - checks response.ok BEFORE parsing (never parses non-JSON error bodies),
//  - on 401 → clears the session, redirects to /login, throws a clean message,
//  - on any other error → throws a clean, user-safe message (no "Unexpected
//    token..." ever reaches the UI).
export async function apiJson<T = unknown>(path: string, opts: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await authFetch(path, opts);
  } catch {
    throw new ApiError("Couldn't reach the server. Is the backend running?", 0);
  }

  if (res.status === 401) {
    clearAuth();
    if (typeof window !== "undefined") {
      const p = window.location.pathname;
      if (!p.startsWith("/login") && !p.startsWith("/signup")) window.location.href = "/login";
    }
    throw new ApiError("Session expired — please log in again.", 401);
  }

  if (!res.ok) {
    let detail = "Something went wrong, please try again.";
    try {
      const data = await res.json();
      if (data && typeof data.detail === "string") detail = data.detail;
    } catch {
      /* non-JSON error body (e.g. plain "Internal Server Error") — keep generic */
    }
    throw new ApiError(detail, res.status);
  }

  try {
    return (await res.json()) as T;
  } catch {
    return null as T; // successful but empty/no body
  }
}
