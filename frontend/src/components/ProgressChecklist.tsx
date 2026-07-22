import type { NodeEventStatus } from "../api/types";

// Mirrors app/graph.py's edges so we can infer which not-yet-completed nodes
// are currently running (all their predecessors are done) vs still pending.
const PREDECESSORS: Record<string, string[]> = {
  geocode_address: [],
  resolve_parcel: ["geocode_address"],
  check_grid_proximity: ["resolve_parcel"],
  check_hosting_capacity: ["check_grid_proximity"],
  check_environmental_constraints: ["resolve_parcel"],
  check_terrain: ["resolve_parcel"],
  research_local_ordinance: ["resolve_parcel"],
  synthesize_memo: [
    "check_hosting_capacity",
    "check_environmental_constraints",
    "check_terrain",
    "research_local_ordinance",
  ],
};

const LABELS: Record<string, string> = {
  geocode_address: "Geocoding address",
  resolve_parcel: "Resolving parcel",
  check_grid_proximity: "Checking grid proximity",
  check_hosting_capacity: "Checking hosting capacity",
  check_environmental_constraints: "Checking environmental constraints",
  check_terrain: "Checking terrain",
  research_local_ordinance: "Researching town ordinance",
  synthesize_memo: "Synthesizing memo",
};

const STEP_ORDER = Object.keys(PREDECESSORS);

type StepStatus = "pending" | "running" | NodeEventStatus;

export interface StepState {
  status: NodeEventStatus;
  label: string;
}

function Icon({ status }: { status: StepStatus }) {
  if (status === "done") {
    return <span style={{ color: "var(--status-success)" }}>✓</span>;
  }
  if (status === "warning") {
    return <span style={{ color: "var(--status-warning)" }}>!</span>;
  }
  if (status === "running") {
    return (
      <span
        style={{
          display: "inline-block",
          width: 10,
          height: 10,
          borderRadius: "50%",
          border: "2px solid var(--border-accent)",
          borderTopColor: "transparent",
          animation: "helios-spin 0.8s linear infinite",
        }}
      />
    );
  }
  return <span style={{ color: "var(--text-muted)" }}>○</span>;
}

export function ProgressChecklist({ completed }: { completed: Record<string, StepState> }) {
  const completedOrder = Object.keys(completed);
  const remaining = STEP_ORDER.filter((node) => !completed[node]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
      <style>{"@keyframes helios-spin { to { transform: rotate(360deg); } }"}</style>
      {completedOrder.map((node) => (
        <Row key={node} label={completed[node].label} status={completed[node].status} />
      ))}
      {remaining.map((node) => {
        const predecessorsDone = PREDECESSORS[node].every((p) => completed[p]);
        return (
          <Row
            key={node}
            label={LABELS[node]}
            status={predecessorsDone ? "running" : "pending"}
          />
        );
      })}
    </div>
  );
}

function Row({ label, status }: { label: string; status: StepStatus }) {
  const dim = status === "pending";
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "8px 4px",
        font: "var(--text-body-md)",
        color: dim ? "var(--text-muted)" : "var(--text-secondary)",
      }}
    >
      <Icon status={status} />
      <span>{label}</span>
    </div>
  );
}
