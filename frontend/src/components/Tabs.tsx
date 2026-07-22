export interface TabDef {
  value: string;
  label: string;
}

export function Tabs({
  tabs,
  active,
  onChange,
}: {
  tabs: TabDef[];
  active: string;
  onChange: (value: string) => void;
}) {
  return (
    <div style={{ display: "flex", gap: 4, borderBottom: "1px solid var(--border-default)", fontFamily: "var(--font-ui)" }}>
      {tabs.map((t) => (
        <button
          key={t.value}
          onClick={() => onChange(t.value)}
          style={{
            background: "none",
            border: "none",
            cursor: "pointer",
            padding: "10px 14px",
            font: "var(--text-label-md)",
            color: active === t.value ? "var(--text-primary)" : "var(--text-muted)",
            borderBottom: `2px solid ${active === t.value ? "var(--accent)" : "transparent"}`,
            marginBottom: -1,
          }}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}
