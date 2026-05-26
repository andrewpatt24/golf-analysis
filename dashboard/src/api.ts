const base = import.meta.env.VITE_API_BASE_URL ?? "";

function accessToken(): string | null {
  if (typeof window === "undefined") return null;
  return new URLSearchParams(window.location.search).get("token");
}

function apiUrl(path: string): string {
  const raw = path.startsWith("http") ? path : `${base}${path}`;
  const token = accessToken();
  if (!token) return raw;
  const u = new URL(raw, window.location.origin);
  if (!u.searchParams.has("token")) u.searchParams.set("token", token);
  return u.pathname + u.search;
}

function apiAuthHeaders(jsonBody = false): HeadersInit {
  const token = accessToken();
  const h: Record<string, string> = {};
  if (jsonBody) h["Content-Type"] = "application/json";
  if (token) h.Authorization = `Bearer ${token}`;
  return h;
}

export async function apiGet<T>(path: string): Promise<T> {
  const url = apiUrl(path);
  const res = await fetch(url, { headers: apiAuthHeaders() });
  if (!res.ok) {
    const t = await res.text();
    throw new Error(t || res.statusText);
  }
  return res.json() as Promise<T>;
}

export async function apiPut<T>(path: string, body: unknown): Promise<T> {
  const url = apiUrl(path);
  const res = await fetch(url, {
    method: "PUT",
    headers: apiAuthHeaders(true),
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const t = await res.text();
    throw new Error(t || res.statusText);
  }
  return res.json() as Promise<T>;
}
