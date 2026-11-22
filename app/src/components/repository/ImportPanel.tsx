import { useEffect, useRef, useState } from "react";
import { api } from "../../lib/api";
import type { ImportJobStatus, TermInfo } from "../../lib/types";

export default function ImportPanel({ onImportFinished }: { onImportFinished: () => void }) {
  const [terms, setTerms] = useState<TermInfo[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [job, setJob] = useState<ImportJobStatus | null>(null);
  const pollRef = useRef<number | null>(null);

  useEffect(() => {
    api.get<{ terms: TermInfo[] }>("/repository/terms").then((res) => setTerms(res.terms));
  }, []);

  useEffect(() => {
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
  }, []);

  function startImport(subpath: string) {
    api.post<{ job_id: string }>("/repository/import", { subpath }).then(({ job_id }) => {
      pollRef.current = window.setInterval(async () => {
        const status = await api.get<ImportJobStatus>(`/repository/import/status/${job_id}`);
        setJob(status);
        if (status.status === "done") {
          if (pollRef.current) window.clearInterval(pollRef.current);
          onImportFinished();
        }
      }, 1000);
    });
  }

  const running = job !== null && job.status === "running";
  const progressPct = job && job.total > 0 ? Math.round((job.processed / job.total) * 100) : 0;

  return (
    <div
      className="rounded-lg border p-4"
      style={{ borderColor: "var(--color-border)", background: "var(--color-surface)" }}
    >
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold">Import from moodle-bak</h2>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <select
          className="rounded-md border px-2 py-1.5 text-sm"
          style={{ borderColor: "var(--color-border)", background: "var(--color-bg)" }}
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          disabled={running}
        >
          <option value="">Entire repository (all terms)</option>
          {terms.map((t) => (
            <option key={t.name} value={t.name}>
              {t.name} ({t.courses.length} courses)
            </option>
          ))}
        </select>
        <button
          className="rounded-md px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
          style={{ background: "var(--color-primary)" }}
          disabled={running}
          onClick={() => startImport(selected)}
        >
          {running ? "Importing..." : "Import"}
        </button>
      </div>

      {job && (
        <div className="mt-3 space-y-1.5">
          <div className="h-2 w-full overflow-hidden rounded-full" style={{ background: "var(--color-border)" }}>
            <div
              className="h-full rounded-full transition-all"
              style={{ width: `${progressPct}%`, background: "var(--color-accent)" }}
            />
          </div>
          <div className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            {job.status === "done"
              ? `Done — ${job.indexed} indexed, ${job.skipped_duplicates} duplicates skipped, ${job.errors.length} errors (${job.processed}/${job.total} files)`
              : `${job.processed}/${job.total} — ${job.current_file ?? "..."}`}
          </div>
          {job.errors.length > 0 && (
            <details className="text-xs" style={{ color: "var(--color-danger)" }}>
              <summary className="cursor-pointer">{job.errors.length} file(s) failed to parse</summary>
              <ul className="mt-1 list-disc pl-4">
                {job.errors.slice(0, 20).map((e, i) => (
                  <li key={i}>
                    {e.file.split("/").pop()}: {e.error}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}
    </div>
  );
}
