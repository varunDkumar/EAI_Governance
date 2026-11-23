import { useCallback, useState, type ReactNode } from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useRetryingEffect } from "../lib/useRetryingEffect";

// --- Types matching backend/api/simulator.py --------------------------------

type Hospital = { name: string; departments: string[] };

type Patient = {
  id: string;
  patient_code: string;
  name: string;
  age: number;
  gender: string;
  blood_group: string;
  registered_date: string;
  medical_history: string[];
  medications: string[];
};

type PolicySet = { department: string[]; task: string[]; patient: string[] };

type Agent = {
  id: string;
  name: string;
  cof_id: string;
  substrate_anchor: string;
  policy_set: PolicySet;
  cne_id: string;
  status: string;
  narrative_seq: number;
  last_activity_at: string;
  created_at: string;
  responsibility: string | null;
  substrate_label: string | null;
  runtime: string | null;
};

type Metrics = {
  total_ai_actions: number;
  actions_with_verifiable_identity: number;
  outputs_with_complete_provenance: number;
  human_consumption_events: number;
  coherence_checks_coherent: number;
  coherence_checks_flagged: number;
  narrative_frames_linked: number;
  duplicate_identity_attempts_detected: number;
  patient_context_mismatches_detected: number;
  unresolved_governance_gaps: number;
};

type HospitalOverview = { hospital: Hospital; patient: Patient; agents: Agent[]; metrics: Metrics };

type ActionRow = {
  id: string;
  encounter_id: string;
  agent_id: string;
  scenario: "without_cne" | "with_cne";
  stage: string;
  sequence: number;
  input_refs: string[];
  output_text: string;
  consumed_by: string | null;
  status: string;
  cne_id_snapshot: string | null;
  gnf_frame_id: string | null;
  rbr_proof_id: string | null;
  created_at: string;
  agent_name: string | null;
};

type Encounter = {
  id: string;
  episode_id: string;
  patient_id: string;
  encounter_code: string;
  visit_date: string;
  department: string;
  doctor_name: string;
  chief_complaint: string;
  sequence: number;
  actions: { without_cne: ActionRow[]; with_cne: ActionRow[] };
};

type Episode = { id: string; patient_id: string; name: string; status: string; opened_at: string; closed_at: string | null; encounters: Encounter[] };

type PatientJourney = { patient: Patient; episodes: Episode[] };

type DimensionRow = { dimension: string; without_cne: string; with_cne: string };
type ComparisonData = { dimensions: DimensionRow[] };

type GovEvent = { id: string; event_type: string; scenario: string; encounter_id: string | null; agent_id: string | null; severity: string; detail: Record<string, unknown>; created_at: string };
type ChainStatus = { agent_id: string; agent_name: string; cof_id: string; frame_count: number; verification: { valid: boolean; failed_index: number | null; failed_frame: string | null } };
type AuditData = { chains: ChainStatus[]; events: GovEvent[] };

type TrailEntry = { action: ActionRow; agent: Agent | null; encounter: Encounter | null; gnf_frame?: Record<string, unknown>; rbr_proof?: Record<string, unknown>; approvals?: Record<string, unknown>[] };
type ReconstructResult = { trail: TrailEntry[] };

const NAV = [
  { path: "overview", label: "Hospital Overview" },
  { path: "journey", label: "Patient Journey" },
  { path: "agents", label: "AI Agent Registry" },
  { path: "without-cne", label: "Without CNE" },
  { path: "with-cne", label: "With CNE" },
  { path: "comparison", label: "Governance Comparison" },
  { path: "audit", label: "Audit & Accountability" },
];

const WITHOUT_CNE_LIMITATIONS = [
  "Agent identity cannot be persistently, verifiably established for this instance.",
  "Provenance cannot be reliably reconstructed: which exact agent, which evidence, which consumer.",
  "No coherence mechanism links this evidence to a verifiable belief revision.",
  "No continuity guarantee prevents this output from being retrieved in the wrong clinical context.",
  "No exclusivity guarantee rules out a duplicate agent instance having produced a competing output.",
  "An auditor cannot reconstruct a complete, verifiable accountability chain for this action.",
];

function fmtDate(value?: string | null): string {
  if (!value) return "—";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value : d.toLocaleString();
}

function shortHash(value?: string | null, length = 16): string {
  if (!value) return "—";
  return value.length > length ? `${value.slice(0, length)}…` : value;
}

function severityColor(severity: string): string {
  if (severity === "blocked") return "var(--color-danger)";
  if (severity === "warning") return "var(--color-warning)";
  return "var(--sim-teal)";
}

function statusColor(status: string): string {
  if (status === "LIVE" || status === "accepted" || status === "coherent") return "var(--color-success)";
  if (status === "REJECTED" || status === "rejected" || status === "blocked" || status === "flagged") return "var(--color-danger)";
  if (status === "SUSPENDED" || status === "modified" || status === "PENDING") return "var(--color-warning)";
  return "var(--color-text-muted)";
}

