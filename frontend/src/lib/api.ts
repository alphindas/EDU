import { useAuth } from "./auth";
import type { TokenOut } from "./types";

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

let refreshing: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
  const { refresh, setSession, logout } = useAuth.getState();
  if (!refresh) return false;
  refreshing ??= fetch("/api/auth/refresh", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ refresh_token: refresh }),
  })
    .then(async (r) => {
      if (!r.ok) { logout(); return false; }
      setSession((await r.json()) as TokenOut);
      return true;
    })
    .catch(() => false)
    .finally(() => { refreshing = null; });
  return refreshing;
}

export async function api<T = unknown>(path: string, init: RequestInit & { json?: unknown } = {}, retry = true): Promise<T> {
  const { access } = useAuth.getState();
  const headers = new Headers(init.headers);
  if (init.json !== undefined) headers.set("Content-Type", "application/json");
  if (access) headers.set("Authorization", `Bearer ${access}`);
  const res = await fetch(`/api${path}`, { ...init, headers, body: init.json !== undefined ? JSON.stringify(init.json) : init.body });
  if (res.status === 401 && retry && access && (await tryRefresh())) return api<T>(path, init, false);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const b = await res.json();
      detail = typeof b.detail === "string" ? b.detail : Array.isArray(b.detail) ? b.detail.map((d: { msg: string }) => d.msg).join("; ") : detail;
    } catch { /* non-JSON error */ }
    if (res.status === 403 && detail === "password_change_required") window.location.assign("/change-password");
    if (res.status === 401 && !path.startsWith("/auth/")) useAuth.getState().logout();
    throw new ApiError(res.status, detail);
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

export const get = <T,>(p: string) => api<T>(p);
export const post = <T,>(p: string, json?: unknown) => api<T>(p, { method: "POST", json });
export const put = <T,>(p: string, json?: unknown) => api<T>(p, { method: "PUT", json });
export const patch = <T,>(p: string, json?: unknown) => api<T>(p, { method: "PATCH", json });
export const del = (p: string) => api<void>(p, { method: "DELETE" });

/** multipart upload (do not set Content-Type: the browser adds the boundary). */
export const upload = <T,>(method: "POST" | "PUT", p: string, fd: FormData) => api<T>(p, { method, body: fd });

/** Authenticated binary fetch (images/PDFs sit behind auth, so <img src> can't be used directly). */
export async function fetchBlob(path: string, retry = true): Promise<Blob> {
  const { access } = useAuth.getState();
  const res = await fetch(`/api${path}`, { headers: access ? { Authorization: `Bearer ${access}` } : {} });
  if (res.status === 401 && retry && access && (await tryRefresh())) return fetchBlob(path, false);
  if (!res.ok) throw new ApiError(res.status, res.statusText);
  return res.blob();
}
