import { useState } from "react";
import type {
  Constraint,
  Environmental,
  HardDisqualifier,
  Interconnection,
  Memo,
  OrdinanceSummary,
  Terrain,
} from "../api/types";
import { isVerified, UNABLE_TO_VERIFY } from "../api/types";
import { Button } from "../components/Button";
import { DimensionCard } from "../components/DimensionCard";
import { MapPanel } from "../components/MapPanel";
import { Tabs } from "../components/Tabs";
import { Tag } from "../components/Tag";
import { VerdictRating } from "../components/VerdictRating";

const DETAIL_TABS = [
  { value: "interconnection", label: "Interconnection" },
  { value: "environmental", label: "Environmental" },
  { value: "terrain", label: "Terrain" },
  { value: "ordinance", label: "Ordinance" },
];

function Unverified() {
  return <p style={{ font: "var(--text-body-md)", color: "var(--text-muted)", fontStyle: "italic" }}>{UNABLE_TO_VERIFY}</p>;
}

function InterconnectionDetail({ data }: { data: Interconnection | typeof UNABLE_TO_VERIFY }) {
  if (!isVerified(data)) return <Unverified />;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <p style={{ font: "var(--text-body-lg)", color: "var(--text-secondary)" }}>
        Nearest transmission line is {data.nearest_transmission_miles.toFixed(1)} mi away ({data.transmission_band}).
        Nearest substation is {data.nearest_substation_miles.toFixed(1)} mi away.
        {data.interconnection_capacity_proxy_mw != null &&
          ` NYISO interconnection queue within 10 mi totals ${data.interconnection_capacity_proxy_mw.toFixed(0)} MW.`}
      </p>
      <Citations items={data.citations} />
    </div>
  );
}

function EnvironmentalDetail({ data }: { data: Environmental | typeof UNABLE_TO_VERIFY }) {
  if (!isVerified(data)) return <Unverified />;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <p style={{ font: "var(--text-body-lg)", color: "var(--text-secondary)" }}>
        FEMA flood zone: {data.flood_zone}. NWI wetland overlap: {data.nwi_overlap ? `yes (${data.nwi_wetland_type ?? "unspecified"})` : "no"}.
        PAD-US protected land overlap: {data.padus_overlap ? `yes (${data.padus_unit_name ?? "unnamed unit"})` : "no"}.
      </p>
      <Citations items={data.citations} />
    </div>
  );
}

function TerrainDetail({ data }: { data: Terrain | typeof UNABLE_TO_VERIFY }) {
  if (!isVerified(data)) return <Unverified />;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <p style={{ font: "var(--text-body-lg)", color: "var(--text-secondary)" }}>
        Mean slope across the parcel is {data.mean_slope_percent.toFixed(1)}%.
      </p>
      <Citations items={data.citations} />
    </div>
  );
}

function OrdinanceDetail({ data }: { data: OrdinanceSummary | typeof UNABLE_TO_VERIFY }) {
  if (!isVerified(data)) return <Unverified />;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {data.moratorium?.active && (
        <p style={{ font: "var(--text-label-md)", color: "var(--status-danger)" }}>
          Active moratorium — {data.moratorium.section ?? "section unspecified"}
        </p>
      )}
      <p style={{ font: "var(--text-body-lg)", color: "var(--text-secondary)" }}>
        {data.summary ?? "No summary available."}
        {data.setbacks && ` Setbacks: ${data.setbacks}.`}
        {data.sup_requirements && ` SUP requirements: ${data.sup_requirements}.`}
      </p>
      <Citations items={[data.citation]} />
    </div>
  );
}

