from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from app.db import close_pool
from app.graph import compiled_graph, HeliosState
from app.models import ScreenRequest, build_memo


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
    }

    final_state = await compiled_graph.ainvoke(initial_state)
    memo = build_memo(final_state)
    return memo.model_dump()
