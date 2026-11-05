import { useCallback, useState } from "react";
import { api } from "../lib/api";
import { useRetryingEffect } from "../lib/useRetryingEffect";
import type { AuditEventView } from "../lib/types";

const API_BASE = "http://127.0.0.1:8756";

export default function AuditLog() {
  const [events, setEvents] = useState<AuditEventView[]>([]);
  const [eventType, setEventType] = useState("");
  const [decision, setDecision] = useState("");
  const [verifyResult, setVerifyResult] = useState<{ intact: boolean; note: string } | null>(null);

  const refresh = useCallback(() => {
    const params = new URLSearchParams();
    if (eventType) params.set("event_type", eventType);
    if (decision) params.set("decision", decision);
    return api.get<{ events: AuditEventView[] }>(`/audit/events?${params.toString()}`).then((res) => setEvents(res.events));
  }, [eventType, decision]);

  useRetryingEffect(refresh, [refresh]);

  async function verify() {
    const res = await api.get<{ intact: boolean; note: string }>("/audit/verify");
    setVerifyResult(res);
  }

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold">Audit Log</h1>
          <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
            Every governed action, append-only and hash-chained.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            className="rounded-md border px-3 py-1.5 text-xs font-medium"
            style={{ borderColor: "var(--color-border)" }}
            onClick={verify}
          >
            Verify chain integrity
          </button>
          <a
            className="rounded-md border px-3 py-1.5 text-xs font-medium"
            style={{ borderColor: "var(--color-border)" }}
            href={`${API_BASE}/audit/export?format=csv`}
          >
            Export CSV
          </a>
          <a
            className="rounded-md border px-3 py-1.5 text-xs font-medium"
            style={{ borderColor: "var(--color-border)" }}
            href={`${API_BASE}/audit/export?format=json`}
          >
            Export JSON
          </a>
        </div>
      </div>

      {verifyResult && (
        <div
          className="rounded-md border px-3 py-2 text-xs"
          style={{
            borderColor: verifyResult.intact ? "var(--color-success)" : "var(--color-danger)",
            color: verifyResult.intact ? "var(--color-success)" : "var(--color-danger)",
          }}
        >
          {verifyResult.intact ? "✓ Chain intact — " : "✗ Chain broken — "}
          {verifyResult.note}
        </div>
      )}

      <div className="flex gap-2">
        <select
          className="rounded-md border px-2 py-1.5 text-sm"
          style={{ borderColor: "var(--color-border)", background: "var(--color-surface)" }}
          value={eventType}
          onChange={(e) => setEventType(e.target.value)}
        >
          <option value="">All event types</option>
          <option value="app_startup">App startup</option>
          <option value="app_shutdown">App shutdown</option>
          <option value="document_access">Document access</option>
          <option value="memory_access">Memory access</option>
          <option value="memory_write">Memory write</option>
          <option value="chat_blocked">Chat blocked</option>
          <option value="agent_status_change">Agent status change</option>
          <option value="human_approval">Human approval</option>
          <option value="human_rejection">Human rejection</option>
        </select>
        <select
          className="rounded-md border px-2 py-1.5 text-sm"
          style={{ borderColor: "var(--color-border)", background: "var(--color-surface)" }}
          value={decision}
          onChange={(e) => setDecision(e.target.value)}
        >
          <option value="">All decisions</option>
          <option value="ALLOW">ALLOW</option>
          <option value="DENY">DENY</option>
          <option value="REQUIRE_APPROVAL">REQUIRE_APPROVAL</option>
        </select>
      </div>

      <div className="overflow-x-auto rounded-lg border" style={{ borderColor: "var(--color-border)", background: "var(--color-surface)" }}>
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b uppercase tracking-wide" style={{ borderColor: "var(--color-border)", color: "var(--color-text-muted)" }}>
              <th className="px-3 py-2 font-medium">Time</th>
              <th className="px-3 py-2 font-medium">Agent</th>
              <th className="px-3 py-2 font-medium">Event</th>
              <th className="px-3 py-2 font-medium">Decision</th>
              <th className="px-3 py-2 font-medium">Reason</th>
            </tr>
          </thead>
          <tbody>
            {events.map((e) => (
              <tr key={e.id} className="border-b" style={{ borderColor: "var(--color-border)" }}>
                <td className="whitespace-nowrap px-3 py-2" style={{ color: "var(--color-text-muted)" }}>
                  {e.timestamp ? new Date(e.timestamp).toLocaleString() : "—"}
                </td>
                <td className="px-3 py-2">{e.agent_name}</td>
                <td className="px-3 py-2">{e.event_type.replaceAll("_", " ")}</td>
                <td className="px-3 py-2">
                  <DecisionPill decision={e.decision} />
                </td>
                <td className="max-w-md px-3 py-2" style={{ color: "var(--color-text-muted)" }}>
                  {e.reason}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {events.length === 0 && (
          <div className="py-12 text-center text-sm" style={{ color: "var(--color-text-muted)" }}>
            No events match the current filters.
          </div>
        )}
      </div>
    </div>
  );
}

function DecisionPill({ decision }: { decision: string | null }) {
  if (!decision) return <span style={{ color: "var(--color-text-muted)" }}>—</span>;
  const color = decision === "ALLOW" ? "var(--color-success)" : decision === "DENY" ? "var(--color-danger)" : "var(--color-warning)";
  return (
    <span className="rounded-full border px-2 py-0.5 text-[11px] font-medium" style={{ borderColor: color, color }}>
      {decision}
    </span>
  );
}
