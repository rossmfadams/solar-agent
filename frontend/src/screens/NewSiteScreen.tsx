import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { getScreenMemo, streamScreen } from "../api/screen";
import { getRecentRuns, saveRecentRun, type RecentRun } from "../api/recentRuns";
import type { Memo } from "../api/types";
import { isVerified, UNABLE_TO_VERIFY } from "../api/types";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Input } from "../components/Input";
import { ProgressChecklist, type StepState } from "../components/ProgressChecklist";

export function NewSiteScreen({ onComplete }: { onComplete: (memo: Memo) => void }) {
  const [address, setAddress] = useState("");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [steps, setSteps] = useState<Record<string, StepState>>({});
  const [recentRuns, setRecentRuns] = useState<RecentRun[]>(() => getRecentRuns());
  const queryClient = useQueryClient();

  const run = async () => {
    if (running || !address.trim()) return;

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
          const score = isVerified(event.memo.viability) ? event.memo.viability.score : null;
          saveRecentRun({ site_id: event.memo.site_id, address, score });
          setRecentRuns(getRecentRuns());
          onComplete(event.memo);
        }
      });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setRunning(false);
    }
  };

  const openRecentRun = async (siteId: string) => {
    try {
      const memo = await queryClient.fetchQuery({
        queryKey: ["screen-memo", siteId],
        queryFn: () => getScreenMemo(siteId),
      });
      onComplete(memo);
    } catch (err) {
      setError((err as Error).message);
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
            onEnter={run}
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
        {!running && recentRuns.length > 0 && (
          <Card style={{ marginTop: 16 }}>
            <div style={{ font: "var(--text-label-md)", color: "var(--text-primary)", marginBottom: 8 }}>
              Recent runs
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              {recentRuns.map((r) => (
                <button
                  key={r.site_id}
                  onClick={() => openRecentRun(r.site_id)}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    background: "transparent",
                    border: "none",
                    borderRadius: "var(--radius-md)",
                    padding: "8px 6px",
                    cursor: "pointer",
                    font: "var(--text-body-md)",
                    color: "var(--text-primary)",
                    textAlign: "left",
                  }}
                >
                  <span>{r.address}</span>
                  <span style={{ color: "var(--text-tertiary)" }}>
                    {r.score !== null ? r.score : UNABLE_TO_VERIFY}
                  </span>
                </button>
              ))}
            </div>
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
