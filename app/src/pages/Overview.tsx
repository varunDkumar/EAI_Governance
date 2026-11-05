import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError, type HealthResponse } from "../lib/api";
import type { OverviewData } from "../lib/types";

type BackendState = "checking" | "online" | "offline";

const RETRY_INTERVAL_MS = 2000;
const MAX_ATTEMPTS = 60; // ~2 minutes — generous for a cold sidecar start with a large corpus

export default function Overview() {
  const [state, setState] = useState<BackendState>("checking");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [data, setData] = useState<OverviewData | null>(null);
  const attemptsRef = useRef(0);

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;

    const attempt = () => {
      api
        .get<HealthResponse>("/health")
        .then((res) => {
          if (cancelled) return;
          setHealth(res);
          setState("online");
          return api.get<OverviewData>("/overview");
        })
        .then((res) => {
          if (!cancelled && res) setData(res);
        })
        .catch((err: unknown) => {
          if (cancelled) return;
          attemptsRef.current += 1;
          if (attemptsRef.current >= MAX_ATTEMPTS) {
            setState("offline");
            console.error(err instanceof ApiError ? err.message : err);
            return;
          }
          // The backend (especially a freshly-launched packaged app, which has
          // to unpack itself and load the full document/vector database) can
          // take a while to come up — keep retrying instead of giving up
          // after one failed check and leaving the UI stuck showing "offline"
          // even once the backend is actually ready.
          setState("checking");
          timer = window.setTimeout(attempt, RETRY_INTERVAL_MS);
        });
    };

    attempt();
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Overview</h1>
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          Snapshot of the repository, agents and governance state — all figures come from live
          application data.
        </p>
      </div>

      <div
        className="flex items-center gap-3 rounded-lg border px-4 py-3 text-sm"
        style={{ borderColor: "var(--color-border)", background: "var(--color-surface)" }}
      >
        <span
          className="h-2.5 w-2.5 rounded-full"
          style={{
            background:
              state === "online"
                ? "var(--color-success)"
                : state === "offline"
                  ? "var(--color-danger)"
                  : "var(--color-warning)",
          }}
        />
        {state === "checking" && attemptsRef.current === 0 && "Checking backend connection..."}
        {state === "checking" && attemptsRef.current > 0 && "Starting backend... this can take up to a minute on first launch."}
        {state === "online" && (
          <span>
            Backend online — version {health?.version}, LLM provider:{" "}
            <strong>{health?.llm_provider}</strong>
            {!health?.llm_configured && (
              <span style={{ color: "var(--color-warning)" }}> (not configured — chat answers disabled)</span>
            )}
          </span>
        )}
        {state === "offline" && "Backend unreachable after repeated attempts. Check the backend logs, or restart the app."}
      </div>

      {data && (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatCard label="Documents indexed" value={`${data.documents.indexed} / ${data.documents.total}`} to="/repository" />
            <StatCard label="Knowledge graph nodes" value={data.knowledge_graph.nodes} to="/graph" />
            <StatCard label="Relationships" value={data.knowledge_graph.edges} to="/graph" />
            <StatCard label="Active agents" value={`${data.agents.active} / ${data.agents.total}`} to="/agents" />
            <StatCard label="Memories stored" value={data.memories_stored} to="/memory" />
            <StatCard
              label="Pending approvals"
              value={data.pending_approvals}
              to="/approvals"
              accent={data.pending_approvals > 0 ? "var(--color-warning)" : undefined}
            />
          </div>

          <div className="rounded-lg border" style={{ borderColor: "var(--color-border)", background: "var(--color-surface)" }}>
            <div className="flex items-center justify-between border-b p-3" style={{ borderColor: "var(--color-border)" }}>
              <h2 className="text-sm font-semibold">Recent governance activity</h2>
              <Link to="/audit" className="text-xs" style={{ color: "var(--color-primary)" }}>
                View full audit log →
              </Link>
            </div>
            <div className="divide-y text-sm" style={{ borderColor: "var(--color-border)" }}>
              {data.recent_events.length === 0 && (
                <div className="p-3 text-xs" style={{ color: "var(--color-text-muted)" }}>
                  No governed events yet.
                </div>
              )}
              {data.recent_events.map((e) => (
                <div key={e.id} className="flex items-center justify-between gap-3 p-3">
                  <div>
                    <strong>{e.agent_name}</strong> — {e.event_type.replaceAll("_", " ")}
                    <div className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                      {e.reason}
                    </div>
                  </div>
                  {e.decision && <DecisionPill decision={e.decision} />}
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function StatCard({ label, value, to, accent }: { label: string; value: string | number; to: string; accent?: string }) {
  return (
    <Link
      to={to}
      className="rounded-lg border p-3 transition-colors hover:border-[var(--color-primary)]"
      style={{ borderColor: "var(--color-border)", background: "var(--color-surface)" }}
    >
      <div className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        {label}
      </div>
      <div className="text-xl font-semibold" style={{ color: accent }}>
        {value}
      </div>
    </Link>
  );
}

function DecisionPill({ decision }: { decision: string }) {
  const color = decision === "ALLOW" ? "var(--color-success)" : decision === "DENY" ? "var(--color-danger)" : "var(--color-warning)";
  return (
    <span className="shrink-0 rounded-full border px-2 py-0.5 text-[11px] font-medium" style={{ borderColor: color, color }}>
      {decision}
    </span>
  );
}
