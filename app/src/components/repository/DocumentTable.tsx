import type { DocumentSummary } from "../../lib/types";

const STATUS_COLOR: Record<string, string> = {
  indexed: "var(--color-success)",
  pending: "var(--color-warning)",
  error: "var(--color-danger)",
};

export default function DocumentTable({
  documents,
  onSelect,
}: {
  documents: DocumentSummary[];
  onSelect: (id: string) => void;
}) {
  if (documents.length === 0) {
    return (
      <div className="py-12 text-center text-sm" style={{ color: "var(--color-text-muted)" }}>
        No documents match the current filters.
      </div>
    );
  }

  return (
    <table className="w-full text-left text-sm">
      <thead>
        <tr className="border-b text-xs uppercase tracking-wide" style={{ borderColor: "var(--color-border)", color: "var(--color-text-muted)" }}>
          <th className="py-2 pr-3 font-medium">Title</th>
          <th className="py-2 pr-3 font-medium">Course</th>
          <th className="py-2 pr-3 font-medium">Category</th>
          <th className="py-2 pr-3 font-medium">Type</th>
          <th className="py-2 pr-3 font-medium">Pages</th>
          <th className="py-2 pr-3 font-medium">Status</th>
        </tr>
      </thead>
      <tbody>
        {documents.map((doc) => (
          <tr
            key={doc.id}
            className="cursor-pointer border-b transition-colors hover:bg-black/[0.02]"
            style={{ borderColor: "var(--color-border)" }}
            onClick={() => onSelect(doc.id)}
          >
            <td className="max-w-xs truncate py-2 pr-3 font-medium" title={doc.title}>
              {doc.title}
            </td>
            <td className="max-w-[220px] truncate py-2 pr-3" style={{ color: "var(--color-text-muted)" }} title={doc.course ?? ""}>
              {doc.course_code ?? doc.course ?? "—"}
            </td>
            <td className="py-2 pr-3" style={{ color: "var(--color-text-muted)" }}>
              {doc.category ?? "—"}
            </td>
            <td className="py-2 pr-3" style={{ color: "var(--color-text-muted)" }}>
              {doc.material_type ?? doc.file_type}
            </td>
            <td className="py-2 pr-3" style={{ color: "var(--color-text-muted)" }}>
              {doc.page_count ?? "—"}
            </td>
            <td className="py-2 pr-3">
              <span className="inline-flex items-center gap-1.5">
                <span className="h-1.5 w-1.5 rounded-full" style={{ background: STATUS_COLOR[doc.status] }} />
                {doc.status}
              </span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
