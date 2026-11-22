import type { AgentView } from "../../lib/types";

const STATUS_COLOR: Record<string, string> = {
  active: "var(--color-success)",
  suspended: "var(--color-warning)",
  deactivated: "var(--color-danger)",
};

export default function AgentBadge({
  agent,
  compact = false,
  selected = false,
  onClick,
}: {
  agent: AgentView;
  compact?: boolean;
  selected?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="w-full rounded-lg border p-3 text-left transition-colors"
      style={{
        borderColor: selected ? "var(--color-primary)" : "var(--color-border)",
        background: selected ? "color-mix(in srgb, var(--color-primary) 8%, var(--color-surface))" : "var(--color-surface)",
      }}
    >
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold">{agent.name}</span>
        <span className="inline-flex items-center gap-1 text-xs" style={{ color: "var(--color-text-muted)" }}>
          <span className="h-1.5 w-1.5 rounded-full" style={{ background: STATUS_COLOR[agent.status] }} />
          {agent.status}
        </span>
      </div>
      {!compact && (
        <>
          <p className="mt-1 text-xs" style={{ color: "var(--color-text-muted)" }}>
            {agent.description}
          </p>
          <p className="mt-1 text-xs">
            Owner: <span style={{ color: "var(--color-text-muted)" }}>{agent.owner}</span>
          </p>
        </>
      )}
    </button>
  );
}
