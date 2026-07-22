import type { CSSProperties, ReactNode } from "react";

export function Card({
  padding = "var(--space-5)",
  elevated = false,
  children,
  style = {},
}: {
  padding?: string;
  elevated?: boolean;
  children: ReactNode;
  style?: CSSProperties;
}) {
  return (
    <div
      style={{
        background: "var(--surface-card)",
        border: "1px solid var(--border-default)",
        borderRadius: "var(--radius-lg)",
        padding,
        boxShadow: elevated ? "var(--shadow-elevated)" : "var(--shadow-card)",
        ...style,
      }}
    >
      {children}
    </div>
  );
}
