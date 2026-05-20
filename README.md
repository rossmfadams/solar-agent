# Helios

> AI agent for early-stage site diligence on utility-scale solar projects in New York State.

Given an address or coordinates, Helios produces a structured **viability memo** — covering siting constraints, interconnection availability, and permitting feasibility — in under 90 seconds. Work that typically takes a junior analyst 30–60 minutes per site.

## Status

Under active development. See [`docs/01_helios_prd.md`](docs/01_helios_prd.md) for the full product spec.

## What it does

1. Geocodes the input and resolves it to a NY parcel polygon
2. Checks proximity to transmission lines and substations (HIFLD)
3. Estimates interconnection congestion from the NYISO queue
4. Flags environmental constraints — flood zones (FEMA), wetlands (NWI), protected lands (PAD-US)
5. Computes mean parcel slope from USGS 3DEP elevation data
6. Researches the town's solar zoning ordinance and moratorium status
7. Synthesizes all signals into a **Viability Score** (0–100) and a cited memo with an interactive map

## Tech stack

- **Backend:** FastAPI + Python 3.11+, PostgreSQL 16 + PostGIS
- **Agent:** LangGraph state graph
- **LLM:** Anthropic Claude (Sonnet for reasoning, Haiku for classification)
- **Frontend:** Server-rendered HTML + Folium maps
- **Infra:** Docker, deployable to Fly.io or Render

## Docs

- [PRD](docs/01_helios_prd.md)
- [Domain language](CONTEXT.md)
- [ADRs](docs/adr/)
