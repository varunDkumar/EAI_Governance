import { useCallback, useState } from "react";
import { api } from "../lib/api";
import { useRetryingEffect } from "../lib/useRetryingEffect";
import type { AgentView, MemoryView } from "../lib/types";

const TYPE_COLOR: Record<string, string> = {
  knowledge: "var(--color-accent)",
  episodic: "var(--color-secondary)",
  user_context: "var(--color-primary)",
  decision: "var(--color-warning)",
};

export default function MemoryExplorer() {
  const [memories, setMemories] = useState<MemoryView[]>([]);
  const [agents, setAgents] = useState<AgentView[]>([]);
  const [memoryType, setMemoryType] = useState("");
  const [approvalStatus, setApprovalStatus] = useState("");
  const [selected, setSelected] = useState<MemoryView | null>(null);

  const refresh = useCallback(() => {
    const params = new URLSearchParams();
    if (memoryType) params.set("memory_type", memoryType);
    if (approvalStatus) params.set("approval_status", approvalStatus);
    return api.get<{ memories: MemoryView[] }>(`/memories?${params.toString()}`).then((res) => setMemories(res.memories));
  }, [memoryType, approvalStatus]);

  const loadAgents = useCallback(() => {
    return api.get<{ agents: AgentView[] }>("/agents").then((res) => setAgents(res.agents));
  }, []);

  useRetryingEffect(loadAgents, [loadAgents]);
  useRetryingEffect(refresh, [refresh]);

  async function approve(id: string) {
    await api.post(`/memories/${id}/approve`);
    refresh();
    setSelected(null);
  }

  async function reject(id: string) {
    await api.post(`/memories/${id}/reject`);
    refresh();
    setSelected(null);
  }

  const agentName = (id: string | null) => agents.find((a) => a.id === id)?.name ?? "—";

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold">Memory Explorer</h1>
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          Persistent memories agents have proposed from conversations — knowledge, episodic, learner context and decisions.
        </p>
      </div>

      <div className="flex gap-2">
        <select
          className="rounded-md border px-2 py-1.5 text-sm"
          style={{ borderColor: "var(--color-border)", background: "var(--color-surface)" }}
          value={memoryType}
          onChange={(e) => setMemoryType(e.target.value)}
        >
          <option value="">All types</option>
          <option value="knowledge">Knowledge</option>
          <option value="episodic">Episodic</option>
          <option value="user_context">User context</option>
          <option value="decision">Decision</option>
        </select>
        <select
          className="rounded-md border px-2 py-1.5 text-sm"
          style={{ borderColor: "var(--color-border)", background: "var(--color-surface)" }}
          value={approvalStatus}
          onChange={(e) => setApprovalStatus(e.target.value)}
        >
          <option value="">All statuses</option>
          <option value="pending">Pending approval</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
        </select>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {memories.length === 0 && (
          <div className="col-span-2 py-12 text-center text-sm" style={{ color: "var(--color-text-muted)" }}>
            No memories yet — have a conversation in the AI Workspace and the agent may propose one.
          </div>
        )}
        {memories.map((m) => (
          <button
            key={m.id}
            onClick={() => setSelected(m)}
            className="rounded-lg border p-3 text-left"
            style={{ borderColor: "var(--color-border)", background: "var(--color-surface)" }}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="rounded-full px-2 py-0.5 text-[11px] font-medium text-white" style={{ background: TYPE_COLOR[m.memory_type] }}>
                {m.memory_type.replaceAll("_", " ")}
              </span>
              <ApprovalPill status={m.approval_status} />
            </div>
            <h3 className="mt-2 text-sm font-semibold">{m.title}</h3>
            <p className="mt-1 line-clamp-2 text-xs" style={{ color: "var(--color-text-muted)" }}>
              {m.description}
            </p>
            <div className="mt-2 text-[11px]" style={{ color: "var(--color-text-muted)" }}>
              {agentName(m.agent_id)} · {m.topic ?? "no topic"} · confidence {Math.round(m.confidence * 100)}%
            </div>
          </button>
        ))}
      </div>

      {selected && (
        <div className="fixed inset-0 z-20 flex items-center justify-center bg-black/30" onClick={() => setSelected(null)}>
          <div
            className="w-full max-w-md rounded-lg border p-5"
            style={{ borderColor: "var(--color-border)", background: "var(--color-surface)" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="rounded-full px-2 py-0.5 text-[11px] font-medium text-white" style={{ background: TYPE_COLOR[selected.memory_type] }}>
                {selected.memory_type.replaceAll("_", " ")}
              </span>
              <ApprovalPill status={selected.approval_status} />
            </div>
            <h2 className="mt-2 text-base font-semibold">{selected.title}</h2>
            <p className="mt-1 text-sm">{selected.description}</p>
            <dl className="mt-3 grid grid-cols-2 gap-y-1 text-xs">
              <dt style={{ color: "var(--color-text-muted)" }}>Proposed by</dt>
              <dd>{agentName(selected.agent_id)}</dd>
              <dt style={{ color: "var(--color-text-muted)" }}>Topic</dt>
              <dd>{selected.topic ?? "—"}</dd>
              <dt style={{ color: "var(--color-text-muted)" }}>Confidence</dt>
              <dd>{Math.round(selected.confidence * 100)}%</dd>
              <dt style={{ color: "var(--color-text-muted)" }}>Source conversation</dt>
              <dd className="truncate">{selected.conversation_id ?? "—"}</dd>
            </dl>
            {selected.approval_status === "pending" && (
              <div className="mt-4 flex gap-2 border-t pt-3" style={{ borderColor: "var(--color-border)" }}>
                <button
                  className="flex-1 rounded-md px-3 py-1.5 text-sm font-medium text-white"
                  style={{ background: "var(--color-success)" }}
                  onClick={() => approve(selected.id)}
                >
                  Approve
                </button>
                <button
                  className="flex-1 rounded-md border px-3 py-1.5 text-sm font-medium"
                  style={{ borderColor: "var(--color-danger)", color: "var(--color-danger)" }}
                  onClick={() => reject(selected.id)}
                >
                  Reject
                </button>
              </div>
            )}
            <button className="mt-3 text-xs" style={{ color: "var(--color-text-muted)" }} onClick={() => setSelected(null)}>
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function ApprovalPill({ status }: { status: string }) {
  const color = status === "approved" ? "var(--color-success)" : status === "rejected" ? "var(--color-danger)" : "var(--color-warning)";
  return (
    <span className="rounded-full border px-2 py-0.5 text-[11px]" style={{ borderColor: color, color }}>
      {status}
    </span>
  );
}
