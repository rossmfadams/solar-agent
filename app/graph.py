from typing import TypedDict

from langgraph.graph import StateGraph, END

from app.nodes.bounds import validate_ny_bounds
from app.nodes.geocode import geocode_address
from app.nodes.parcel import resolve_parcel
from app.nodes.grid import check_grid_proximity
from app.nodes.hosting_capacity import check_hosting_capacity
from app.nodes.environmental import check_environmental_constraints
from app.nodes.terrain import check_terrain
from app.nodes.ordinance import research_local_ordinance
from app.nodes.synthesize import synthesize_memo


class HeliosState(TypedDict):
    address: str | None
    lat: float | None
    lng: float | None
    resolved_lat: float | None
    resolved_lng: float | None
    out_of_ny_bounds: bool
    parcel_id: str | None
    county: str | None
    muni: str | None
    parcel_geojson: dict | None
    parcel_fallback: bool
    # Grid / interconnection
    nearest_transmission_miles: float | None
    transmission_band: str | None
    nearest_substation_miles: float | None
    nearest_substations: list
    grid_data_available: bool
    interconnection_capacity_proxy_mw: float | None
    queue_match_rate: float | None
    nyiso_snapshot_date: str | None
    nyiso_retrieval_date: str | None
    hosting_capacity_available: bool
    # Environmental constraints
    flood_zone: str | None
    nwi_overlap: bool | None
    nwi_wetland_type: str | None
    padus_overlap: bool | None
    padus_unit_name: str | None
    environmental_data_available: bool
    # Terrain
    mean_slope_percent: float | None
    terrain_data_available: bool
    # Ordinance research — disjoint namespace so parallel fan-out is safe on a
    # plain TypedDict (no Annotated reducer needed; keys never overlap grid/hosting).
    ordinance_available: bool
    ordinance_found: bool
    ordinance_source: str | None
    ordinance_source_url: str | None
    ordinance_section: str | None
    ordinance_setbacks: str | None
    ordinance_sup: str | None
    ordinance_summary_text: str | None
    ordinance_moratorium_active: bool
    ordinance_moratorium_section: str | None
    ordinance_moratorium_quote: str | None
    ordinance_retrieval_date: str | None
    # Synthesis
    ordinance_deduction: int | None


def _build_graph():
    builder: StateGraph = StateGraph(HeliosState)
    builder.add_node("geocode_address", geocode_address)
    builder.add_node("validate_ny_bounds", validate_ny_bounds)
    builder.add_node("resolve_parcel", resolve_parcel)
    builder.add_node("check_grid_proximity", check_grid_proximity)
    builder.add_node("check_hosting_capacity", check_hosting_capacity)
    builder.add_node("check_environmental_constraints", check_environmental_constraints)
    builder.add_node("check_terrain", check_terrain)
    builder.add_node("research_local_ordinance", research_local_ordinance)
    builder.add_node("synthesize_memo", synthesize_memo)
    builder.set_entry_point("geocode_address")
    builder.add_edge("geocode_address", "validate_ny_bounds")
    # Out-of-NY sites stop here — no parcel/grid/ordinance/NYISO calls run.
    builder.add_conditional_edges(
        "validate_ny_bounds",
        lambda state: END if state.get("out_of_ny_bounds") else "resolve_parcel",
        {END: END, "resolve_parcel": "resolve_parcel"},
    )
    # Fan out from resolve_parcel: grid, environmental, terrain, and ordinance
    # run concurrently in the same superstep.  All fan in at END.
    # Each node writes to a disjoint set of state keys — concurrent writes to
    # a shared key on a plain TypedDict raise InvalidUpdateError, so the
    # namespace separation across all parallel branches is load-bearing.
    builder.add_edge("resolve_parcel", "check_grid_proximity")
    builder.add_edge("resolve_parcel", "check_environmental_constraints")
    builder.add_edge("resolve_parcel", "check_terrain")
    builder.add_edge("resolve_parcel", "research_local_ordinance")
    # Grid branch: hosting capacity depends on grid proximity result
    builder.add_edge("check_grid_proximity", "check_hosting_capacity")
    # All four parallel branches fan in to synthesize_memo (LangGraph's superstep
    # barrier ensures it only runs after all branches complete), then to END.
    builder.add_edge("check_hosting_capacity", "synthesize_memo")
    builder.add_edge("check_environmental_constraints", "synthesize_memo")
    builder.add_edge("check_terrain", "synthesize_memo")
    builder.add_edge("research_local_ordinance", "synthesize_memo")
    builder.add_edge("synthesize_memo", END)
    return builder.compile()


compiled_graph = _build_graph()
