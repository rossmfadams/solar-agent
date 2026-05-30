# ADR 0003 — Geospatial Sources: Environmental Constraints and Terrain Slope

**Date:** 2026-05-29  
**Status:** Accepted

## Context

Issue #5 requires `check_environmental_constraints` and `check_terrain` LangGraph nodes
that run in parallel after `resolve_parcel`. These nodes must populate the Environmental,
Terrain, and Hard Disqualifiers sections of the Memo.

Three decisions needed to be made:

1. Which data sources to use for each constraint type.
2. How to ingest 3DEP elevation data for slope calculation (runtime fetch vs. bulk load).
3. Where hard-disqualifier logic should live in the graph.

## Decisions

### 1. Data sources

| Constraint | Source | Layer |
|---|---|---|
| Flood zones | FEMA National Flood Hazard Layer (NFHL) | `S_Fld_Haz_Ar` |
| Wetlands | USFWS National Wetlands Inventory (NWI) | Wetlands polygon layer |
| Protected lands | USGS Protected Areas Database (PAD-US) | Combined layer (Fee + Designation + Easement + Proclamation) |
| Terrain slope | USGS 3D Elevation Program (3DEP) | 1/3 arc-second (~10m) DEM |

All four sources are authoritative federal datasets, freely available, and cover New York
statewide. They are loaded via `ogr2ogr` (vector layers) and `raster2pgsql` (DEM) into
the existing PostGIS instance, following the same ingest pattern as HIFLD.

### 2. 3DEP slope: bulk load via PostGIS raster

**Chosen:** bulk-load the NY 10m DEM into a PostGIS `dem` raster table using
`raster2pgsql`; query slope per-request with `ST_Slope` + `ST_Clip` + `ST_SummaryStats`.

**Rationale:** USGS 3DEP elevation data is derived from lidar and represents bare-earth
surface. It changes only on multi-year re-collection cycles. Because terrain is
effectively static, the primary weakness of bulk-loading — staleness — does not apply
here. Bulk-loading keeps `check_terrain` architecturally consistent with every other
Helios node: a single PostGIS query, no runtime external network dependency, no new Python
dependencies (no rasterio/numpy in the container), and graceful degradation if the DEM
table is absent.

**Rejected alternative:** on-demand fetch from the USGS 3DEP WCS/REST API per
`/screen` request using rasterio. This would add rasterio + numpy + GDAL to the container,
introduce a per-request network call (reducing reliability), and provide no practical
freshness benefit given the static nature of terrain.

**Extension:** `postgis_raster` extension is enabled in `init-postgis.sql` for fresh
volumes. The `dem` table is created by `scripts/load_3dep_dem.sh` (not in init SQL), which
matches the HIFLD convention and is necessary because `init-postgis.sql` does not re-run
against the shared external volume.

### 3. Hard-disqualifier logic lives in `build_memo`, not in a graph node or reducer

Per CONTEXT.md, any NWI or PAD-US overlap is a Hard Disqualifier (forces Viability Score
to 0). This logic is derived from the same data the `check_environmental_constraints` node
already computes (`nwi_overlap`, `padus_overlap` booleans).

**Chosen:** `_build_hard_disqualifiers(state)` in `app/models.py` reads the environmental
flags and constructs `HardDisqualifier` entries with Citations at Memo-build time.

**Rationale:** hard disqualifiers are a synthesis/presentation concern, not a data-fetch
concern. Keeping them out of the graph avoids the need for a state reducer on the
`hard_disqualifiers` key (which would be required if two parallel nodes wrote to the same
key). Derivation in `build_memo` is the same pattern used for all other Memo sections, and
it keeps the node responsible only for returning raw data. The ordinance moratorium
disqualifier (a separate hard disqualifier, out of scope for this slice) will follow the
same derivation pattern in the ordinance slice.

## Consequences

- `check_environmental_constraints` and `check_terrain` write disjoint state keys,
  requiring no LangGraph state reducer — consistent with the existing pattern of all nodes
  writing disjoint keys.
- The DEM load is a one-time, persistent operation (data survives in `helios_postgres_data`
  across container restarts). The NY 10m DEM is several GB; teams should load it once and
  treat it as infrastructure, not per-test setup.
- If the DEM table is absent, `check_terrain` degrades gracefully (`terrain_data_available
  = False`), and the Terrain section defaults to `"unable to verify"`, preserving the
  invariant that all Memo sections are always present.
- Future slope re-collection from USGS (if a newer DEM is published) requires re-running
  `scripts/load_3dep_dem.sh` — this is acceptable given the multi-year update cycle.
