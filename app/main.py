from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.db import close_pool
from app.graph import compiled_graph, HeliosState
from app.map_render import fetch_map_layers, render_map
from app.models import ScreenRequest, build_memo
from app.screens_store import get_screen, save_screen


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_pool()


app = FastAPI(title="Helios", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/screen")
async def screen(request: ScreenRequest):
    try:
        request.validate_input()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    site_id = uuid4()

    initial_state: HeliosState = {
        "address": request.address,
        "lat": request.lat,
        "lng": request.lng,
        "resolved_lat": None,
        "resolved_lng": None,
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

    final_state = await compiled_graph.ainvoke(initial_state)
    memo = build_memo(final_state)
    memo.interactive_map = {"site_id": str(site_id), "url": f"/screen/{site_id}"}

    await save_screen(site_id, final_state, memo.model_dump())

    result = memo.model_dump()
    result["site_id"] = str(site_id)
    return result


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
app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="spa")
