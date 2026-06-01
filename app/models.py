from __future__ import annotations

from datetime import date
from typing import Any, TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from app.graph import HeliosState

UNABLE_TO_VERIFY = "unable to verify"


class MemoHeader(BaseModel):
    address: str | None = None
    lat: float | None = None
    lng: float | None = None
    parcel_id: str | None = None
    county: str | None = None
    municipality: str | None = None
    parcel_fallback: bool = False
    fallback_note: str | None = None


class Citation(BaseModel):
    source: str
    reference: str
    retrieval_date: str


class SubstationProximity(BaseModel):
    id: int | str
    name: str | None
    miles: float


class Interconnection(BaseModel):
    nearest_transmission_miles: float
    transmission_band: str
    nearest_substation_miles: float
    nearest_substations: list[SubstationProximity]
    # Interconnection Capacity (proxy) — total MW queued in the NYISO
    # interconnection queue within 10 miles of nearby substations.
    # Optional: populated only when the NYISO queue table has been loaded.
    interconnection_capacity_proxy_mw: float | None = None
    queue_match_rate: float | None = None
    citations: list[Citation]


class Environmental(BaseModel):
    flood_zone: str
    nwi_overlap: bool
    nwi_wetland_type: str | None
    padus_overlap: bool
    padus_unit_name: str | None
    citations: list[Citation]


class Terrain(BaseModel):
    mean_slope_percent: float
    citations: list[Citation]


class HardDisqualifier(BaseModel):
    constraint: str
    citation: Citation


class Moratorium(BaseModel):
    active: bool
    section: str | None = None
    quote: str | None = None


class OrdinanceSummary(BaseModel):
    source: str
    section: str | None = None
    setbacks: str | None = None
    sup_requirements: str | None = None
    summary: str | None = None
    moratorium: Moratorium | None = None
    citation: Citation


class ScoreComponent(BaseModel):
    dimension: str
    raw: Any
    deduction: int
    note: str | None = None


class Constraint(BaseModel):
    constraint: str
    impact: int
    citation: Citation


class Viability(BaseModel):
    score: int
    stars: int
    label: str
    hard_disqualified: bool
    breakdown: list[ScoreComponent]


class Memo(BaseModel):
    header: MemoHeader
    viability: Any = UNABLE_TO_VERIFY
    hard_disqualifiers: Any = UNABLE_TO_VERIFY
    top_3_constraints: Any = UNABLE_TO_VERIFY
    interconnection: Any = UNABLE_TO_VERIFY
    environmental: Any = UNABLE_TO_VERIFY
    terrain: Any = UNABLE_TO_VERIFY
    ordinance_summary: Any = UNABLE_TO_VERIFY
    interactive_map: Any = UNABLE_TO_VERIFY


class ScreenRequest(BaseModel):
    address: str | None = None
    lat: float | None = None
    lng: float | None = None

    def validate_input(self) -> None:
        if self.address is None and (self.lat is None or self.lng is None):
            raise ValueError("Provide 'address' or both 'lat' and 'lng'")


def _build_interconnection(state: dict) -> Interconnection | str:
    if not state.get("grid_data_available"):
        return UNABLE_TO_VERIFY

    citations: list[Citation] = [
        Citation(
            source="HIFLD",
            reference="Electric Power Transmission Lines; Electric Substations",
            retrieval_date=date.today().isoformat(),
        )
    ]

    proxy_mw: float | None = None
    match_rate: float | None = None

    if state.get("hosting_capacity_available"):
        proxy_mw = state.get("interconnection_capacity_proxy_mw")
        match_rate = state.get("queue_match_rate")
        snapshot = state.get("nyiso_snapshot_date") or "unknown"
        retrieval = state.get("nyiso_retrieval_date") or date.today().isoformat()
        # match_rate embedded in reference so it's visible in the Citation
        pct = f"{round((match_rate or 0) * 100):.0f}%" if match_rate is not None else "n/a"
        citations.append(
            Citation(
                source="NYISO Interconnection Queue",
                reference=f"Queue snapshot {snapshot}; {pct} of MW geolocated by substation name",
                retrieval_date=retrieval,
            )
        )

    return Interconnection(
        nearest_transmission_miles=state["nearest_transmission_miles"],
        transmission_band=state["transmission_band"],
        nearest_substation_miles=state["nearest_substation_miles"],
        nearest_substations=[
            SubstationProximity(**s) for s in state["nearest_substations"]
        ],
        interconnection_capacity_proxy_mw=proxy_mw,
        queue_match_rate=match_rate,
        citations=citations,
    )


