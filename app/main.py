from fastapi import FastAPI

app = FastAPI(title="Helios")


@app.get("/health")
async def health():
    return {"status": "ok"}
