from app.db import get_pool

_METERS_PER_MILE = 1609.344
_TEN_MILES_M = 10 * _METERS_PER_MILE

_DEGRADED = {
    "interconnection_capacity_proxy_mw": None,
    "queue_match_rate": None,
    "nyiso_snapshot_date": None,
    "nyiso_retrieval_date": None,
    "hosting_capacity_available": False,
}

# Sum summer MW from nyiso_queue rows whose geometry falls within 10 miles of
# any of the given substation IDs.  Also breaks out county-fallback MW so the
# caller can surface a match-rate metric.
_QUEUE_QUERY = """
SELECT
    COALESCE(SUM(q.summer_mw) FILTER (
        WHERE q.summer_mw IS NOT NULL AND q.summer_mw::text != 'NaN'
    ), 0)                                                                     AS total_mw,
    COALESCE(SUM(q.summer_mw) FILTER (
        WHERE q.match_method = 'county'
          AND q.summer_mw IS NOT NULL AND q.summer_mw::text != 'NaN'
    ), 0)                                                                     AS county_mw,
    COUNT(*)                                                                  AS n_projects
FROM nyiso_queue q
WHERE q.geom IS NOT NULL
  AND EXISTS (
    SELECT 1 FROM substations s
    WHERE  s.id = ANY($1::bigint[])
    AND    ST_DWithin(q.geom::geography, s.geom::geography, $2)
)
"""


async def check_hosting_capacity(state: dict) -> dict:
    # Requires the nearest_substations list populated by check_grid_proximity.
    if not state.get("grid_data_available"):
        return _DEGRADED

    nearest_substations: list[dict] = state.get("nearest_substations") or []
    if not nearest_substations:
        return _DEGRADED

    sub_ids = [s["id"] for s in nearest_substations]

    try:
        pool = await get_pool()
    except RuntimeError:
        return _DEGRADED

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(_QUEUE_QUERY, sub_ids, _TEN_MILES_M)

            if row is None:
                return _DEGRADED

            total_mw: float = float(row["total_mw"])
            county_mw: float = float(row["county_mw"])

            # Snapshot / retrieval dates come from the table itself so the
            # Citation always reflects the actual loaded data.
            meta = await conn.fetchrow(
                "SELECT snapshot_date, retrieved_at FROM nyiso_queue LIMIT 1"
            )
    except Exception:
        return _DEGRADED

    if meta is None:
        # Table is empty — NYISO data not loaded yet; degrade gracefully.
        return _DEGRADED

    # Match rate: fraction of total_mw geolocated via substation name (not county).
    if total_mw > 0:
        match_rate = round(1.0 - county_mw / total_mw, 3)
    else:
        match_rate = 1.0  # no queued MW at all → not meaningful, but non-null

    return {
        "interconnection_capacity_proxy_mw": round(total_mw),
        "queue_match_rate": match_rate,
        "nyiso_snapshot_date": meta["snapshot_date"].isoformat() if meta["snapshot_date"] else None,
        "nyiso_retrieval_date": meta["retrieved_at"].isoformat() if meta["retrieved_at"] else None,
        "hosting_capacity_available": True,
    }
