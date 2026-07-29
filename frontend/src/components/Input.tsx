import type { KeyboardEvent } from "react";

export function Input({
  id,
  label,
  placeholder,
  value,
  onChange,
  onEnter,
  onKeyDown,
  helper,
  error,
  role,
  ariaExpanded,
  ariaControls,
  ariaActiveDescendant,
  ariaAutoComplete,
}: {
  id?: string;
  label?: string;
  placeholder?: string;
  value: string;
  onChange?: (value: string) => void;
  onEnter?: () => void;
  onKeyDown?: (e: KeyboardEvent<HTMLInputElement>) => void;
  helper?: string;
  error?: string;
  role?: string;
  ariaExpanded?: boolean;
  ariaControls?: string;
  ariaActiveDescendant?: string;
  ariaAutoComplete?: "list" | "none" | "inline" | "both";
}) {
  const helperId = helper || error ? `${id ?? "field"}-helper` : undefined;

  return (
    <label style={{ display: "flex", flexDirection: "column", gap: 6, fontFamily: "var(--font-ui)" }}>
      {label && <span style={{ font: "var(--text-label-md)", color: "var(--text-primary)" }}>{label}</span>}
      <input
        id={id}
        value={value}
        placeholder={placeholder}
        role={role}
        aria-expanded={ariaExpanded}
        aria-controls={ariaControls}
        aria-activedescendant={ariaActiveDescendant}
        aria-autocomplete={ariaAutoComplete}
        aria-describedby={helperId}
        aria-invalid={error ? true : undefined}
        onChange={(e) => onChange?.(e.target.value)}
        onKeyDown={(e) => {
          onKeyDown?.(e);
          if (!e.defaultPrevented && e.key === "Enter") onEnter?.();
        }}
        style={{
          font: "var(--text-body-md)",
          color: "var(--text-primary)",
          background: "var(--surface-card)",
          border: `1px solid ${error ? "var(--status-danger)" : "var(--border-subtle)"}`,
          borderRadius: "var(--radius-md)",
          padding: "10px 12px",
          minHeight: 44,
        }}
      />
      {(helper || error) && (
        <span
          id={helperId}
          role={error ? "alert" : undefined}
          aria-live={error ? "assertive" : undefined}
          style={{ font: "var(--text-body-sm)", color: error ? "var(--status-danger)" : "var(--text-muted)" }}
        >
          {error || helper}
        </span>
      )}
    </label>
  );
}
