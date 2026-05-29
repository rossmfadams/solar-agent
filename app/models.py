from __future__ import annotations

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
    return Memo(header=header)
