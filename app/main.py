import json
import os
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.db import close_pool
from app.graph import compiled_graph, HeliosState
from app.map_render import fetch_map_layers, render_map
from app.models import ScreenRequest, build_memo
from app.screens_store import get_screen, save_screen

# Friendly labels for the SSE progress feed, keyed by LangGraph node name.
NODE_LABELS = {
    "geocode_address": "Geocoding address",
    "validate_ny_bounds": "Checking service area",
    "resolve_parcel": "Resolving parcel",
    "check_grid_proximity": "Checking grid proximity",
    "check_hosting_capacity": "Checking hosting capacity",
    "check_environmental_constraints": "Checking environmental constraints",
    "check_terrain": "Checking terrain",
    "research_local_ordinance": "Researching town ordinance",
    "synthesize_memo": "Synthesizing memo",
}

# Nodes that can degrade gracefully ("unable to verify") map to the state key
# that flags it. Nodes not listed here always complete in the "done" state.
DEGRADED_FLAGS = {
    "check_grid_proximity": "grid_data_available",
    "check_hosting_capacity": "hosting_capacity_available",
    "check_environmental_constraints": "environmental_data_available",
    "check_terrain": "terrain_data_available",
}


def _node_status(node: str, update: dict) -> str:
    # Mirrors _build_ordinance_summary's condition: a completed search that
    # found nothing still renders "unable to verify" in the memo, so the
    # step feed should surface it as a warning, not a plain done.
    if node == "research_local_ordinance":
        found = update.get("ordinance_available") and update.get("ordinance_found")
        return "done" if found else "warning"

    flag = DEGRADED_FLAGS.get(node)
    if flag is None:
        return "done"
    return "done" if update.get(flag) else "warning"


NY_BOUNDS_MESSAGE = "Helios currently only covers New York State sites — try an address in NY"


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_pool()


app = FastAPI(title="Helios", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


def _initial_state(request: ScreenRequest) -> HeliosState:
    return {
        "address": request.address,
        "lat": request.lat,
        "lng": request.lng,
        "resolved_lat": None,
        "resolved_lng": None,
        "out_of_ny_bounds": False,
        "parcel_id": None,
        "county": None,
        "muni": None,
        "parcel_geojson": None,
        "parcel_fallback": False,
        "interconnection_capacity_proxy_mw": None,
        "queue_match_rate": None,
        "nyiso_snapshot_date": None,
        "nyiso_retrieval_date": None,
        "hosting_capacity_available": False,
    }


@app.post("/screen")
async def screen(request: ScreenRequest):
    try:
        request.validate_input()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    site_id = uuid4()
    final_state = await compiled_graph.ainvoke(_initial_state(request))

    if final_state.get("out_of_ny_bounds"):
        raise HTTPException(status_code=422, detail=NY_BOUNDS_MESSAGE)

    memo = build_memo(final_state)
    memo.interactive_map = {"site_id": str(site_id), "url": f"/screen/{site_id}"}

    await save_screen(site_id, final_state, memo.model_dump())

    result = memo.model_dump()
    result["site_id"] = str(site_id)
    return result


@app.post("/screen/stream")
async def screen_stream(request: ScreenRequest):
    try:
        request.validate_input()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    async def event_source():
        site_id = uuid4()
        state: dict = dict(_initial_state(request))

        async for update in compiled_graph.astream(state, stream_mode="updates"):
            for node, node_update in update.items():
                state.update(node_update)

                if node == "geocode_address" and state.get("resolved_lat") is None:
                    yield _sse({
                        "type": "error",
                        "node": node,
                        "label": NODE_LABELS.get(node, node),
                        "message": "Could not resolve the address to a location",
                    })
                    return

                if node == "validate_ny_bounds" and state.get("out_of_ny_bounds"):
                    yield _sse({
                        "type": "error",
                        "node": node,
                        "label": NODE_LABELS.get(node, node),
                        "message": NY_BOUNDS_MESSAGE,
                    })
                    return

                # synthesize_memo has four converging edges (one per parallel
                # branch) and LangGraph fires it once per incoming edge, not
                # once after all have joined — so it can report "done" before
                # a sibling branch has finished. Its real completion is the
                # final memo event below, so skip the progress event here.
                if node == "synthesize_memo":
                    continue

                yield _sse({
                    "type": "node",
                    "node": node,
                    "label": NODE_LABELS.get(node, node),
                    "status": _node_status(node, node_update),
                })

        memo = build_memo(state)
        memo.interactive_map = {"site_id": str(site_id), "url": f"/screen/{site_id}"}
        await save_screen(site_id, state, memo.model_dump())

        result = memo.model_dump()
        result["site_id"] = str(site_id)
        yield _sse({"type": "memo", "memo": result})

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/screen/{site_id}/memo")
async def get_screen_memo(site_id: str):
    row = await get_screen(site_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Screen not found")

    return row["memo"]


@app.get("/screen/{site_id}")
async def get_screen_map(site_id: str):
    row = await get_screen(site_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Screen not found")

    layers = await fetch_map_layers(
        row.get("parcel_geojson"),
        row.get("resolved_lat"),
        row.get("resolved_lng"),
    )
    html = render_map(layers, bool(row.get("parcel_fallback", False)))
    return HTMLResponse(html)


# Mounted last so it only handles paths not matched by the API routes above.
# Only present when the frontend has been built (e.g. in the Docker image); absent in CI/test runs.
if os.path.isdir("frontend/dist"):
    app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="spa")
