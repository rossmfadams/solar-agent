import json
import uuid

from app.db import get_pool

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS screens (
    site_id         UUID PRIMARY KEY,
    address         TEXT,
    resolved_lat    DOUBLE PRECISION,
    resolved_lng    DOUBLE PRECISION,
    parcel_id       TEXT,
    parcel_geojson  JSONB,
    parcel_fallback BOOLEAN NOT NULL DEFAULT FALSE,
    memo            JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""

_INSERT = """
INSERT INTO screens (site_id, address, resolved_lat, resolved_lng, parcel_id, parcel_geojson, parcel_fallback, memo)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
ON CONFLICT (site_id) DO NOTHING
"""


async def save_screen(site_id: uuid.UUID, state: dict, memo_dict: dict) -> bool:
    try:
        pool = await get_pool()
    except RuntimeError:
        return False

    parcel_geojson = state.get("parcel_geojson")
    if parcel_geojson is not None and not isinstance(parcel_geojson, str):
        parcel_geojson = json.dumps(parcel_geojson)

    try:
        async with pool.acquire() as conn:
            await conn.execute(_CREATE_TABLE)
            await conn.execute(
                _INSERT,
                site_id,
                state.get("address"),
                state.get("resolved_lat"),
                state.get("resolved_lng"),
                state.get("parcel_id"),
                parcel_geojson,
                bool(state.get("parcel_fallback", False)),
                json.dumps(memo_dict),
            )
    except Exception:
        return False

    return True


async def get_screen(site_id: str) -> dict | None:
    try:
        pool = await get_pool()
    except RuntimeError:
        return None

    try:
        parsed_id = uuid.UUID(site_id)
    except (ValueError, AttributeError):
        return None

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM screens WHERE site_id = $1", parsed_id
            )
    except Exception:
        return None

    if row is None:
        return None

    result = dict(row)
    if result.get("parcel_geojson") and isinstance(result["parcel_geojson"], str):
        result["parcel_geojson"] = json.loads(result["parcel_geojson"])
    if result.get("memo") and isinstance(result["memo"], str):
        result["memo"] = json.loads(result["memo"])
    return result