def _build_environmental(state: dict) -> Environmental | str:
    if not state.get("environmental_data_available"):
        return UNABLE_TO_VERIFY

    today = date.today().isoformat()
    citations: list[Citation] = [
        Citation(
            source="FEMA National Flood Hazard Layer",
            reference="S_Fld_Haz_Ar — Special Flood Hazard Area polygons",
            retrieval_date=today,
        ),
        Citation(
            source="USFWS National Wetlands Inventory",
            reference="Wetlands polygon layer",
            retrieval_date=today,
        ),
        Citation(
            source="USGS Protected Areas Database (PAD-US)",
            reference="PAD-US Combined layer — Fee, Designation, Easement, Proclamation",
            retrieval_date=today,
        ),
    ]

    return Environmental(
        flood_zone=state.get("flood_zone") or "none",
        nwi_overlap=bool(state.get("nwi_overlap")),
        nwi_wetland_type=state.get("nwi_wetland_type"),
        padus_overlap=bool(state.get("padus_overlap")),
        padus_unit_name=state.get("padus_unit_name"),
        citations=citations,
    )


def _build_terrain(state: dict) -> Terrain | str:
    if not state.get("terrain_data_available"):
        return UNABLE_TO_VERIFY

    return Terrain(
        mean_slope_percent=state["mean_slope_percent"],
        citations=[
            Citation(
                source="USGS 3D Elevation Program (3DEP)",
                reference="1/3 arc-second (~10m) Digital Elevation Model — New York",
                retrieval_date=date.today().isoformat(),
            )
        ],
    )


# ---------------------------------------------------------------------------
# Scoring helpers — pure functions, no I/O, fully unit-testable
# ---------------------------------------------------------------------------

def _transmission_deduction(miles: float) -> int:
    if miles <= 1:
        return 0
    if miles <= 5:
        return -10
    if miles <= 10:
        return -20
    return -35


def _queue_deduction(mw: float | None) -> int:
    if mw is None:
        return 0
    if mw < 500:
        return 0
    if mw <= 1500:
        return -10
    return -20


def _flood_deduction(zone: str | None) -> int:
    if not zone:
        return 0
    z = zone.upper()
    if any(code in z for code in ("AE", "AH", "AO", "VE")):
        return -20
    if "X (SHADED)" in z:
        return -10
    return 0


def _slope_deduction(pct: float | None) -> int:
    if pct is None:
        return 0
    if pct <= 5:
        return 0
    if pct <= 15:
        return -8
    return -15


def _stars_and_label(score: int) -> tuple[int, str]:
    if score == 0:
        return 0, "Hard Disqualified"
    if score <= 25:
        return 1, "Very Low"
    if score <= 50:
        return 2, "Low"
    if score <= 70:
        return 3, "Moderate"
    if score <= 85:
        return 4, "Good"
    return 5, "Strong"


# ---------------------------------------------------------------------------
# Hard disqualifiers — extended to include active moratorium
# ---------------------------------------------------------------------------

def _build_hard_disqualifiers(state: dict) -> list[HardDisqualifier] | str:
    env_available = bool(state.get("environmental_data_available"))
    ord_available = bool(state.get("ordinance_found"))

    if not env_available and not ord_available:
        return UNABLE_TO_VERIFY

    today = date.today().isoformat()
    disqualifiers: list[HardDisqualifier] = []

    if env_available:
        if state.get("nwi_overlap"):
            wetland_type = state.get("nwi_wetland_type") or "wetland"
            disqualifiers.append(
                HardDisqualifier(
                    constraint=f"NWI wetland overlap ({wetland_type})",
                    citation=Citation(
                        source="USFWS National Wetlands Inventory",
                        reference="Wetlands polygon layer",
                        retrieval_date=today,
                    ),
                )
            )

        if state.get("padus_overlap"):
            unit_name = state.get("padus_unit_name") or "protected area"
            disqualifiers.append(
                HardDisqualifier(
                    constraint=f"PAD-US protected lands overlap ({unit_name})",
                    citation=Citation(
                        source="USGS Protected Areas Database (PAD-US)",
                        reference="PAD-US Combined layer — Fee, Designation, Easement, Proclamation",
                        retrieval_date=today,
                    ),
                )
            )

    if state.get("ordinance_moratorium_active"):
        section = state.get("ordinance_moratorium_section") or "moratorium provision"
        retrieval = state.get("ordinance_retrieval_date") or today
        disqualifiers.append(
            HardDisqualifier(
                constraint=f"Active solar permit moratorium — {section}",
                citation=Citation(
                    source=state.get("ordinance_source") or "unknown",
                    reference=section,
                    retrieval_date=retrieval,
                ),
            )
        )

    return disqualifiers


