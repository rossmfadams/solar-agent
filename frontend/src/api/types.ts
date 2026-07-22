export const UNABLE_TO_VERIFY = "unable to verify" as const;
export type Unverified = typeof UNABLE_TO_VERIFY;

export interface Citation {
  source: string;
  reference: string;
  retrieval_date: string;
}

export interface MemoHeader {
  address: string | null;
  lat: number | null;
  lng: number | null;
  parcel_id: string | null;
  county: string | null;
  municipality: string | null;
  parcel_fallback: boolean;
  fallback_note: string | null;
}

export interface ScoreComponent {
  dimension: string;
  raw: unknown;
  deduction: number;
  note: string | null;
}

export interface Viability {
  score: number;
  stars: number;
  label: string;
  hard_disqualified: boolean;
  breakdown: ScoreComponent[];
}

export interface HardDisqualifier {
  constraint: string;
  citation: Citation;
}

export interface Constraint {
  constraint: string;
  impact: number;
  citation: Citation;
}

export interface SubstationProximity {
  id: number | string;
  name: string | null;
  miles: number;
}

export interface Interconnection {
  nearest_transmission_miles: number;
  transmission_band: string;
  nearest_substation_miles: number;
  nearest_substations: SubstationProximity[];
  interconnection_capacity_proxy_mw: number | null;
  queue_match_rate: number | null;
  citations: Citation[];
}

export interface Environmental {
  flood_zone: string;
  nwi_overlap: boolean;
  nwi_wetland_type: string | null;
  padus_overlap: boolean;
  padus_unit_name: string | null;
  citations: Citation[];
}

export interface Terrain {
  mean_slope_percent: number;
  citations: Citation[];
}

export interface Moratorium {
  active: boolean;
  section: string | null;
  quote: string | null;
}

export interface OrdinanceSummary {
  source: string;
  section: string | null;
  setbacks: string | null;
  sup_requirements: string | null;
  summary: string | null;
  moratorium: Moratorium | null;
  citation: Citation;
}

export interface InteractiveMap {
  site_id: string;
  url: string;
}

export interface Memo {
  header: MemoHeader;
  viability: Viability | Unverified;
  hard_disqualifiers: HardDisqualifier[] | Unverified;
  top_3_constraints: Constraint[] | Unverified;
  interconnection: Interconnection | Unverified;
  environmental: Environmental | Unverified;
  terrain: Terrain | Unverified;
  ordinance_summary: OrdinanceSummary | Unverified;
  interactive_map: InteractiveMap | Unverified;
  site_id: string;
}

export function isVerified<T>(value: T | Unverified): value is T {
  return value !== UNABLE_TO_VERIFY;
}

export interface ScreenRequest {
  address?: string;
  lat?: number;
  lng?: number;
}
