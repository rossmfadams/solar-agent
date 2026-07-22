import type { ReactNode } from "react";

export function Tag({ children, href }: { children: ReactNode; href?: string }) {
  const Comp = href ? "a" : "span";
  return (
    <Comp
      href={href}
      style={{
        display: "inline-flex",
        alignItems: "center",
        padding: "3px 10px",
        borderRadius: "var(--radius-pill)",
        font: "var(--text-label-sm)",
        color: "var(--text-tertiary)",
        background: "var(--surface-card)",
        border: "1px solid var(--border-subtle)",
        textDecoration: "none",
        cursor: href ? "pointer" : "default",
      }}
    >
      {children}
    </Comp>
  );
}