def _build_ordinance_summary(state: dict) -> OrdinanceSummary | str:
    if not state.get("ordinance_available") or not state.get("ordinance_found"):
        return UNABLE_TO_VERIFY

    moratorium: Moratorium | None = None
    if state.get("ordinance_moratorium_active"):
        moratorium = Moratorium(
            active=True,
            section=state.get("ordinance_moratorium_section"),
            quote=state.get("ordinance_moratorium_quote"),
        )

    retrieval = state.get("ordinance_retrieval_date") or date.today().isoformat()
    reference = (
        state.get("ordinance_section")
        or state.get("ordinance_source_url")
        or "solar zoning"
    )
    citation = Citation(
        source=state.get("ordinance_source") or "unknown",
        reference=reference,
        retrieval_date=retrieval,
    )

    return OrdinanceSummary(
        source=state.get("ordinance_source") or "unknown",
        section=state.get("ordinance_section"),
        setbacks=state.get("ordinance_setbacks"),
        sup_requirements=state.get("ordinance_sup"),
        summary=state.get("ordinance_summary_text"),
        moratorium=moratorium,
        citation=citation,
    )


# ---------------------------------------------------------------------------
# Viability score — deterministic synthesis of all available signals
# ---------------------------------------------------------------------------

def _build_viability(state: dict) -> Viability:
    today = date.today().isoformat()

    disqualifiers = _build_hard_disqualifiers(state)
    if isinstance(disqualifiers, list) and len(disqualifiers) > 0:
        breakdown = [
            ScoreComponent(
                dimension=d.constraint,
                raw=True,
                deduction=-100,
                note="hard disqualifier",
            )
            for d in disqualifiers
        ]
        return Viability(
            score=0,
            stars=0,
            label="Hard Disqualified",
            hard_disqualified=True,
            breakdown=breakdown,
        )

    components: list[ScoreComponent] = []
    score = 100

    # Transmission distance
    if state.get("grid_data_available"):
        miles = state.get("nearest_transmission_miles") or 0.0
        ded = _transmission_deduction(miles)
        components.append(ScoreComponent(dimension="transmission", raw=miles, deduction=ded))
        score += ded
    else:
        components.append(ScoreComponent(dimension="transmission", raw=None, deduction=0, note="unable to verify"))

    # Interconnection queue congestion
    if state.get("hosting_capacity_available"):
        mw = state.get("interconnection_capacity_proxy_mw")
        ded = _queue_deduction(mw)
        components.append(ScoreComponent(dimension="interconnection_queue", raw=mw, deduction=ded))
        score += ded
    else:
        components.append(ScoreComponent(dimension="interconnection_queue", raw=None, deduction=0, note="unable to verify"))

    # Flood zone
    if state.get("environmental_data_available"):
        zone = state.get("flood_zone")
        ded = _flood_deduction(zone)
        components.append(ScoreComponent(dimension="flood_zone", raw=zone, deduction=ded))
        score += ded
    else:
        components.append(ScoreComponent(dimension="flood_zone", raw=None, deduction=0, note="unable to verify"))

    # Terrain slope
    if state.get("terrain_data_available"):
        pct = state.get("mean_slope_percent")
        ded = _slope_deduction(pct)
        components.append(ScoreComponent(dimension="slope", raw=pct, deduction=ded))
        score += ded
    else:
        components.append(ScoreComponent(dimension="slope", raw=None, deduction=0, note="unable to verify"))

    # Ordinance
    if state.get("ordinance_found"):
        ord_ded = state.get("ordinance_deduction") or 0
        components.append(ScoreComponent(dimension="ordinance", raw=state.get("ordinance_summary_text"), deduction=ord_ded))
        score += ord_ded
    else:
        components.append(ScoreComponent(dimension="ordinance", raw=None, deduction=0, note="unable to verify"))

    score = max(1, min(100, score))
    stars, label = _stars_and_label(score)

    return Viability(
        score=score,
        stars=stars,
        label=label,
        hard_disqualified=False,
        breakdown=components,
    )


