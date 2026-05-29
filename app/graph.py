from typing import TypedDict

from langgraph.graph import StateGraph, END

from app.nodes.geocode import geocode_address
from app.nodes.parcel import resolve_parcel
from app.nodes.grid import check_grid_proximity
from app.nodes.hosting_capacity import check_hosting_capacity


class HeliosState(TypedDict):
    address: str | None
    lat: float | None
    lng: float | None
    resolved_lat: float | None
    resolved_lng: float | None
    parcel_id: str | None
    county: str | None
    muni: str | None
    parcel_geojson: dict | None
    parcel_fallback: bool
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


def _build_graph():
    builder: StateGraph = StateGraph(HeliosState)
    builder.add_node("geocode_address", geocode_address)
    builder.add_node("resolve_parcel", resolve_parcel)
    builder.add_node("check_grid_proximity", check_grid_proximity)
    builder.add_node("check_hosting_capacity", check_hosting_capacity)
    builder.set_entry_point("geocode_address")
    builder.add_edge("geocode_address", "resolve_parcel")
    builder.add_edge("resolve_parcel", "check_grid_proximity")
    builder.add_edge("check_grid_proximity", "check_hosting_capacity")
    builder.add_edge("check_hosting_capacity", END)
    return builder.compile()


compiled_graph = _build_graph()
