import { useCallback, useState } from "react";
import { api } from "../lib/api";
import { useRetryingEffect } from "../lib/useRetryingEffect";
import type { ApprovalView } from "../lib/types";

export default function ApprovalCentre() {
  const [status, setStatus] = useState("pending");
  const [approvals, setApprovals] = useState<ApprovalView[]>([]);
  const [selected, setSelected] = useState<ApprovalView | null>(null);

  const refresh = useCallback(() => {
    return api.get<{ approvals: ApprovalView[] }>(`/approvals?status=${status}`).then((res) => setApprovals(res.approvals));
  }, [status]);

  useRetryingEffect(refresh, [refresh]);

  async function decide(id: string, decision: "approve" | "reject") {
    await api.post(`/approvals/${id}/decide`, { decision });
    setSelected(null);
    refresh();
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold">Approval Centre</h1>
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          Sensitive agent actions wait here for a human decision before they take effect.
        </p>
      </div>

      <div className="flex gap-2">
        {["pending", "approved", "rejected"].map((s) => (
          <button
            key={s}
            onClick={() => setStatus(s)}
            className="rounded-md border px-3 py-1.5 text-sm font-medium capitalize"
            style={{
              borderColor: status === s ? "var(--color-primary)" : "var(--color-border)",
              color: status === s ? "var(--color-primary)" : "var(--color-text)",
            }}
          >
            {s}
          </button>
        ))}
      </div>

      <div className="space-y-2">
        {approvals.length === 0 && (
          <div className="py-12 text-center text-sm" style={{ color: "var(--color-text-muted)" }}>
            No {status} approval requests.
          </div>
        )}
        {approvals.map((a) => (
          <div
            key={a.id}
            className="rounded-lg border p-3"
            style={{ borderColor: "var(--color-border)", background: "var(--color-surface)" }}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-sm">
                  <strong>{a.agent_name}</strong> requested <code className="text-xs">{a.action}</code>
                </div>
                <p className="mt-1 text-xs" style={{ color: "var(--color-text-muted)" }}>
                  {a.reason}
                </p>
                {a.policy_id && (
                  <p className="mt-1 text-[11px]" style={{ color: "var(--color-text-muted)" }}>
                    Policy: {a.policy_id}
                  </p>
                )}
              </div>
              {a.status === "pending" ? (
                <div className="flex shrink-0 gap-1.5">
                  <button
                    className="rounded-md px-3 py-1.5 text-xs font-medium text-white"
                    style={{ background: "var(--color-success)" }}
                    onClick={() => decide(a.id, "approve")}
                  >
                    Approve
                  </button>
                  <button
                    className="rounded-md border px-3 py-1.5 text-xs font-medium"
                    style={{ borderColor: "var(--color-danger)", color: "var(--color-danger)" }}
                    onClick={() => decide(a.id, "reject")}
                  >
                    Reject
                  </button>
                  <button
                    className="rounded-md border px-3 py-1.5 text-xs font-medium"
                    style={{ borderColor: "var(--color-border)" }}
                    onClick={() => setSelected(a)}
                  >
                    Details
                  </button>
                </div>
              ) : (
                <span
                  className="shrink-0 rounded-full border px-2 py-0.5 text-[11px] font-medium capitalize"
                  style={{
                    borderColor: a.status === "approved" ? "var(--color-success)" : "var(--color-danger)",
                    color: a.status === "approved" ? "var(--color-success)" : "var(--color-danger)",
                  }}
                >
                  {a.status}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>

      {selected && (
        <div className="fixed inset-0 z-20 flex items-center justify-center bg-black/30" onClick={() => setSelected(null)}>
          <div
            className="w-full max-w-md rounded-lg border p-5"
            style={{ borderColor: "var(--color-border)", background: "var(--color-surface)" }}
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="text-base font-semibold">Approval request</h2>
            <dl className="mt-3 grid grid-cols-2 gap-y-1.5 text-xs">
              <dt style={{ color: "var(--color-text-muted)" }}>Agent</dt>
              <dd>{selected.agent_name}</dd>
              <dt style={{ color: "var(--color-text-muted)" }}>Action</dt>
              <dd>{selected.action}</dd>
              <dt style={{ color: "var(--color-text-muted)" }}>Resource type</dt>
              <dd>{selected.resource_type}</dd>
              <dt style={{ color: "var(--color-text-muted)" }}>Policy</dt>
              <dd>{selected.policy_id ?? "—"}</dd>
            </dl>
            <p className="mt-3 text-sm">{selected.reason}</p>
            {selected.resource_preview && (
              <div className="mt-3 rounded-md border p-2.5 text-xs" style={{ borderColor: "var(--color-border)" }}>
                <div className="font-medium">{selected.resource_preview.title}</div>
                <div style={{ color: "var(--color-text-muted)" }}>{selected.resource_preview.description}</div>
              </div>
            )}
            {selected.status === "pending" && (
              <div className="mt-4 flex gap-2 border-t pt-3" style={{ borderColor: "var(--color-border)" }}>
                <button
                  className="flex-1 rounded-md px-3 py-1.5 text-sm font-medium text-white"
                  style={{ background: "var(--color-success)" }}
                  onClick={() => decide(selected.id, "approve")}
                >
                  Approve
                </button>
                <button
                  className="flex-1 rounded-md border px-3 py-1.5 text-sm font-medium"
                  style={{ borderColor: "var(--color-danger)", color: "var(--color-danger)" }}
                  onClick={() => decide(selected.id, "reject")}
                >
                  Reject
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
