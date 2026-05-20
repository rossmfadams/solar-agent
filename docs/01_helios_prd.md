# Helios — NY Solar Site Pre-Screening Agent

**Product Requirements Document**
Version 1.0

---

## Overview

Helios is an AI agent that automates early-stage site diligence for utility-scale solar projects in New York State. Given an address or coordinates, it produces a structured viability memo covering siting constraints, interconnection availability, and permitting feasibility within roughly 90 seconds — work that typically takes a junior analyst 30 to 60 minutes per site.

## Problem

Solar developers in NY triage dozens of inbound leads per week. The vast majority get killed for binary reasons (no nearby transmission, town moratorium, wetlands, no hosting capacity) that *could* be caught quickly — but the relevant data lives across eight or more sources: NY GIS Clearinghouse for parcels, HIFLD for transmission and substations, five-plus utility ArcGIS portals for hosting capacity, FEMA for flood zones, USFWS for wetlands, USGS for terrain, PAD-US for protected lands, and town-specific zoning PDFs. The triage work is repetitive, requires light domain judgment, and is therefore a textbook automation target.

## Goals

- Reduce per-site triage from ~45 minutes to under 90 seconds
- Produce decision-quality memos with citations to every source
- Cover the three dimensions of Paces' product surface: **siting, interconnection, permitting**
- Handle batch input (CSV of sites) as a stretch goal

## Non-goals

- Late-stage diligence (Phase 1 ESA, glare studies, glint analysis, etc.)
- Legally-binding zoning interpretation
- Coverage of states outside New York
- Technologies other than solar (no wind, BESS, EV charging)
- Project finance modeling

## Target user

**Sarah, Head of Development at a 5-50MW NY-focused solar developer.** Her team receives 30-50 inbound leads/week from landowners and brokers. She wants the obvious no's killed automatically so her analysts spend time on the maybes.

## User stories

1. **Single-site screen.** Sarah pastes an address; within 90 seconds she sees a one-page memo with viability score (0-100), top 3 constraints, and an interactive map.
2. **Cited reasoning.** Every flag in the memo links back to the source data layer or document section that produced it.
3. **Ordinance summary.** The memo includes a paragraph summarizing the town's solar zoning rules (setbacks, special-use-permit requirements, any moratorium) with a link to the relevant section of the code.
4. **Batch mode (stretch).** Sarah uploads a CSV of 20 candidate sites and gets back a ranked report.

## Functional requirements

| ID | Requirement |
|----|-------------|
| F1 | Accept input as address, lat/lng, or CSV |
| F2 | Geocode input and resolve to NY parcel polygon (where available) |
| F3 | Compute distances to nearest transmission line and substation |
| F4 | Look up NYISO interconnection queue density (total MW queued within 10 miles of the 3 nearest substations) as a proxy for transmission interconnection capacity |
| F5 | Check overlap with FEMA flood zones, NWI wetlands, PAD-US protected lands |
| F6 | Compute mean slope across the parcel from USGS 3DEP elevation |
| F7 | Research and summarize the town's solar ordinance (setbacks, SUP, moratorium status) |
| F8 | Synthesize all signals into a viability score + structured memo with citations |
| F9 | Render an interactive map with parcel + all relevant overlays |
| F10 | Export memo as markdown or PDF |

## Technical architecture

**Backend:** FastAPI + Python 3.11+

**Database:** PostgreSQL 16 with PostGIS extension — stores normalized copies of HIFLD, FEMA, NWI, PAD-US layers for fast spatial queries.

**Agent orchestration:** LangGraph state graph with these tools:

- `geocode_address`
- `resolve_parcel`
- `check_grid_proximity` (transmission + substation distance)
- `check_hosting_capacity` (queries NYISO interconnection queue for MW queued within 10 miles of nearby substations)
- `check_environmental_constraints` (FEMA + NWI + PAD-US in one call)
- `check_terrain` (slope from 3DEP)
- `research_local_ordinance` (web search + PDF parsing + LLM summarization)
- `synthesize_memo`

**LLM:** Anthropic Messages API — Claude Sonnet 4.6 for main reasoning, Claude Haiku 4.5 for cheap classification subtasks.

**Frontend:** Single-page app — server-rendered HTML + Folium for the map.

**Infra:** Docker, deployable to Fly.io or Render.

## Data sources

| Source | Purpose | Format |
|--------|---------|--------|
| NY GIS Clearinghouse | Statewide parcel polygons | Shapefile / GeoJSON |
| HIFLD | Transmission lines + substations | Shapefile |
| NYISO Interconnection Queue | Transmission congestion proxy (queue MW within 10 miles of substations) | Public CSV / API |
| FEMA NFHL | Flood zones | WMS / shapefile |
| USFWS NWI | Wetlands | Shapefile |
| USGS PAD-US | Protected lands | Shapefile |
| USGS 3DEP | Elevation (for slope) | GeoTIFF raster |
| eCode360, Municode, town websites | Local zoning ordinances | HTML + PDF |
| NYSERDA Solar Guidebook | Ordinance baseline reference | PDF |

## Success criteria

- 10 hand-picked test sites (5 viable, 5 with disqualifying issues) processed correctly end-to-end
- Memo citations resolve to correct source data in 100% of cases
- p50 latency under 90 seconds per site
- Agent degrades gracefully when a data source is unavailable (returns memo with that field marked "unable to verify")

## Phased milestones

### Phase 1 — Foundation (~12 hrs)
- Repo, Docker, PostGIS up
- HIFLD transmission + substations loaded
- Geocode + parcel resolution working
- Bare-bones LangGraph with 2 tools

### Phase 2 — Geospatial layers (~15 hrs)
- FEMA, NWI, PAD-US ingested
- Slope calculation from 3DEP
- Folium map rendering with overlays

### Phase 3 — Hosting capacity (~10 hrs)
- ArcGIS REST integration for 2-3 priority utilities
- Substation-to-capacity matching logic

### Phase 4 — Ordinance research agent (~12 hrs)
- Web search + PDF parse subgraph
- Cached results for ~10 demo towns

### Phase 5 — Synthesis + polish (~8 hrs)
- Memo template + scoring logic
- README, demo video, eval results

**Total: ~55-60 hours**

## Risks & mitigations

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Ordinance unavailable for some towns | High | Cache 10-15 known towns for demo; agent returns "unable to verify" otherwise |
| Hosting capacity APIs change format mid-build | Medium | Scope to 2-3 utilities (ConEd, National Grid, NYSEG); document the integration as extensible |
| Slope calculation precision | Low | Use parcel-mean slope; document the simplification |
| Agent hallucinates ordinance details | Medium | Require citation in agent output schema; eval against known towns |
| Scope creep | High | Treat F10 (PDF export) and batch mode as stretch goals only |

## Out of scope (explicit)

Phase 1 environmental assessment · Title/ownership lookup · Project finance · Lease comp data · Non-NY states · Battery storage · Wind · EV charging · Sub-utility-scale (< 1MW) projects
