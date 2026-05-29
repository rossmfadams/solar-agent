from typing import TypedDict

from langgraph.graph import StateGraph, END

from app.nodes.geocode import geocode_address
from app.nodes.parcel import resolve_parcel


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


def _build_graph():
    builder: StateGraph = StateGraph(HeliosState)
    builder.add_node("geocode_address", geocode_address)
    builder.add_node("resolve_parcel", resolve_parcel)
    builder.set_entry_point("geocode_address")
    builder.add_edge("geocode_address", "resolve_parcel")
    builder.add_edge("resolve_parcel", END)
    return builder.compile()


compiled_graph = _build_graph()
