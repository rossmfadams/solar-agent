export interface TabDef {
  value: string;
  label: string;
}

export function Tabs({
  tabs,
  active,
  onChange,
  idPrefix = "tabs",
}: {
  tabs: TabDef[];
  active: string;
  onChange: (value: string) => void;
  idPrefix?: string;
}) {
  function handleKeyDown(e: React.KeyboardEvent<HTMLButtonElement>, index: number) {
    let nextIndex: number | null = null;
    if (e.key === "ArrowRight") nextIndex = (index + 1) % tabs.length;
    else if (e.key === "ArrowLeft") nextIndex = (index - 1 + tabs.length) % tabs.length;
    else if (e.key === "Home") nextIndex = 0;
    else if (e.key === "End") nextIndex = tabs.length - 1;
    if (nextIndex === null) return;
    e.preventDefault();
    const next = tabs[nextIndex];
    onChange(next.value);
    document.getElementById(`${idPrefix}-tab-${next.value}`)?.focus();
  }

  return (
    <div
      role="tablist"
      style={{ display: "flex", gap: 4, borderBottom: "1px solid var(--border-default)", fontFamily: "var(--font-ui)" }}
    >
      {tabs.map((t, i) => {
        const selected = active === t.value;
        return (
          <button
            key={t.value}
            id={`${idPrefix}-tab-${t.value}`}
            role="tab"
            aria-selected={selected}
            aria-controls={`${idPrefix}-panel-${t.value}`}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(t.value)}
            onKeyDown={(e) => handleKeyDown(e, i)}
            className="tap-target"
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              padding: "10px 14px",
              font: "var(--text-label-md)",
              color: selected ? "var(--text-primary)" : "var(--text-muted)",
              borderBottom: `2px solid ${selected ? "var(--accent)" : "transparent"}`,
              marginBottom: -1,
            }}
          >
            {t.label}
          </button>
        );
      })}
    </div>
  );
}
