import { useState } from "react";
import { useNavigate } from "react-router-dom";
import type { ChatMessage } from "../../lib/types";

export default function MessageBubble({ message }: { message: ChatMessage }) {
  const [showGovernance, setShowGovernance] = useState(false);
  const isUser = message.role === "user";
  const navigate = useNavigate();

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[75%] ${isUser ? "" : "w-full"}`}>
        <div
          className="rounded-lg px-3.5 py-2.5 text-sm whitespace-pre-wrap"
          style={{
            background: isUser ? "var(--color-primary)" : "var(--color-surface)",
            color: isUser ? "white" : "var(--color-text)",
            border: isUser ? "none" : "1px solid var(--color-border)",
          }}
        >
          {message.content}
        </div>

        {!isUser && message.citations?.length > 0 && (
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {message.citations.slice(0, 8).map((c, i) => (
              <button
                key={c.chunk_id + i}
                className="rounded-full border px-2 py-0.5 text-[11px] hover:bg-black/5"
                style={{ borderColor: "var(--color-border)", color: "var(--color-text-muted)" }}
                title={`${c.snippet}\n\nClick to open the source document`}
                onClick={() =>
                  navigate(`/repository?doc=${c.document_id}${c.page_number ? `&page=${c.page_number}` : ""}`)
                }
              >
                [{i + 1}] {c.title}
                {c.page_number ? ` p.${c.page_number}` : c.slide_number ? ` slide ${c.slide_number}` : ""}
              </button>
            ))}
          </div>
        )}

        {!isUser && message.memories_used?.length > 0 && (
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {message.memories_used.map((m) => (
              <span
                key={m.memory_id}
                className="rounded-full px-2 py-0.5 text-[11px] text-white"
                style={{ background: "var(--color-primary)" }}
                title={m.description}
              >
                ✦ remembered: {m.title}
              </span>
            ))}
          </div>
        )}

        {!isUser && message.governance_notes?.length > 0 && (
          <div className="mt-1.5">
            <button
              className="text-[11px] underline"
              style={{ color: "var(--color-warning)" }}
              onClick={() => setShowGovernance((s) => !s)}
            >
              {message.governance_notes.length} source{message.governance_notes.length === 1 ? "" : "s"} withheld by governance
            </button>
            {showGovernance && (
              <ul className="mt-1 space-y-0.5 text-[11px]" style={{ color: "var(--color-text-muted)" }}>
                {message.governance_notes.map((n, i) => (
                  <li key={i}>
                    <strong>{n.decision}</strong> {n.title ? `"${n.title}"` : ""} — {n.reason}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
