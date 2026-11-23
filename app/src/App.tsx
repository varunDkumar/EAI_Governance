import { Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import Overview from "./pages/Overview";
import Workspace from "./pages/Workspace";
import Repository from "./pages/Repository";
import MemoryExplorer from "./pages/MemoryExplorer";
import KnowledgeGraph from "./pages/KnowledgeGraph";
import AgentManagement from "./pages/AgentManagement";
import GovernanceCentre from "./pages/GovernanceCentre";
import ApprovalCentre from "./pages/ApprovalCentre";
import AuditLog from "./pages/AuditLog";
import Settings from "./pages/Settings";
import Home from "./pages/Home";
import PublicHome from "./pages/PublicHome";
import GovernanceSimulator from "./pages/GovernanceSimulator";

// The public web deployment only ever serves two products: the Governance
// Simulator (fully synthetic data) and a read-only Knowledge Graph view
// (see backend/api/public_graph.py). The rest of Memory Intelligence — chat,
// memory, agents, governance centre — sits over the user's live corpus and
// stays desktop-only.
const PUBLIC_MODE = import.meta.env.VITE_PUBLIC_MODE === "true";

function PublicGraphShell() {
  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden">
      <div className="flex items-center justify-between border-b bg-white px-7 py-2.5" style={{ borderColor: "var(--color-border)" }}>
        <Link to="/" className="text-xs font-semibold" style={{ color: "var(--color-primary)" }}>← All products</Link>
        <div className="text-[11px]" style={{ color: "var(--color-text-muted)" }}>IIM Ahmedabad MBA course corpus · read-only public demo</div>
      </div>
      <main className="min-h-0 flex-1 overflow-y-auto px-8 py-6">
        <KnowledgeGraph />
      </main>
    </div>
  );
}

function App() {
  const location = useLocation();
  if (PUBLIC_MODE) {
    if (location.pathname === "/") return <PublicHome />;
    if (location.pathname.startsWith("/governance-simulator")) return <GovernanceSimulator />;
    if (location.pathname.startsWith("/graph")) return <PublicGraphShell />;
    return <Navigate to="/" replace />;
  }
  if (location.pathname === "/") return <Home />;
  if (location.pathname.startsWith("/governance-simulator")) return <GovernanceSimulator />;
  return (
    <div className="flex h-screen w-screen overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-y-auto px-8 py-6">
        <Routes>
          <Route path="/overview" element={<Overview />} />
          <Route path="/" element={<Navigate to="/overview" replace />} />
          <Route path="/workspace" element={<Workspace />} />
          <Route path="/repository" element={<Repository />} />
          <Route path="/memory" element={<MemoryExplorer />} />
          <Route path="/graph" element={<KnowledgeGraph />} />
          <Route path="/agents" element={<AgentManagement />} />
          <Route path="/governance" element={<GovernanceCentre />} />
          <Route path="/approvals" element={<ApprovalCentre />} />
          <Route path="/audit" element={<AuditLog />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
