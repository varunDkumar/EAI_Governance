import { Navigate, Route, Routes, useLocation } from "react-router-dom";
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
import GovernanceSimulator from "./pages/GovernanceSimulator";

// The public web deployment only ever serves the Governance Simulator (fully
// synthetic data) — Memory Intelligence sits over the user's real academic
// corpus, which is desktop-only and never shipped to the public backend.
const PUBLIC_MODE = import.meta.env.VITE_PUBLIC_MODE === "true";

function App() {
  const location = useLocation();
  if (PUBLIC_MODE) {
    if (!location.pathname.startsWith("/governance-simulator")) {
      return <Navigate to="/governance-simulator/comparison" replace />;
    }
    return <GovernanceSimulator />;
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
