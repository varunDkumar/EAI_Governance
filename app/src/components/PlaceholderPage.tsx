export default function PlaceholderPage({ title, phase }: { title: string; phase: string }) {
  return (
    <div className="space-y-2">
      <h1 className="text-xl font-semibold">{title}</h1>
      <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
        Built in {phase}.
      </p>
    </div>
  );
}
