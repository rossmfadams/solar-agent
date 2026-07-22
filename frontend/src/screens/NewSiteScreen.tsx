import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { postScreen } from "../api/screen";
import type { Memo } from "../api/types";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Input } from "../components/Input";

export function NewSiteScreen({ onComplete }: { onComplete: (memo: Memo) => void }) {
  const [address, setAddress] = useState("");

  const mutation = useMutation({
    mutationFn: () => postScreen({ address }),
    onSuccess: onComplete,
  });

  return (
    <div style={{ padding: 28, fontFamily: "var(--font-ui)", flex: 1, display: "flex", justifyContent: "center" }}>
      <div style={{ width: 480, marginTop: 40 }}>
        <div style={{ font: "var(--text-display-md)", color: "var(--text-primary)", textAlign: "center" }}>
          New site diligence
        </div>
        <div style={{ font: "var(--text-body-md)", color: "var(--text-tertiary)", textAlign: "center", marginTop: 6 }}>
          Enter an address. A structured memo is ready in about 90 seconds.
        </div>
        <Card style={{ marginTop: 24 }}>
          <Input
            label="Address"
            placeholder="123 County Rd, Madison County, NY"
            value={address}
            onChange={setAddress}
            error={mutation.isError ? (mutation.error as Error).message : undefined}
          />
          <div style={{ marginTop: 16, display: "flex", justifyContent: "flex-end" }}>
            <Button variant="primary" onClick={() => mutation.mutate()} disabled={mutation.isPending || !address.trim()}>
              {mutation.isPending ? "Running diligence…" : "Run diligence"}
            </Button>
          </div>
        </Card>
        <div style={{ font: "var(--text-body-sm)", color: "var(--text-muted)", marginTop: 14, textAlign: "center" }}>
          Covers siting, interconnection, and permitting — sourced from NY GIS, HIFLD, utility hosting-capacity portals,
          FEMA, USFWS, USGS, and PAD-US.
        </div>
      </div>
    </div>
  );
}
