import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { api } from "../api/client";
import type { DocStatus } from "../api/types";

const STATUS_STYLES: Record<DocStatus, string> = {
  ready: "text-good border-good/40",
  processing: "text-warning border-warning/40 animate-pulse",
  pending: "text-sub border-hairline",
  unsupported: "text-serious border-serious/40",
  error: "text-critical border-critical/40",
};

export default function Documents() {
  const queryClient = useQueryClient();
  const [importPath, setImportPath] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);

  const documents = useQuery({
    queryKey: ["documents"],
    queryFn: api.documents,
    refetchInterval: (query) =>
      query.state.data?.some((d) => d.status === "pending" || d.status === "processing")
        ? 2000
        : false,
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["documents"] });
  const upload = useMutation({ mutationFn: api.uploadDocument, onSuccess: invalidate });
  const importDir = useMutation({
    mutationFn: api.importPath,
    onSuccess: () => {
      setImportPath("");
      invalidate();
    },
  });
  const remove = useMutation({ mutationFn: api.deleteDocument, onSuccess: invalidate });

  return (
    <div className="max-w-4xl">
      <header className="mb-6">
        <div className="section-tag mb-1">library</div>
        <h2 className="text-xl font-semibold">Documents</h2>
      </header>

      <div className="grid sm:grid-cols-2 gap-3 mb-6">
        <div
          className="panel px-5 py-6 text-center border-dashed cursor-pointer hover:border-s1 transition-colors"
          onClick={() => fileInput.current?.click()}
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            event.preventDefault();
            for (const file of Array.from(event.dataTransfer.files)) {
              upload.mutate(file);
            }
          }}
          role="button"
          aria-label="upload documents"
        >
          <div className="section-tag mb-2">upload</div>
          <p className="text-sm text-sub">Drop PDF / Markdown / TXT here, or click to choose.</p>
          <input
            ref={fileInput}
            type="file"
            multiple
            accept=".pdf,.md,.markdown,.txt"
            className="hidden"
            aria-label="file input"
            onChange={(event) => {
              for (const file of Array.from(event.target.files ?? [])) {
                upload.mutate(file);
              }
              event.target.value = "";
            }}
          />
        </div>
        <div className="panel px-5 py-4">
          <div className="section-tag mb-2">bulk import</div>
          <p className="text-[11px] text-muted mb-2">
            Folder path relative to the active storage root.
          </p>
          <div className="flex gap-2">
            <input
              aria-label="import path"
              value={importPath}
              onChange={(event) => setImportPath(event.target.value)}
              placeholder="e.g. archive/2024"
              className="flex-1 bg-surface border border-hairline rounded-sm px-3 py-1.5 font-mono text-sm focus:border-s1 outline-none"
            />
            <button
              onClick={() => importPath && importDir.mutate(importPath)}
              disabled={!importPath || importDir.isPending}
              className="font-mono text-xs border border-s1 text-s1 px-3 rounded-sm hover:bg-s1 hover:text-page transition-colors disabled:opacity-40"
            >
              IMPORT
            </button>
          </div>
        </div>
      </div>

      {(upload.isError || importDir.isError) && (
        <p role="alert" className="mb-4 text-sm text-critical">
          {((upload.error ?? importDir.error) as Error).message}
        </p>
      )}

      <div className="panel overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left border-b border-hairline">
              {["document", "format", "status", "chunks", ""].map((heading) => (
                <th key={heading} className="section-tag font-normal px-4 py-3">
                  {heading}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {documents.data?.map((doc) => (
              <tr key={doc.id} className="border-b border-hairline/50">
                <td className="px-4 py-2.5">
                  <div className="text-ink">{doc.title ?? doc.filename}</div>
                  <div className="font-mono text-[10px] text-muted">
                    {doc.filename}
                    {doc.pages ? ` · ${doc.pages}p` : ""}
                  </div>
                  {doc.error && (
                    <div className="text-[11px] text-serious mt-1 max-w-md">{doc.error}</div>
                  )}
                </td>
                <td className="px-4 py-2.5 font-mono text-xs text-sub">{doc.format}</td>
                <td className="px-4 py-2.5">
                  <span
                    className={`font-mono text-[10px] uppercase tracking-widest border px-2 py-0.5 rounded-sm ${STATUS_STYLES[doc.status]}`}
                  >
                    {doc.status}
                  </span>
                </td>
                <td className="px-4 py-2.5 font-mono text-xs">{doc.chunk_count ?? "—"}</td>
                <td className="px-4 py-2.5 text-right">
                  <button
                    onClick={() => remove.mutate(doc.id)}
                    aria-label={`delete ${doc.filename}`}
                    className="text-[11px] text-muted hover:text-critical transition-colors"
                  >
                    delete
                  </button>
                </td>
              </tr>
            ))}
            {documents.data?.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-sub text-sm">
                  No documents yet — upload something above.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
