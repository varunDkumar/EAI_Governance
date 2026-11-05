import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../lib/api";
import { useRetryingEffect } from "../lib/useRetryingEffect";
import type { DocumentSummary, RepositoryStats } from "../lib/types";
import ImportPanel from "../components/repository/ImportPanel";
import DocumentTable from "../components/repository/DocumentTable";
import DocumentDetail from "../components/repository/DocumentDetail";

export default function Repository() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [stats, setStats] = useState<RepositoryStats | null>(null);
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [term, setTerm] = useState("");
  const [category, setCategory] = useState("");
  const [status, setStatus] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(searchParams.get("doc"));

  const refresh = useCallback(() => {
    const params = new URLSearchParams();
    if (search) params.set("q", search);
    if (term) params.set("term", term);
    if (category) params.set("category", category);
    if (status) params.set("status", status);
    params.set("limit", "200");
    return Promise.all([
      api.get<RepositoryStats>("/repository/stats").then(setStats),
      api
        .get<{ total: number; documents: DocumentSummary[] }>(`/repository/documents?${params.toString()}`)
        .then((res) => {
          setDocuments(res.documents);
          setTotal(res.total);
        }),
    ]);
  }, [search, term, category, status]);

  useRetryingEffect(refresh, [refresh]);

  useEffect(() => {
    const docParam = searchParams.get("doc");
    if (docParam) setSelectedId(docParam);
  }, [searchParams]);

  function closeDetail() {
    setSelectedId(null);
    if (searchParams.get("doc")) {
      const next = new URLSearchParams(searchParams);
      next.delete("doc");
      setSearchParams(next, { replace: true });
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold">Knowledge Repository</h1>
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          Imported academic documents, indexed with page/slide-level citations.
        </p>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <StatCard label="Documents" value={stats?.total ?? "—"} />
        <StatCard label="Indexed" value={stats?.indexed ?? "—"} />
        <StatCard label="Failed" value={stats?.errored ?? "—"} accent={stats && stats.errored > 0 ? "var(--color-danger)" : undefined} />
      </div>

      <ImportPanel onImportFinished={refresh} />

      <div
        className="rounded-lg border"
        style={{ borderColor: "var(--color-border)", background: "var(--color-surface)" }}
      >
        <div className="flex flex-wrap items-center gap-2 border-b p-3" style={{ borderColor: "var(--color-border)" }}>
          <input
            className="min-w-[200px] flex-1 rounded-md border px-2.5 py-1.5 text-sm"
            style={{ borderColor: "var(--color-border)", background: "var(--color-bg)" }}
            placeholder="Search by title..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <select
            className="rounded-md border px-2 py-1.5 text-sm"
            style={{ borderColor: "var(--color-border)", background: "var(--color-bg)" }}
            value={term}
            onChange={(e) => setTerm(e.target.value)}
          >
            <option value="">All terms</option>
            {stats && Object.keys(stats.by_term).sort().map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
          <select
            className="rounded-md border px-2 py-1.5 text-sm"
            style={{ borderColor: "var(--color-border)", background: "var(--color-bg)" }}
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          >
            <option value="">All categories</option>
            {stats && Object.keys(stats.by_category).sort().map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <select
            className="rounded-md border px-2 py-1.5 text-sm"
            style={{ borderColor: "var(--color-border)", background: "var(--color-bg)" }}
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="">All statuses</option>
            <option value="indexed">Indexed</option>
            <option value="pending">Pending</option>
            <option value="error">Error</option>
          </select>
          <span className="ml-auto text-xs" style={{ color: "var(--color-text-muted)" }}>
            {total} result{total === 1 ? "" : "s"}
          </span>
        </div>
        <div className="p-3">
          <DocumentTable documents={documents} onSelect={setSelectedId} />
        </div>
      </div>

      {selectedId && (
        <DocumentDetail documentId={selectedId} initialPage={searchParams.get("page")} onClose={closeDetail} />
      )}
    </div>
  );
}

function StatCard({ label, value, accent }: { label: string; value: string | number; accent?: string }) {
  return (
    <div className="rounded-lg border p-3" style={{ borderColor: "var(--color-border)", background: "var(--color-surface)" }}>
      <div className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        {label}
      </div>
      <div className="text-xl font-semibold" style={{ color: accent }}>
        {value}
      </div>
    </div>
  );
}