function Citations({ items }: { items: { source: string }[] }) {
  if (items.length === 0) return null;
  return (
    <div style={{ display: "flex", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
      {items.map((c, i) => (
        <Tag key={i}>{c.source}</Tag>
      ))}
    </div>
  );
}

function hardDisqualifierCard(hd: HardDisqualifier[] | typeof UNABLE_TO_VERIFY) {
  if (!isVerified(hd)) {
    return <DimensionCard label="Hard disqualifiers" status="Unable to verify" tone="warning" />;
  }
  if (hd.length === 0) {
    return <DimensionCard label="Hard disqualifiers" status="Clear" tone="success" detail="None found" />;
  }
  return (
    <DimensionCard
      label="Hard disqualifiers"
      status="Disqualified"
      tone="danger"
      detail={hd.map((d) => d.constraint).join("; ")}
    />
  );
}

function topConstraintsCard(constraints: Constraint[] | typeof UNABLE_TO_VERIFY) {
  if (!isVerified(constraints)) {
    return <DimensionCard label="Top constraints" status="Unable to verify" tone="warning" />;
  }
  if (constraints.length === 0) {
    return <DimensionCard label="Top constraints" status="None flagged" tone="success" />;
  }
  return (
    <DimensionCard
      label="Top constraints"
      status={`${constraints.length} flagged`}
      tone="warning"
      detail={constraints.map((c) => c.constraint).join("; ")}
    />
  );
}

function ordinanceStatusCard(ordinance: OrdinanceSummary | typeof UNABLE_TO_VERIFY) {
  if (!isVerified(ordinance)) {
    return <DimensionCard label="Permitting" status="Unable to verify" tone="warning" />;
  }
  if (ordinance.moratorium?.active) {
    return <DimensionCard label="Permitting" status="Moratorium active" tone="danger" />;
  }
  return <DimensionCard label="Permitting" status="No moratorium" tone="success" />;
}

export function MemoDetailScreen({ memo, onBack }: { memo: Memo; onBack: () => void }) {
  const [tab, setTab] = useState("interconnection");
  const { header } = memo;

  return (
    <div style={{ padding: 28, fontFamily: "var(--font-ui)", flex: 1, overflow: "auto" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
        <button
          onClick={onBack}
          style={{ background: "none", border: "none", color: "var(--text-tertiary)", cursor: "pointer", font: "var(--text-label-md)" }}
        >
          ← New site
        </button>
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16 }}>
        <div>
          <div style={{ font: "var(--text-eyebrow)", textTransform: "uppercase", letterSpacing: "var(--tracking-eyebrow)", color: "var(--text-muted)" }}>
            Site memo
          </div>
          <div style={{ font: "var(--text-display-md)", color: "var(--text-primary)", marginTop: 4 }}>
            {header.address ?? `${header.lat}, ${header.lng}`}
          </div>
          <div style={{ font: "var(--text-body-sm)", color: "var(--text-tertiary)", marginTop: 4 }}>
            {header.county ?? "Unknown county"} · {header.municipality ?? "Unknown municipality"}
            {header.parcel_fallback && " · parcel boundary estimated (500m buffer)"}
          </div>
        </div>
        <div style={{ background: "var(--surface-accent-soft)", border: "1px solid var(--border-accent)", borderRadius: "var(--radius-md)", padding: "12px 16px" }}>
          {isVerified(memo.viability) ? <VerdictRating score={memo.viability.score} /> : <Unverified />}
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, marginTop: 24 }}>
        {hardDisqualifierCard(memo.hard_disqualifiers)}
        {topConstraintsCard(memo.top_3_constraints)}
        {ordinanceStatusCard(memo.ordinance_summary)}
      </div>

      <div style={{ marginTop: 24 }}>
        <Tabs tabs={DETAIL_TABS} active={tab} onChange={setTab} />
        <div style={{ marginTop: 16, display: "grid", gridTemplateColumns: "1.1fr 1fr", gap: 20 }}>
          <div>
            {tab === "interconnection" && <InterconnectionDetail data={memo.interconnection} />}
            {tab === "environmental" && <EnvironmentalDetail data={memo.environmental} />}
            {tab === "terrain" && <TerrainDetail data={memo.terrain} />}
            {tab === "ordinance" && <OrdinanceDetail data={memo.ordinance_summary} />}
          </div>
          <div>
            {isVerified(memo.interactive_map) ? (
              <MapPanel url={memo.interactive_map.url} />
            ) : (
              <Unverified />
            )}
          </div>
        </div>
      </div>

      <div style={{ display: "flex", gap: 8, marginTop: 28 }}>
        <Button variant="secondary" onClick={onBack}>
          New site diligence
        </Button>
      </div>
    </div>
  );
}
