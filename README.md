# Helios

> AI agent for early-stage site diligence on utility-scale solar projects in New York State.

Given an address or coordinates, Helios produces a structured **viability memo** — covering siting constraints, interconnection availability, and permitting feasibility — targeting under 90 seconds per site, for work that typically takes a junior analyst 30–60 minutes.

## Status

Live at [helios.rossadams.dev](https://helios.rossadams.dev). The server scales to zero when idle, so the first page load may take a few seconds while it wakes up.

## What it does

1. Geocodes the input (OpenStreetMap Nominatim) and resolves it to a NY parcel polygon, falling back to a 500 m buffer when no parcel matches
2. Checks proximity to transmission lines and substations (HIFLD)
3. Estimates interconnection congestion from the NYISO queue
4. Flags environmental constraints — flood zones (FEMA), wetlands (NWI), protected lands (PAD-US)
5. Computes mean parcel slope from USGS 3DEP elevation data
6. Researches the town's solar zoning ordinance and moratorium status
7. Synthesizes all signals into a **Viability Score** (0–100) and a cited memo with an interactive map

## Tech stack

- **Backend:** FastAPI + Python 3.14, PostgreSQL 16 + PostGIS
- **Agent:** LangGraph state graph
- **LLM:** Anthropic Claude Sonnet 4.6, for ordinance research (server-side web search) and memo synthesis
- **Frontend:** React + Vite + TypeScript SPA served by FastAPI, with the Folium map embedded via iframe and Mapbox address autocomplete
- **Infra:** Single Docker image on Fly.io, scale-to-zero

## Docs

- [PRD](docs/01_helios_prd.md)
- [Domain language](CONTEXT.md)
- [ADRs](docs/adr/)
