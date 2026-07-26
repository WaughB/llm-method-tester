import type { Meta } from "./types";

export async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`GET ${path} -> ${response.status}`);
  return response.json() as Promise<T>;
}

export async function sendJson<T>(
  method: "POST" | "PUT" | "DELETE",
  path: string,
  body?: unknown,
): Promise<T> {
  const response = await fetch(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    throw new Error(detail?.detail ?? `${method} ${path} -> ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  meta: () => getJson<Meta>("/api/meta"),
};
