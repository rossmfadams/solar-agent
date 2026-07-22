import { type CSSProperties, type ReactNode, useState } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

const VARIANTS: Record<Variant, CSSProperties> = {
  primary: { background: "var(--accent)", color: "var(--text-on-accent)", border: "1px solid var(--accent)" },
  secondary: { background: "var(--surface-card)", color: "var(--text-primary)", border: "1px solid var(--border-subtle)" },
  ghost: { background: "transparent", color: "var(--text-primary)", border: "1px solid transparent" },
  danger: { background: "var(--status-danger)", color: "#fff", border: "1px solid var(--status-danger)" },
};

const SIZES: Record<Size, CSSProperties> = {
  sm: { padding: "6px 12px", font: "var(--text-label-sm)" },
  md: { padding: "9px 16px", font: "var(--text-label-md)" },
  lg: { padding: "12px 20px", font: "600 15px var(--font-ui)" },
};

export function Button({
  variant = "primary",
  size = "md",
  disabled = false,
  children,
  onClick,
}: {
  variant?: Variant;
  size?: Size;
  disabled?: boolean;
  children: ReactNode;
  onClick?: () => void;
}) {
  const [hovered, setHovered] = useState(false);
  return (
    <button
      onClick={disabled ? undefined : onClick}
      disabled={disabled}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 8,
        borderRadius: "var(--radius-md)",
        cursor: disabled ? "not-allowed" : "pointer",
        transition: "opacity 0.15s ease, background 0.15s ease",
        opacity: disabled ? 0.45 : hovered ? 0.88 : 1,
        ...VARIANTS[variant],
        ...SIZES[size],
      }}
    >
      {children}
    </button>
  );
}
