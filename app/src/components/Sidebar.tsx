import { NavLink } from "react-router-dom";
import { Link } from "react-router-dom";

const NAV_ITEMS = [
  { to: "/overview", label: "Overview", icon: "◧" },
  { to: "/workspace", label: "AI Workspace", icon: "◎" },
  { to: "/repository", label: "Knowledge Repository", icon: "▤" },
  { to: "/memory", label: "Memory Explorer", icon: "✦" },
  { to: "/graph", label: "Knowledge Graph", icon: "⬡" },
  { to: "/agents", label: "Agent Management", icon: "⚙" },
  { to: "/governance", label: "Governance Centre", icon: "⛉" },
  { to: "/approvals", label: "Approval Centre", icon: "✓" },
  { to: "/audit", label: "Audit Log", icon: "≡" },
  { to: "/settings", label: "Settings", icon: "✧" },
];

export default function Sidebar() {
  return (
    <aside
      className="flex h-full w-60 flex-col border-r px-3 py-4"
      style={{ borderColor: "var(--color-border)", background: "var(--color-surface)" }}
    >
      <div className="mb-6 px-2">
        <div className="text-sm font-semibold tracking-tight" style={{ color: "var(--color-primary)" }}>
          Agent Trust Fabric
        </div>
        <div className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          Academic Intelligence Edition
        </div>
      </div>
      <nav className="flex flex-1 flex-col gap-0.5">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) =>
              `flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition-colors ${
                isActive ? "font-medium" : ""
              }`
            }
            style={({ isActive }) => ({
              color: isActive ? "var(--color-primary)" : "var(--color-text)",
              background: isActive ? "color-mix(in srgb, var(--color-primary) 12%, transparent)" : "transparent",
            })}
          >
            <span aria-hidden className="w-4 text-center text-xs opacity-70">
              {item.icon}
            </span>
            {item.label}
          </NavLink>
        ))}
      </nav>
      <Link to="/" className="mt-3 rounded-md border border-[var(--color-border)] px-2.5 py-2 text-xs font-medium text-[var(--color-primary)] hover:bg-violet-50">← Switch product</Link>
    </aside>
  );
}
