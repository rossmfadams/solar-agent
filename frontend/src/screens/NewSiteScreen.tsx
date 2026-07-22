import { useState } from "react";
import { streamScreen } from "../api/screen";
import type { Memo } from "../api/types";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Input } from "../components/Input";
import { ProgressChecklist, type StepState } from "../components/ProgressChecklist";

export function NewSiteScreen({ onComplete }: { onComplete: (memo: Memo) => void }) {
  const [address, setAddress] = useState("");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [steps, setSteps] = useState<Record<string, StepState>>({});

  const run = async () => {
    setError(null);
    setSteps({});
    setRunning(true);

    try {
      await streamScreen({ address }, (event) => {
        if (event.type === "node") {
          setSteps((prev) => ({
            ...prev,
            [event.node]: { status: event.status, label: event.label },
          }));
        } else if (event.type === "error") {
          setError(event.message);
          setRunning(false);
        } else if (event.type === "memo") {
          onComplete(event.memo);
        }
      });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div style={{ padding: 28, fontFamily: "var(--font-ui)", flex: 1, display: "flex", justifyContent: "center" }}>
      <div style={{ width: 480, marginTop: 40 }}>
        <div style={{ font: "var(--text-display-md)", color: "var(--text-primary)", textAlign: "center" }}>
          New site diligence
        </div>
        <div style={{ font: "var(--text-body-md)", color: "var(--text-tertiary)", textAlign: "center", marginTop: 6 }}>
          Enter an address. Watch the agent work — a structured memo is ready in about 90 seconds.
        </div>
        <Card style={{ marginTop: 24 }}>
          <Input
            label="Address"
            placeholder="123 County Rd, Madison County, NY"
            value={address}
            onChange={setAddress}
            error={error ?? undefined}
          />
          <div style={{ marginTop: 16, display: "flex", justifyContent: "flex-end" }}>
            <Button variant="primary" onClick={run} disabled={running || !address.trim()}>
              {running ? "Running diligence…" : "Run diligence"}
            </Button>
          </div>
        </Card>
        {running && (
          <Card style={{ marginTop: 16 }}>
            <ProgressChecklist completed={steps} />
          </Card>
        )}
        <div style={{ font: "var(--text-body-sm)", color: "var(--text-muted)", marginTop: 14, textAlign: "center" }}>
          Covers siting, interconnection, and permitting — sourced from NY GIS, HIFLD, utility hosting-capacity portals,
          FEMA, USFWS, USGS, and PAD-US.
        </div>
      </div>
    </div>
  );
}