def _build_top_3_constraints(state: dict) -> list[Constraint] | str:
    any_signal = (
        state.get("grid_data_available")
        or state.get("hosting_capacity_available")
        or state.get("environmental_data_available")
        or state.get("terrain_data_available")
        or state.get("ordinance_found")
    )
    if not any_signal:
        return UNABLE_TO_VERIFY

    today = date.today().isoformat()

    disqualifiers = _build_hard_disqualifiers(state)
    if isinstance(disqualifiers, list) and len(disqualifiers) > 0:
        return [
            Constraint(
                constraint=d.constraint,
                impact=100,
                citation=d.citation,
            )
            for d in disqualifiers
        ][:3]

    constraints: list[Constraint] = []

    if state.get("grid_data_available"):
        miles = state.get("nearest_transmission_miles") or 0.0
        ded = _transmission_deduction(miles)
        if ded < 0:
            constraints.append(
                Constraint(
                    constraint=f"Transmission distance {miles:.1f} miles",
                    impact=abs(ded),
                    citation=Citation(
                        source="HIFLD",
                        reference="Electric Power Transmission Lines",
                        retrieval_date=today,
                    ),
                )
            )

    if state.get("hosting_capacity_available"):
        mw = state.get("interconnection_capacity_proxy_mw")
        ded = _queue_deduction(mw)
        if ded < 0:
            retrieval = state.get("nyiso_retrieval_date") or today
            constraints.append(
                Constraint(
                    constraint=f"Interconnection queue congestion ({mw} MW within 10 miles)",
                    impact=abs(ded),
                    citation=Citation(
                        source="NYISO Interconnection Queue",
                        reference=f"Queue snapshot {state.get('nyiso_snapshot_date') or 'unknown'}",
                        retrieval_date=retrieval,
                    ),
                )
            )

    if state.get("environmental_data_available"):
        zone = state.get("flood_zone")
        ded = _flood_deduction(zone)
        if ded < 0:
            constraints.append(
                Constraint(
                    constraint=f"Flood zone {zone}",
                    impact=abs(ded),
                    citation=Citation(
                        source="FEMA National Flood Hazard Layer",
                        reference="S_Fld_Haz_Ar — Special Flood Hazard Area polygons",
                        retrieval_date=today,
                    ),
                )
            )

    if state.get("terrain_data_available"):
        pct = state.get("mean_slope_percent")
        ded = _slope_deduction(pct)
        if ded < 0:
            constraints.append(
                Constraint(
                    constraint=f"Terrain slope {pct:.1f}%",
                    impact=abs(ded),
                    citation=Citation(
                        source="USGS 3D Elevation Program (3DEP)",
                        reference="1/3 arc-second (~10m) Digital Elevation Model — New York",
                        retrieval_date=today,
                    ),
                )
            )

    if state.get("ordinance_found"):
        ord_ded = state.get("ordinance_deduction") or 0
        if ord_ded < 0:
            retrieval = state.get("ordinance_retrieval_date") or today
            constraints.append(
                Constraint(
                    constraint=f"Local ordinance constraints ({state.get('ordinance_source') or 'ordinance'})",
                    impact=abs(ord_ded),
                    citation=Citation(
                        source=state.get("ordinance_source") or "unknown",
                        reference=state.get("ordinance_section") or state.get("ordinance_source_url") or "solar zoning",
                        retrieval_date=retrieval,
                    ),
                )
            )

    constraints.sort(key=lambda c: c.impact, reverse=True)
    return constraints[:3]


def build_memo(state: dict) -> Memo:
    fallback = state.get("parcel_fallback", False)
    if fallback and state.get("parcel_id"):
        fallback_note = (
            "No parcel polygon found at coordinates; "
            "analysis based on nearest parcel within 500m buffer"
        )
    elif fallback:
        fallback_note = (
            "No parcel polygon found at coordinates; "
            "500m buffer search also returned no results"
        )
    else:
        fallback_note = None

    header = MemoHeader(
        address=state.get("address"),
        lat=state.get("resolved_lat"),
        lng=state.get("resolved_lng"),
        parcel_id=state.get("parcel_id"),
        county=state.get("county"),
        municipality=state.get("muni"),
        parcel_fallback=fallback,
        fallback_note=fallback_note,
    )
    return Memo(
        header=header,
        viability=_build_viability(state),
        interconnection=_build_interconnection(state),
        environmental=_build_environmental(state),
        terrain=_build_terrain(state),
        hard_disqualifiers=_build_hard_disqualifiers(state),
        top_3_constraints=_build_top_3_constraints(state),
        ordinance_summary=_build_ordinance_summary(state),
    )
