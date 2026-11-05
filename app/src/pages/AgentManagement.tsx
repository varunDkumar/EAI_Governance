import { useState } from "react";
import { api } from "../lib/api";
import { useRetryingEffect } from "../lib/useRetryingEffect";
import type { AgentView } from "../lib/types";

const STATUS_OPTIONS: AgentView["status"][] = ["active", "suspended", "deactivated"];

export default function AgentManagement() {
  const [agents, setAgents] = useState<AgentView[]>([]);

  function refresh() {
    return api.get<{ agents: AgentView[] }>("/agents").then((res) => setAgents(res.agents));
  }

  useRetryingEffect(refresh, []);

  async function setStatus(id: string, status: string) {
    await api.patch(`/agents/${id}/status`, { status });
    refresh();
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold">Agent Management</h1>
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          Every agent's identity, mandate, permissions and kill switch.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {agents.map((agent) => (
          <div key={agent.id} className="rounded-lg border p-4" style={{ borderColor: "var(--color-border)", background: "var(--color-surface)" }}>
            <div className="flex items-start justify-between">
              <div>
                <h2 className="text-base font-semibold">{agent.name}</h2>
                <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                  {agent.owner}
                </p>
              </div>
              <StatusPill status={agent.status} />
            </div>

            <p className="mt-2 text-sm">{agent.description}</p>

            <div className="mt-3">
              <h3 className="text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--color-text-muted)" }}>
                Mandate
              </h3>
              <p className="mt-1 text-xs">{agent.purpose}</p>
            </div>

            <div className="mt-3">
              <h3 className="text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--color-text-muted)" }}>
                Permissions
              </h3>
              <div className="mt-1 flex flex-wrap gap-1">
                {agent.permissions.map((p, i) => (
                  <span key={i} className="rounded-full border px-2 py-0.5 text-[11px]" style={{ borderColor: "var(--color-border)" }}>
                    {p.resource_type}: {p.resource_value} ({p.access_level})
                  </span>
                ))}
              </div>
            </div>

            <div className="mt-3">
              <h3 className="text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--color-text-muted)" }}>
                Restricted actions
              </h3>
              <ul className="mt-1 list-inside list-disc text-[11px]" style={{ color: "var(--color-text-muted)" }}>
                {agent.restricted_actions.map((r) => (
                  <li key={r}>{r.replaceAll("_", " ")}</li>
                ))}
              </ul>
            </div>

            <div className="mt-4 flex gap-1.5 border-t pt-3" style={{ borderColor: "var(--color-border)" }}>
              {STATUS_OPTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => setStatus(agent.id, s)}
                  disabled={agent.status === s}
                  className="flex-1 rounded-md border px-2 py-1 text-[11px] font-medium capitalize disabled:opacity-40"
                  style={{ borderColor: "var(--color-border)" }}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  const color = status === "active" ? "var(--color-success)" : status === "suspended" ? "var(--color-warning)" : "var(--color-danger)";
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px]" style={{ borderColor: color, color }}>
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: color }} />
      {status}
    </span>
  );
}
