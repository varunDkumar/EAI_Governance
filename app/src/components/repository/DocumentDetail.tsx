import { useEffect, useRef, useState } from "react";
import { api } from "../../lib/api";
import type { DocumentDetail as DocumentDetailType } from "../../lib/types";

export default function DocumentDetail({
  documentId,
  initialPage,
  onClose,
}: {
  documentId: string;
  initialPage?: string | null;
  onClose: () => void;
}) {
  const [doc, setDoc] = useState<DocumentDetailType | null>(null);
  const highlightRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setDoc(null);
    api.get<DocumentDetailType>(`/repository/documents/${documentId}`).then(setDoc);
  }, [documentId]);

  useEffect(() => {
    if (doc && highlightRef.current) {
      highlightRef.current.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [doc]);

  const targetPage = initialPage ? Number(initialPage) : null;

  return (
    <div className="fixed inset-0 z-20 flex justify-end bg-black/20" onClick={onClose}>
      <div
        className="h-full w-full max-w-lg overflow-y-auto border-l p-5"
        style={{ background: "var(--color-surface)", borderColor: "var(--color-border)" }}
        onClick={(e) => e.stopPropagation()}
      >
        {!doc ? (
          <div className="text-sm" style={{ color: "var(--color-text-muted)" }}>
            Loading...
          </div>
        ) : (
          <>
            <div className="mb-4 flex items-start justify-between gap-2">
              <h2 className="text-base font-semibold">{doc.title}</h2>
              <button onClick={onClose} className="text-sm" style={{ color: "var(--color-text-muted)" }}>
                Close
              </button>
            </div>
            <dl className="mb-4 grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
              <dt style={{ color: "var(--color-text-muted)" }}>Course</dt>
              <dd>{doc.course ?? "—"}</dd>
              <dt style={{ color: "var(--color-text-muted)" }}>Term</dt>
              <dd>{doc.term ?? "—"}</dd>
              <dt style={{ color: "var(--color-text-muted)" }}>Category</dt>
              <dd>{doc.category ?? "—"}</dd>
              <dt style={{ color: "var(--color-text-muted)" }}>Collection</dt>
              <dd>{doc.material_type ?? "—"}</dd>
              <dt style={{ color: "var(--color-text-muted)" }}>Pages</dt>
              <dd>{doc.page_count ?? "—"}</dd>
              <dt style={{ color: "var(--color-text-muted)" }}>Status</dt>
              <dd>{doc.status}</dd>
            </dl>
            {doc.error_message && (
              <div className="mb-4 rounded-md border px-3 py-2 text-xs" style={{ borderColor: "var(--color-danger)", color: "var(--color-danger)" }}>
                {doc.error_message}
              </div>
            )}
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--color-text-muted)" }}>
              Extracted passages ({doc.chunks.length})
            </h3>
            <div className="space-y-3">
              {doc.chunks.map((chunk, i) => {
                const isTarget = targetPage != null && chunk.page_number === targetPage && !doc.chunks.slice(0, i).some((c) => c.page_number === targetPage);
                return (
                  <div
                    key={chunk.chunk_index}
                    ref={isTarget ? highlightRef : undefined}
                    className="rounded-md border p-2.5 text-xs"
                    style={{
                      borderColor: isTarget ? "var(--color-primary)" : "var(--color-border)",
                      background: isTarget ? "color-mix(in srgb, var(--color-primary) 8%, transparent)" : undefined,
                    }}
                  >
                    <div className="mb-1 font-medium" style={{ color: "var(--color-primary)" }}>
                      {chunk.page_number ? `Page ${chunk.page_number}` : chunk.slide_number ? `Slide ${chunk.slide_number}` : "Document"}
                    </div>
                    <p style={{ color: "var(--color-text)" }}>
                      {chunk.text.slice(0, 300)}
                      {chunk.text.length > 300 ? "…" : ""}
                    </p>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