function readableStage(stage: string): string {
  return stage.replaceAll("_", " ");
}

function readableEventType(type: string): string {
  return type.replaceAll("_", " ");
}

// --- Shared layout -----------------------------------------------------------

function Pill({ children, color }: { children: ReactNode; color: string }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium" style={{ borderColor: color, color }}>
      {children}
    </span>
  );
}

function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-xl border bg-white p-5 ${className}`} style={{ borderColor: "var(--color-border)" }}>
      {children}
    </div>
  );
}

function SectionTitle({ children, caption }: { children: ReactNode; caption?: string }) {
  return (
    <div className="mb-3">
      <h2 className="text-sm font-semibold uppercase tracking-wide" style={{ color: "var(--sim-navy)" }}>{children}</h2>
      {caption && <p className="mt-0.5 text-xs" style={{ color: "var(--color-text-muted)" }}>{caption}</p>}
    </div>
  );
}

function Header() {
  return (
    <header className="flex items-center justify-between border-b bg-white px-7 py-4" style={{ borderColor: "var(--color-border)" }}>
      <div>
        <Link to="/" className="text-xs font-semibold" style={{ color: "var(--sim-teal)" }}>← All products</Link>
        <div className="mt-1 flex items-center gap-2 text-lg font-semibold" style={{ color: "var(--sim-navy)" }}>
          Governance Simulator
          <span className="rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-white" style={{ background: "var(--sim-teal)" }}>CNE protocol</span>
        </div>
      </div>
      <div className="text-right">
        <div className="text-xs font-medium">Apollo Multispeciality Hospital · fictional</div>
        <div className="mt-1 text-[11px]" style={{ color: "var(--color-text-muted)" }}>Educational simulation using synthetic data · not for clinical use</div>
      </div>
    </header>
  );
}

function Shell({ page, children }: { page: string; children: ReactNode }) {
  return (
    <div className="sim-theme flex h-screen w-screen flex-col overflow-hidden" style={{ background: "var(--sim-bg)" }}>
      <Header />
      <div className="flex min-h-0 flex-1">
        <aside className="flex w-60 shrink-0 flex-col border-r bg-white px-3 py-5" style={{ borderColor: "var(--color-border)" }}>
          <div className="px-3 pb-4 text-[10px] font-semibold uppercase tracking-[.18em]" style={{ color: "var(--color-text-muted)" }}>SIMULATOR</div>
          <nav className="grid gap-1">
            {NAV.map((n) => (
              <NavLink
                key={n.path}
                to={`/governance-simulator/${n.path}`}
                className="rounded-lg px-3 py-2 text-sm font-medium"
                style={{
                  background: page === n.path ? "var(--sim-teal-light)" : "transparent",
                  color: page === n.path ? "var(--sim-navy)" : "var(--color-text-muted)",
                }}
              >
                {n.label}
              </NavLink>
            ))}
          </nav>
        </aside>
        <main className="min-h-0 flex-1 overflow-y-auto px-8 py-6">{children}</main>
      </div>
    </div>
  );
}

// --- Data loading --------------------------------------------------------------

function useSimulatorData() {
  const [overview, setOverview] = useState<HospitalOverview | null>(null);
  const [journey, setJourney] = useState<PatientJourney | null>(null);
  const [agents, setAgents] = useState<Agent[] | null>(null);
  const [comparisonData, setComparisonData] = useState<ComparisonData | null>(null);
  const [auditData, setAuditData] = useState<AuditData | null>(null);

  const refresh = useCallback(() => {
    return Promise.all([
      api.get<HospitalOverview>("/simulator/hospital-overview").then(setOverview),
      api.get<PatientJourney>("/simulator/patient-journey").then(setJourney),
      api.get<Agent[]>("/simulator/agents").then(setAgents),
      api.get<ComparisonData>("/simulator/comparison").then(setComparisonData),
      api.get<AuditData>("/simulator/audit").then(setAuditData),
    ]);
  }, []);

  useRetryingEffect(refresh, [refresh]);

  return { overview, journey, agents, comparisonData, auditData, refresh };
}

// --- Screen: Hospital Overview --------------------------------------------------

function HospitalOverviewScreen({ overview }: { overview: HospitalOverview | null }) {
  if (!overview) return <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>Connecting to simulator…</p>;
  const { hospital, patient, agents, metrics } = overview;

  const metricTiles: [string, number][] = [
    ["Total AI actions", metrics.total_ai_actions],
    ["Actions with verifiable identity", metrics.actions_with_verifiable_identity],
    ["Outputs with complete provenance", metrics.outputs_with_complete_provenance],
    ["Human consumption events", metrics.human_consumption_events],
    ["Coherence checks — coherent", metrics.coherence_checks_coherent],
    ["Coherence checks — flagged", metrics.coherence_checks_flagged],
    ["Narrative frames linked", metrics.narrative_frames_linked],
    ["Duplicate identities detected", metrics.duplicate_identity_attempts_detected],
    ["Context mismatches detected", metrics.patient_context_mismatches_detected],
    ["Unresolved governance gaps", metrics.unresolved_governance_gaps],
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold" style={{ color: "var(--sim-navy)" }}>{hospital.name}</h1>
        <p className="mt-1 text-sm" style={{ color: "var(--color-text-muted)" }}>A fictional multispeciality hospital running AI agents across departments, demonstrated with and without the CNE protocol.</p>
        <div className="mt-3 flex flex-wrap gap-1.5">
          {hospital.departments.map((d) => (
            <span key={d} className="rounded-full border px-2.5 py-1 text-xs" style={{ borderColor: "var(--color-border)" }}>{d}</span>
          ))}
        </div>
      </div>

      <Card>
        <SectionTitle>Patient</SectionTitle>
        <div className="flex flex-wrap items-baseline gap-x-6 gap-y-1">
          <span className="text-base font-semibold">{patient.name}</span>
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>{patient.patient_code}</span>
          <span className="text-xs">{patient.age} / {patient.gender} / {patient.blood_group}</span>
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>Registered {patient.registered_date}</span>
        </div>
        <div className="mt-3 flex flex-wrap gap-4 text-xs">
          <div><span style={{ color: "var(--color-text-muted)" }}>Medical history: </span>{patient.medical_history.join(", ") || "None recorded"}</div>
          <div><span style={{ color: "var(--color-text-muted)" }}>Medications: </span>{patient.medications.join(", ") || "None recorded"}</div>
        </div>
      </Card>

      <div>
        <SectionTitle caption="8 AI agents, each with its own CNE identity. See the Agent Registry for full identity documents.">AI agents</SectionTitle>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {agents.map((a) => (
            <Card key={a.id} className="!p-3">
              <div className="flex items-start justify-between gap-2">
                <span className="text-xs font-semibold">{a.name}</span>
                <Pill color={statusColor(a.status)}>{a.status}</Pill>
              </div>
              <div className="mt-1 text-[11px]" style={{ color: "var(--color-text-muted)" }}>{a.cof_id}</div>
              <div className="mt-1 truncate text-[10px]" style={{ color: "var(--color-text-muted)" }} title={a.cne_id}>CNE-ID {shortHash(a.cne_id, 20)}</div>
            </Card>
          ))}
        </div>
      </div>

      <div>
        <SectionTitle caption="Calculated live from the simulated actions, events and proofs below — not fixed numbers.">Live metrics</SectionTitle>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
          {metricTiles.map(([label, value]) => (
            <Card key={label} className="!p-3">
              <div className="text-xl font-semibold" style={{ color: "var(--sim-navy)" }}>{value}</div>
              <div className="mt-1 text-[11px]" style={{ color: "var(--color-text-muted)" }}>{label}</div>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}

// --- Action detail (shared by Patient Journey / Without / With CNE) ------------

function ActionDetail({ action, open, onToggle, scenario, onReconstruct }: { action: ActionRow; open: boolean; onToggle: () => void; scenario: "without_cne" | "with_cne"; onReconstruct: (actionId: string) => void }) {
  return (
    <div className="rounded-lg border" style={{ borderColor: "var(--color-border)" }}>
      <button className="flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left" onClick={onToggle}>
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold capitalize">{readableStage(action.stage)}</span>
            <span className="text-[11px]" style={{ color: "var(--color-text-muted)" }}>{action.agent_name}</span>
            <Pill color={statusColor(action.status)}>{action.status}</Pill>
          </div>
          <p className="mt-1 truncate text-xs" style={{ color: "var(--color-text-muted)" }}>{action.output_text}</p>
        </div>
        <span className="shrink-0 text-xs" style={{ color: "var(--color-text-muted)" }}>{open ? "Hide" : "Open"}</span>
      </button>
      {open && (
        <div className="space-y-2 border-t px-3 py-3 text-xs" style={{ borderColor: "var(--color-border)" }}>
          <p className="leading-5">{action.output_text}</p>
          <div><span style={{ color: "var(--color-text-muted)" }}>Input references: </span>{action.input_refs.join(", ")}</div>
          <div><span style={{ color: "var(--color-text-muted)" }}>Consumed by: </span>{action.consumed_by ?? "Not yet consumed"}</div>
          {scenario === "with_cne" ? (
            <>
              <div><span style={{ color: "var(--color-text-muted)" }}>CNE-ID snapshot: </span><span title={action.cne_id_snapshot ?? ""}>{shortHash(action.cne_id_snapshot, 24)}</span></div>
              <div><span style={{ color: "var(--color-text-muted)" }}>GNF frame: </span>{action.gnf_frame_id ? "Linked" : "—"}</div>
              <div><span style={{ color: "var(--color-text-muted)" }}>RbR proof: </span>{action.rbr_proof_id ? "Recorded" : "Not applicable to this stage"}</div>
              <button className="mt-1 rounded-md border px-2.5 py-1 text-[11px]" style={{ borderColor: "var(--sim-teal)", color: "var(--sim-teal)" }} onClick={() => onReconstruct(action.id)}>Reconstruct full decision trail →</button>
            </>
          ) : (
            <p className="rounded-md border px-2 py-1.5" style={{ borderColor: "var(--color-warning)", color: "var(--color-warning)" }}>No verifiable agent identity, provenance link or narrative record exists for this action.</p>
          )}
        </div>
      )}
    </div>
  );
}

function EncounterCard({ encounter, scenario, openAction, setOpenAction, onReconstruct }: { encounter: Encounter; scenario: "without_cne" | "with_cne"; openAction: string | null; setOpenAction: (id: string | null) => void; onReconstruct: (actionId: string) => void }) {
  const actions = encounter.actions[scenario];
  return (
    <Card>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <span className="text-sm font-semibold">{encounter.encounter_code}</span>
          <span className="ml-2 text-xs" style={{ color: "var(--color-text-muted)" }}>{encounter.visit_date} · {encounter.department} · {encounter.doctor_name}</span>
        </div>
      </div>
      <p className="mt-1 text-xs" style={{ color: "var(--color-text-muted)" }}>{encounter.chief_complaint}</p>
      <div className="mt-3 space-y-1.5">
        {actions.map((a) => (
          <ActionDetail key={a.id} action={a} scenario={scenario} open={openAction === a.id} onToggle={() => setOpenAction(openAction === a.id ? null : a.id)} onReconstruct={onReconstruct} />
        ))}
      </div>
    </Card>
  );
}

// --- Screen: Patient Journey -----------------------------------------------------

function PatientJourneyScreen({ journey, onReconstruct }: { journey: PatientJourney | null; onReconstruct: (actionId: string) => void }) {
  const [scenario, setScenario] = useState<"without_cne" | "with_cne">("with_cne");
  const [openAction, setOpenAction] = useState<string | null>(null);
  if (!journey) return <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>Connecting to simulator…</p>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold" style={{ color: "var(--sim-navy)" }}>{journey.patient.name}'s journey</h1>
          <p className="mt-1 text-sm" style={{ color: "var(--color-text-muted)" }}>{journey.patient.patient_code} · {journey.episodes.reduce((n, e) => n + e.encounters.length, 0)} visits across {journey.episodes.length} episodes</p>
        </div>
        <div className="inline-flex rounded-lg border p-0.5" style={{ borderColor: "var(--color-border)" }}>
          {(["without_cne", "with_cne"] as const).map((s) => (
            <button key={s} onClick={() => setScenario(s)} className="rounded-md px-3 py-1.5 text-xs font-medium" style={{ background: scenario === s ? "var(--sim-teal-light)" : "transparent", color: scenario === s ? "var(--sim-navy)" : "var(--color-text-muted)" }}>
              {s === "without_cne" ? "Without CNE" : "With CNE"}
            </button>
          ))}
        </div>
      </div>

      {journey.episodes.map((episode) => (
        <div key={episode.id}>
          <div className="mb-2 flex items-center gap-2">
            <h2 className="text-sm font-semibold">{episode.name}</h2>
            <Pill color={episode.status === "closed" ? "var(--color-text-muted)" : "var(--color-success)"}>{episode.status}</Pill>
            <span className="text-[11px]" style={{ color: "var(--color-text-muted)" }}>{episode.opened_at}{episode.closed_at ? ` – ${episode.closed_at}` : " – ongoing"}</span>
          </div>
          <div className="space-y-3">
            {episode.encounters.map((encounter) => (
              <EncounterCard key={encounter.id} encounter={encounter} scenario={scenario} openAction={openAction} setOpenAction={setOpenAction} onReconstruct={onReconstruct} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

// --- Screen: AI Agent Registry -------------------------------------------------

function AgentRegistryScreen({ agents }: { agents: Agent[] | null }) {
  if (!agents) return <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>Connecting to simulator…</p>;
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold" style={{ color: "var(--sim-navy)" }}>AI Agent Registry</h1>
        <p className="mt-1 text-sm font-mono" style={{ color: "var(--color-text-muted)" }}>CNE-ID = H( Substrate Anchor ‖ CoF-ID ‖ Policy Set )</p>
      </div>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {agents.map((a) => (
          <Card key={a.id}>
            <div className="flex items-start justify-between">
              <div>
                <h3 className="text-sm font-semibold">{a.name}</h3>
                <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>{a.responsibility}</p>
              </div>
              <Pill color={statusColor(a.status)}>{a.status}</Pill>
            </div>
            <dl className="mt-3 grid grid-cols-2 gap-y-1.5 text-xs">
              <dt style={{ color: "var(--color-text-muted)" }}>CoF-ID</dt><dd>{a.cof_id}</dd>
              <dt style={{ color: "var(--color-text-muted)" }}>Substrate anchor</dt><dd>{a.substrate_anchor} ({a.substrate_label})</dd>
              <dt style={{ color: "var(--color-text-muted)" }}>Runtime</dt><dd>{a.runtime}</dd>
              <dt style={{ color: "var(--color-text-muted)" }}>Narrative sequence</dt><dd>{a.narrative_seq} frame(s)</dd>
              <dt style={{ color: "var(--color-text-muted)" }}>Last activity</dt><dd>{fmtDate(a.last_activity_at)}</dd>
            </dl>
            <div className="mt-2 rounded-md border px-2 py-1.5 text-[11px] font-mono" style={{ borderColor: "var(--color-border)", color: "var(--sim-navy)" }} title={a.cne_id}>CNE-ID {a.cne_id}</div>
            <div className="mt-3 grid grid-cols-3 gap-2 text-[11px]">
              <div><div className="font-semibold" style={{ color: "var(--color-text-muted)" }}>Department policy</div><ul className="mt-1 space-y-0.5">{a.policy_set.department.map((p) => <li key={p}>· {p}</li>)}</ul></div>
              <div><div className="font-semibold" style={{ color: "var(--color-text-muted)" }}>Task policy</div><ul className="mt-1 space-y-0.5">{a.policy_set.task.map((p) => <li key={p}>· {p}</li>)}</ul></div>
              <div><div className="font-semibold" style={{ color: "var(--color-text-muted)" }}>Patient policy</div><ul className="mt-1 space-y-0.5">{a.policy_set.patient.map((p) => <li key={p}>· {p}</li>)}</ul></div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

// --- Screens: Without CNE / With CNE --------------------------------------------

function WithoutCneScreen({ journey }: { journey: PatientJourney | null }) {
  const [openAction, setOpenAction] = useState<string | null>(null);
  if (!journey) return <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>Connecting to simulator…</p>;
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold" style={{ color: "var(--sim-navy)" }}>Without CNE</h1>
        <p className="mt-1 max-w-3xl text-sm" style={{ color: "var(--color-text-muted)" }}>The same hospital, the same AI agents, the same patient journey. The agents still produce clinically plausible outputs — the problem is not output quality, it is the hospital's inability to establish reliable identity, continuity, exclusivity and attribution for any of it.</p>
      </div>
      <Card>
        <SectionTitle>What's missing in this universe</SectionTitle>
        <ul className="grid gap-1.5 text-xs sm:grid-cols-2">
          {WITHOUT_CNE_LIMITATIONS.map((l) => <li key={l} className="flex gap-2"><span style={{ color: "var(--color-warning)" }}>⚠</span>{l}</li>)}
        </ul>
      </Card>
      {journey.episodes.map((episode) => (
        <div key={episode.id}>
          <h2 className="mb-2 text-sm font-semibold">{episode.name}</h2>
          <div className="space-y-3">
            {episode.encounters.map((encounter) => (
              <EncounterCard key={encounter.id} encounter={encounter} scenario="without_cne" openAction={openAction} setOpenAction={setOpenAction} onReconstruct={() => undefined} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function WithCneScreen({ journey, onReconstruct }: { journey: PatientJourney | null; onReconstruct: (actionId: string) => void }) {
  const [openAction, setOpenAction] = useState<string | null>(null);
  if (!journey) return <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>Connecting to simulator…</p>;
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold" style={{ color: "var(--sim-navy)" }}>With CNE</h1>
        <p className="mt-1 max-w-3xl text-sm" style={{ color: "var(--color-text-muted)" }}>Every action now carries a verified CNE-ID, a linked Global Narrative Frame, and — where a belief is revised from new evidence — a Recursive Belief Revision proof capsule. Open any action to inspect its identity and trace, or reconstruct its complete decision trail.</p>
      </div>
      {journey.episodes.map((episode) => (
        <div key={episode.id}>
          <h2 className="mb-2 text-sm font-semibold">{episode.name}</h2>
          <div className="space-y-3">
            {episode.encounters.map((encounter) => (
              <EncounterCard key={encounter.id} encounter={encounter} scenario="with_cne" openAction={openAction} setOpenAction={setOpenAction} onReconstruct={onReconstruct} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

// --- Screen: Governance Comparison -----------------------------------------------

const EVENT_BUTTONS: { type: string; label: string; description: string }[] = [
  { type: "normal_consultation", label: "1 · Normal consultation", description: "Patient submits symptoms; replay the triage stage." },
  { type: "new_diagnostic_evidence", label: "2 · New diagnostic evidence", description: "Upload a new lab report; the diagnosis updates." },
  { type: "duplicate_agent", label: "4 · Duplicate AI agent", description: "Spin up a second Treatment Recommendation Agent instance." },
  { type: "cross_context_contamination", label: "5 · Cross-context contamination", description: "Try to reuse a respiratory output in the orthopaedic visit." },
  { type: "new_unrelated_treatment", label: "6 · New unrelated treatment", description: "Confirm episode separation for the orthopaedic visit." },
  { type: "agent_substrate_change", label: "7 · Agent restart / substrate change", description: "Move the Diagnostic Agent to a different compute node." },
];

function EventOutcomePanel({ title, outcome }: { title: string; outcome: Record<string, unknown> | null }) {
  return (
    <div className="rounded-lg border p-3" style={{ borderColor: "var(--color-border)" }}>
      <div className="text-xs font-semibold" style={{ color: "var(--sim-navy)" }}>{title}</div>
      {!outcome ? (
        <p className="mt-1 text-[11px]" style={{ color: "var(--color-text-muted)" }}>No event triggered yet.</p>
      ) : (
        <dl className="mt-2 space-y-1 text-[11px]">
          {Object.entries(outcome).map(([k, v]) => (
            <div key={k} className="flex justify-between gap-2">
              <dt style={{ color: "var(--color-text-muted)" }}>{k.replaceAll("_", " ")}</dt>
              <dd className="text-right">{Array.isArray(v) ? v.join(", ") : String(v)}</dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  );
}

function GovernanceComparisonScreen({ comparisonData, overview, onTriggerEvent, lastResults, onDoctorConsume, journey }: {
  comparisonData: ComparisonData | null;
  overview: HospitalOverview | null;
  onTriggerEvent: (type: string) => void;
  lastResults: Record<string, { without_cne: Record<string, unknown>; with_cne: Record<string, unknown> }>;
  onDoctorConsume: () => void;
  journey: PatientJourney | null;
}) {
  const firstAction = journey?.episodes[0]?.encounters[0]?.actions.with_cne.find((a) => a.stage === "treatment");
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold" style={{ color: "var(--sim-navy)" }}>Governance Comparison</h1>
        <p className="mt-1 text-sm" style={{ color: "var(--color-text-muted)" }}>Trigger a governance event and watch both scenarios update together.</p>
      </div>

      <Card>
        <SectionTitle>Dimension by dimension</SectionTitle>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b" style={{ borderColor: "var(--color-border)" }}>
                <th className="py-1.5 pr-3 font-semibold">Governance dimension</th>
                <th className="py-1.5 pr-3 font-semibold" style={{ color: "var(--color-warning)" }}>Without CNE</th>
                <th className="py-1.5 font-semibold" style={{ color: "var(--sim-teal)" }}>With CNE</th>
              </tr>
            </thead>
            <tbody>
              {comparisonData?.dimensions.map((row) => (
                <tr key={row.dimension} className="border-b" style={{ borderColor: "var(--color-border)" }}>
                  <td className="py-1.5 pr-3 font-medium">{row.dimension}</td>
                  <td className="py-1.5 pr-3" style={{ color: "var(--color-text-muted)" }}>{row.without_cne}</td>
                  <td className="py-1.5">{row.with_cne}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {overview && (
        <Card>
          <SectionTitle>Live metrics</SectionTitle>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-5 text-xs">
            {Object.entries(overview.metrics).map(([k, v]) => (
              <div key={k}><div className="text-lg font-semibold" style={{ color: "var(--sim-navy)" }}>{v}</div><div style={{ color: "var(--color-text-muted)" }}>{k.replaceAll("_", " ")}</div></div>
            ))}
          </div>
        </Card>
      )}

      <div>
        <SectionTitle caption="Every event updates both scenario panels at once.">Trigger a governance event</SectionTitle>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <Card className="!p-3">
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="text-xs font-semibold">3 · Doctor consumes AI output</div>
                <p className="mt-0.5 text-[11px]" style={{ color: "var(--color-text-muted)" }}>Dr. Meera Sharma clicks "Use AI Recommendation" on the Visit 1 treatment recommendation.</p>
              </div>
              <button disabled={!firstAction} onClick={onDoctorConsume} className="shrink-0 rounded-md px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50" style={{ background: "var(--sim-teal)" }}>Run</button>
            </div>
            {lastResults.doctor_consumes_output && (
              <div className="mt-3 grid grid-cols-2 gap-2">
                <EventOutcomePanel title="Without CNE" outcome={lastResults.doctor_consumes_output.without_cne} />
                <EventOutcomePanel title="With CNE" outcome={lastResults.doctor_consumes_output.with_cne} />
              </div>
            )}
          </Card>
          {EVENT_BUTTONS.map((e) => (
            <Card key={e.type} className="!p-3">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="text-xs font-semibold">{e.label}</div>
                  <p className="mt-0.5 text-[11px]" style={{ color: "var(--color-text-muted)" }}>{e.description}</p>
                </div>
                <button onClick={() => onTriggerEvent(e.type)} className="shrink-0 rounded-md px-3 py-1.5 text-xs font-medium text-white" style={{ background: "var(--sim-teal)" }}>Run</button>
              </div>
              {lastResults[e.type] && (
                <div className="mt-3 grid grid-cols-2 gap-2">
                  <EventOutcomePanel title="Without CNE" outcome={lastResults[e.type].without_cne} />
                  <EventOutcomePanel title="With CNE" outcome={lastResults[e.type].with_cne} />
                </div>
              )}
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}

// --- Screen: Audit & Accountability -----------------------------------------------

function TrailView({ trail }: { trail: TrailEntry[] }) {
  return (
    <div className="space-y-3">
      {trail.map((entry) => (
        <div key={entry.action.id} className="rounded-lg border p-3 text-xs" style={{ borderColor: "var(--color-border)" }}>
          <div className="flex items-center gap-2">
            <span className="font-semibold capitalize">{readableStage(entry.action.stage)}</span>
            <span style={{ color: "var(--color-text-muted)" }}>{entry.agent?.name}</span>
            <Pill color={entry.action.scenario === "with_cne" ? "var(--sim-teal)" : "var(--color-warning)"}>{entry.action.scenario === "with_cne" ? "With CNE" : "Without CNE"}</Pill>
          </div>
          <p className="mt-1" style={{ color: "var(--color-text-muted)" }}>{entry.encounter?.encounter_code} · {entry.encounter?.visit_date} · {entry.encounter?.department}</p>
          <p className="mt-2 leading-5">{entry.action.output_text}</p>
          <dl className="mt-2 grid grid-cols-2 gap-y-1">
            <dt style={{ color: "var(--color-text-muted)" }}>Consumed by</dt><dd>{entry.action.consumed_by ?? "Not yet consumed"}</dd>
            <dt style={{ color: "var(--color-text-muted)" }}>Status</dt><dd>{entry.action.status}</dd>
            {entry.action.cne_id_snapshot && <><dt style={{ color: "var(--color-text-muted)" }}>CNE-ID</dt><dd className="truncate" title={entry.action.cne_id_snapshot}>{shortHash(entry.action.cne_id_snapshot, 28)}</dd></>}
            {entry.gnf_frame && <><dt style={{ color: "var(--color-text-muted)" }}>GNF frame</dt><dd>seq {String(entry.gnf_frame.seq)}, hash {shortHash(String(entry.gnf_frame.frame_hash), 20)}</dd></>}
            {entry.rbr_proof && <><dt style={{ color: "var(--color-text-muted)" }}>RbR proof</dt><dd>{String(entry.rbr_proof.status)}, post-belief {shortHash(String(entry.rbr_proof.post_belief_hash), 20)}</dd></>}
          </dl>
          {entry.approvals && entry.approvals.length > 0 && (
            <div className="mt-2">
              <span style={{ color: "var(--color-text-muted)" }}>Decisions: </span>
              {entry.approvals.map((ap, i) => <span key={i}>{String(ap.decided_by)} → {String(ap.status)}; </span>)}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function AuditScreen({ auditData, journey, reconstructResult, onReconstructByEncounter }: {
  auditData: AuditData | null;
  journey: PatientJourney | null;
  reconstructResult: ReconstructResult | null;
  onReconstructByEncounter: (encounterId: string) => void;
}) {
  const allEncounters = journey?.episodes.flatMap((e) => e.encounters) ?? [];
  const [selected, setSelected] = useState<string>("");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold" style={{ color: "var(--sim-navy)" }}>Audit & Accountability</h1>
        <p className="mt-1 text-sm" style={{ color: "var(--color-text-muted)" }}>Select a visit and reconstruct the complete AI decision trail across every agent action, identity, proof and consumption event.</p>
      </div>

      <Card>
        <SectionTitle>Reconstruct complete AI decision trail</SectionTitle>
        <div className="flex items-center gap-2">
          <select className="rounded-md border px-2.5 py-1.5 text-sm" style={{ borderColor: "var(--color-border)" }} value={selected} onChange={(e) => setSelected(e.target.value)}>
            <option value="">Select a visit…</option>
            {allEncounters.map((e) => <option key={e.id} value={e.id}>{e.encounter_code} — {e.visit_date} — {e.department}</option>)}
          </select>
          <button disabled={!selected} onClick={() => onReconstructByEncounter(selected)} className="rounded-md px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50" style={{ background: "var(--sim-teal)" }}>Reconstruct Complete AI Decision Trail</button>
        </div>
        {reconstructResult && <div className="mt-4"><TrailView trail={reconstructResult.trail} /></div>}
      </Card>

      <Card>
        <SectionTitle caption="Each agent's Global Narrative Frame chain is independently re-verified here.">Narrative chain integrity</SectionTitle>
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b" style={{ borderColor: "var(--color-border)" }}>
              <th className="py-1.5 pr-3 font-semibold">Agent</th>
              <th className="py-1.5 pr-3 font-semibold">CoF-ID</th>
              <th className="py-1.5 pr-3 font-semibold">Frames</th>
              <th className="py-1.5 font-semibold">Chain status</th>
            </tr>
          </thead>
          <tbody>
            {auditData?.chains.map((c) => (
              <tr key={c.agent_id} className="border-b" style={{ borderColor: "var(--color-border)" }}>
                <td className="py-1.5 pr-3">{c.agent_name}</td>
                <td className="py-1.5 pr-3" style={{ color: "var(--color-text-muted)" }}>{c.cof_id}</td>
                <td className="py-1.5 pr-3">{c.frame_count}</td>
                <td className="py-1.5"><Pill color={c.verification.valid ? "var(--color-success)" : "var(--color-danger)"}>{c.verification.valid ? "Verified intact" : "Broken"}</Pill></td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <Card>
        <SectionTitle>Governance event log</SectionTitle>
        <div className="max-h-96 space-y-1.5 overflow-y-auto">
          {auditData?.events.map((e) => (
            <div key={e.id} className="flex items-start justify-between gap-3 border-b pb-1.5 text-xs" style={{ borderColor: "var(--color-border)" }}>
              <div>
                <span className="font-medium capitalize">{readableEventType(e.event_type)}</span>
                <span className="ml-2" style={{ color: "var(--color-text-muted)" }}>{e.scenario === "with_cne" ? "With CNE" : "Without CNE"}</span>
                <p className="mt-0.5" style={{ color: "var(--color-text-muted)" }}>{String(e.detail.finding ?? "")}</p>
              </div>
              <div className="shrink-0 text-right">
                <Pill color={severityColor(e.severity)}>{e.severity}</Pill>
                <div className="mt-1" style={{ color: "var(--color-text-muted)" }}>{fmtDate(e.created_at)}</div>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

// --- Root --------------------------------------------------------------------

export default function GovernanceSimulator() {
  const location = useLocation();
  const navigate = useNavigate();
  const page = location.pathname.split("/")[2] || "comparison";
  const { overview, journey, agents, comparisonData, auditData, refresh } = useSimulatorData();
  const [eventResults, setEventResults] = useState<Record<string, { without_cne: Record<string, unknown>; with_cne: Record<string, unknown> }>>({});
  const [reconstructResult, setReconstructResult] = useState<ReconstructResult | null>(null);

  const triggerEvent = useCallback((type: string) => {
    api.post<{ without_cne: Record<string, unknown>; with_cne: Record<string, unknown> }>(`/simulator/events/${type}`, {}).then((result) => {
      setEventResults((prev) => ({ ...prev, [type]: result }));
      void refresh();
    });
  }, [refresh]);

  const doctorConsume = useCallback(() => {
    const action = journey?.episodes[0]?.encounters[0]?.actions.with_cne.find((a) => a.stage === "treatment");
    if (!action) return;
    api.post(`/simulator/actions/${action.id}/decision`, { decision: "accepted", decided_by: "Dr. Meera Sharma", note: "Reviewed and approved." }).then(() => {
      setEventResults((prev) => ({ ...prev, doctor_consumes_output: { without_cne: { attribution_recorded: false }, with_cne: { attribution_recorded: true, decided_by: "Dr. Meera Sharma" } } }));
      void refresh();
    });
  }, [journey, refresh]);

  const reconstructByAction = useCallback((actionId: string) => {
    api.post<ReconstructResult>("/simulator/audit/reconstruct", { action_id: actionId }).then((result) => {
      setReconstructResult(result);
      navigate("/governance-simulator/audit");
    });
  }, [navigate]);

  const reconstructByEncounter = useCallback((encounterId: string) => {
    api.post<ReconstructResult>("/simulator/audit/reconstruct", { encounter_id: encounterId }).then(setReconstructResult);
  }, []);

  let content: ReactNode;
  if (page === "overview") content = <HospitalOverviewScreen overview={overview} />;
  else if (page === "journey") content = <PatientJourneyScreen journey={journey} onReconstruct={reconstructByAction} />;
  else if (page === "agents") content = <AgentRegistryScreen agents={agents} />;
  else if (page === "without-cne") content = <WithoutCneScreen journey={journey} />;
  else if (page === "with-cne") content = <WithCneScreen journey={journey} onReconstruct={reconstructByAction} />;
  else if (page === "audit") content = <AuditScreen auditData={auditData} journey={journey} reconstructResult={reconstructResult} onReconstructByEncounter={reconstructByEncounter} />;
  else content = <GovernanceComparisonScreen comparisonData={comparisonData} overview={overview} onTriggerEvent={triggerEvent} lastResults={eventResults} onDoctorConsume={doctorConsume} journey={journey} />;

  return <Shell page={page}>{content}</Shell>;
}
