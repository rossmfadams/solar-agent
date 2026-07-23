export function Input({
  label,
  placeholder,
  value,
  onChange,
  onEnter,
  helper,
  error,
}: {
  label?: string;
  placeholder?: string;
  value: string;
  onChange?: (value: string) => void;
  onEnter?: () => void;
  helper?: string;
  error?: string;
}) {
  return (
    <label style={{ display: "flex", flexDirection: "column", gap: 6, fontFamily: "var(--font-ui)" }}>
      {label && <span style={{ font: "var(--text-label-md)", color: "var(--text-primary)" }}>{label}</span>}
      <input
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange?.(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") onEnter?.();
        }}
        style={{
          font: "var(--text-body-md)",
          color: "var(--text-primary)",
          background: "var(--surface-card)",
          border: `1px solid ${error ? "var(--status-danger)" : "var(--border-subtle)"}`,
          borderRadius: "var(--radius-md)",
          padding: "10px 12px",
          outline: "none",
        }}
      />
      {(helper || error) && (
        <span style={{ font: "var(--text-body-sm)", color: error ? "var(--status-danger)" : "var(--text-muted)" }}>
          {error || helper}
        </span>
      )}
    </label>
  );
}
