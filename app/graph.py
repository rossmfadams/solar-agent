from typing import TypedDict

from langgraph.graph import StateGraph, END

from app.nodes.geocode import geocode_address
from app.nodes.parcel import resolve_parcel
from app.nodes.grid import check_grid_proximity


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


def _build_graph():
    builder: StateGraph = StateGraph(HeliosState)
    builder.add_node("geocode_address", geocode_address)
    builder.add_node("resolve_parcel", resolve_parcel)
    builder.add_node("check_grid_proximity", check_grid_proximity)
    builder.set_entry_point("geocode_address")
    builder.add_edge("geocode_address", "resolve_parcel")
    builder.add_edge("resolve_parcel", "check_grid_proximity")
    builder.add_edge("check_grid_proximity", END)
    return builder.compile()


compiled_graph = _build_graph()
