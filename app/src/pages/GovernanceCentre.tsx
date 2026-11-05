import { useCallback, useState } from "react";
import { api } from "../lib/api";
import { useRetryingEffect } from "../lib/useRetryingEffect";

interface Policy {
  id: string;
  name: string;
  resource_type: string;
  effect: string;
  reason: string;
  priority: number;
}

interface DenialEvent {
  id: string;
  timestamp: string | null;
  agent_name: string;
  event_type: string;
  decision: string;
  reason: string | null;
  policy_evaluated: string | null;
}

interface AgentActivity {
  agent_id: string;
  agent_name: string;
  status: string;
  permission_count: number;
  allow_count: number;
  deny_count: number;
  require_approval_count: number;
}

interface Overview {
  agents_by_status: Record<string, number>;
  decision_counts: Record<string, number>;
  pending_approvals: number;
  agent_activity: AgentActivity[];
  recent_denials: DenialEvent[];
}

export default function GovernanceCentre() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [policies, setPolicies] = useState<Policy[]>([]);

  const refresh = useCallback(() => {
    return Promise.all([
      api.get<Overview>("/governance/overview").then(setOverview),
      api.get<{ policies: Policy[] }>("/governance/policies").then((res) => setPolicies(res.policies)),
    ]);
  }, []);

  useRetryingEffect(refresh, [refresh]);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold">Governance Centre</h1>
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          Backend-enforced access decisions — every agent action is checked here before it happens.
        </p>
      </div>

      <div className="grid grid-cols-5 gap-3">
        <Stat label="Active agents" value={overview?.agents_by_status.active ?? "—"} color="var(--color-success)" />
        <Stat label="Suspended" value={overview?.agents_by_status.suspended ?? "—"} color="var(--color-warning)" />
        <Stat label="ALLOW decisions" value={overview?.decision_counts.ALLOW ?? 0} />
        <Stat label="DENY decisions" value={overview?.decision_counts.DENY ?? 0} color="var(--color-danger)" />
        <Stat label="Pending approvals" value={overview?.pending_approvals ?? 0} color={overview && overview.pending_approvals > 0 ? "var(--color-warning)" : undefined} />
      </div>

      <div className="rounded-lg border" style={{ borderColor: "var(--color-border)", background: "var(--color-surface)" }}>
        <h2 className="border-b p-3 text-sm font-semibold" style={{ borderColor: "var(--color-border)" }}>
          Agent-specific activity &amp; permission coverage
        </h2>
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b text-xs uppercase tracking-wide" style={{ borderColor: "var(--color-border)", color: "var(--color-text-muted)" }}>
              <th className="px-3 py-2 font-medium">Agent</th>
              <th className="px-3 py-2 font-medium">Status</th>
              <th className="px-3 py-2 font-medium">Permissions</th>
              <th className="px-3 py-2 font-medium">Allowed</th>
              <th className="px-3 py-2 font-medium">Denied</th>
              <th className="px-3 py-2 font-medium">Approval required</th>
            </tr>
          </thead>
          <tbody>
            {overview?.agent_activity.map((a) => (
              <tr key={a.agent_id} className="border-b" style={{ borderColor: "var(--color-border)" }}>
                <td className="px-3 py-2 font-medium">{a.agent_name}</td>
                <td className="px-3 py-2 capitalize" style={{ color: a.status === "active" ? "var(--color-success)" : "var(--color-warning)" }}>
                  {a.status}
                </td>
                <td className="px-3 py-2">{a.permission_count}</td>
                <td className="px-3 py-2">{a.allow_count}</td>
                <td className="px-3 py-2">{a.deny_count}</td>
                <td className="px-3 py-2">{a.require_approval_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="rounded-lg border" style={{ borderColor: "var(--color-border)", background: "var(--color-surface)" }}>
        <h2 className="border-b p-3 text-sm font-semibold" style={{ borderColor: "var(--color-border)" }}>
          Active policies
        </h2>
        <div className="divide-y" style={{ borderColor: "var(--color-border)" }}>
          {policies.map((p) => (
            <div key={p.id} className="flex items-center justify-between gap-3 p-3 text-sm">
              <div>
                <div className="font-medium">{p.name}</div>
                <div className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                  {p.reason}
                </div>
              </div>
              <EffectPill effect={p.effect} />
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-lg border" style={{ borderColor: "var(--color-border)", background: "var(--color-surface)" }}>
        <h2 className="border-b p-3 text-sm font-semibold" style={{ borderColor: "var(--color-border)" }}>
          Recent denied / approval-required requests
        </h2>
        <div className="divide-y text-sm" style={{ borderColor: "var(--color-border)" }}>
          {overview?.recent_denials.length === 0 && (
            <div className="p-3 text-xs" style={{ color: "var(--color-text-muted)" }}>
              No denials recorded yet.
            </div>
          )}
          {overview?.recent_denials.map((e) => (
            <div key={e.id} className="flex items-center justify-between gap-3 p-3">
              <div>
                <div>
                  <strong>{e.agent_name}</strong> — {e.event_type.replaceAll("_", " ")}
                </div>
                <div className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                  {e.reason}
                </div>
              </div>
              <EffectPill effect={e.decision} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <div className="rounded-lg border p-3" style={{ borderColor: "var(--color-border)", background: "var(--color-surface)" }}>
      <div className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        {label}
      </div>
      <div className="text-xl font-semibold" style={{ color }}>
        {value}
      </div>
    </div>
  );
}

function EffectPill({ effect }: { effect: string }) {
  const color = effect === "ALLOW" ? "var(--color-success)" : effect === "DENY" ? "var(--color-danger)" : "var(--color-warning)";
  return (
    <span className="shrink-0 rounded-full border px-2 py-0.5 text-[11px] font-medium" style={{ borderColor: color, color }}>
      {effect}
    </span>
  );
}
