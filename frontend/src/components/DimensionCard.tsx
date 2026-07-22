type Tone = "success" | "warning" | "danger";

const TONE_COLOR: Record<Tone, string> = {
  success: "var(--status-success)",
  warning: "var(--status-warning)",
  danger: "var(--status-danger)",
};

export function DimensionCard({
  label,
  status,
  tone = "success",
  detail,
}: {
  label: string;
  status: string;
  tone?: Tone;
  detail?: string;
}) {
  return (
    <div
      style={{
        background: "var(--surface-card)",
        border: "1px solid var(--border-default)",
        borderRadius: "var(--radius-md)",
        padding: 14,
        fontFamily: "var(--font-ui)",
      }}
    >
      <div style={{ font: "var(--text-label-sm)", color: "var(--text-muted)" }}>{label}</div>
      <div style={{ font: `600 17px var(--font-display)`, color: TONE_COLOR[tone], marginTop: 4 }}>{status}</div>
      {detail && <div style={{ font: "var(--text-body-sm)", color: "var(--text-muted)", marginTop: 2 }}>{detail}</div>}
    </div>
  );
}
