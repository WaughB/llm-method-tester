import type {
  AppSettings,
  AskResponse,
  Conversation,
  DocumentRow,
  Job,
  Meta,
  StorageLocation,
} from "./types";

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
  locations: () =>
    getJson<{ locations: StorageLocation[] }>("/api/locations").then((r) => r.locations),
  activateLocation: (location_id: string) =>
    sendJson<StorageLocation>("PUT", "/api/locations/active", { location_id }),
  settings: () => getJson<AppSettings>("/api/settings"),
  updateSettings: (patch: Partial<AppSettings>) =>
    sendJson<AppSettings>("PUT", "/api/settings", patch),
  documents: () =>
    getJson<{ documents: DocumentRow[] }>("/api/documents").then((r) => r.documents),
  deleteDocument: (docId: string) => sendJson<unknown>("DELETE", `/api/documents/${docId}`),
  importPath: (path: string) =>
    sendJson<{ queued: unknown[] }>("POST", "/api/documents/import", { path }),
  uploadDocument: async (file: File): Promise<{ doc_id: string; job_id: number }> => {
    const form = new FormData();
    form.append("file", file);
    const response = await fetch("/api/documents", { method: "POST", body: form });
    if (!response.ok) {
      const detail = await response.json().catch(() => null);
      throw new Error(detail?.detail ?? `upload failed (${response.status})`);
    }
    return response.json();
  },
  jobs: (status?: string) =>
    getJson<{ jobs: Job[] }>(status ? `/api/jobs?status=${status}` : "/api/jobs").then(
      (r) => r.jobs,
    ),
  conversations: () =>
    getJson<{ conversations: Conversation[] }>("/api/conversations").then(
      (r) => r.conversations,
    ),
  conversation: (id: string) => getJson<Conversation>(`/api/conversations/${id}`),
  createConversation: (body: { title?: string; model?: string }) =>
    sendJson<Conversation>("POST", "/api/conversations", body),
  ask: (conversationId: string, question: string, usePageindexStage?: boolean) =>
    sendJson<AskResponse>("POST", `/api/conversations/${conversationId}/messages`, {
      question,
      use_pageindex_stage: usePageindexStage,
    }),
};
