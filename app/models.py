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


class Memo(BaseModel):
    header: MemoHeader
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


def _build_hard_disqualifiers(state: dict) -> list[HardDisqualifier] | str:
    if not state.get("environmental_data_available"):
        return UNABLE_TO_VERIFY

    today = date.today().isoformat()
    disqualifiers: list[HardDisqualifier] = []

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

    return disqualifiers


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
        interconnection=_build_interconnection(state),
        environmental=_build_environmental(state),
        terrain=_build_terrain(state),
        hard_disqualifiers=_build_hard_disqualifiers(state),
    )
