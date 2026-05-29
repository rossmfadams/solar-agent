#!/usr/bin/env python3
"""Load the NYISO interconnection queue into PostGIS.

Data source (public, no auth required):
  https://www.nyiso.com/documents/20142/1407078/NYISO-Interconnection-Queue.xlsx

The NYISO queue has no lat/lng. Each project row carries:
  - Points of Interconnection (POI) — the substation name the project connects at
  - County — coarse fallback

Geolocation strategy (ADR-0002):
  1. exact  — normalized POI matches a HIFLD substation name exactly.
  2. fuzzy  — normalized POI is a substring of a substation name (or vice versa).
  3. county — no substation match; centroid of the project's county is used.

Active queue rows come from two sheets:
  - 'Interconnection Queue'   — individual study projects
  - ' Cluster Projects'       — cluster-study projects

Summer Capacity (SP MW) is the canonical MW figure — matches the 500 / 1,500 MW
congestion thresholds in CONTEXT.md.

Refresh strategy: re-run this script to pull a fresh snapshot. The snapshot_date and
retrieved_at columns in nyiso_queue make staleness visible.

Usage:
  DATABASE_URL=postgresql://user:pass@host:5432/dbname python scripts/load_nyiso_queue.py

Requires: pandas, openpyxl, asyncpg (already in requirements.txt)
"""

import asyncio
import math
import os
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path

import asyncpg
import pandas as pd

NYISO_URL = (
    "https://www.nyiso.com/documents/20142/1407078/NYISO-Interconnection-Queue.xlsx"
)

DATA_DIR = Path(__file__).parent.parent / "data"

# Sheets that contain active-queue projects (the Withdrawn / In Service sheets
# are deliberately excluded — their rows are not queued).
_ACTIVE_SHEETS = ["Interconnection Queue", " Cluster Projects"]

# NY county centroids (WGS84 lng, lat) — fallback for unmatched POI rows.
# Source: approximate geographic centroids; sufficient for county-level fallback.
NY_COUNTY_CENTROIDS: dict[str, tuple[float, float]] = {
    "ALBANY": (-73.9761, 42.6001),
    "ALLEGANY": (-78.0270, 42.2570),
    "BRONX": (-73.8648, 40.8448),
    "BROOME": (-75.8160, 42.1623),
    "CATTARAUGUS": (-78.6698, 42.2489),
    "CAYUGA": (-76.5761, 42.9143),
    "CHAUTAUQUA": (-79.3951, 42.2920),
    "CHEMUNG": (-76.7619, 42.1462),
    "CHENANGO": (-75.6068, 42.4937),
    "CLINTON": (-73.6787, 44.7443),
    "COLUMBIA": (-73.6268, 42.2468),
    "CORTLAND": (-76.0559, 42.5981),
    "DELAWARE": (-74.9707, 42.2009),
    "DUTCHESS": (-73.7478, 41.7784),
    "ERIE": (-78.7398, 42.7284),
    "ESSEX": (-73.9088, 44.1087),
    "FRANKLIN": (-74.3026, 44.5912),
    "FULTON": (-74.4274, 43.1262),
    "GENESEE": (-78.1898, 42.9976),
    "GREENE": (-74.1829, 42.3012),
    "HAMILTON": (-74.5221, 43.6610),
    "HERKIMER": (-74.9632, 43.4337),
    "JEFFERSON": (-75.9974, 44.0048),
    "KINGS": (-73.9442, 40.6452),
    "LEWIS": (-75.4496, 43.7918),
    "LIVINGSTON": (-77.7876, 42.6723),
    "MADISON": (-75.6668, 42.9126),
    "MONROE": (-77.6088, 43.1548),
    "MONTGOMERY": (-74.4415, 42.9007),
    "NASSAU": (-73.5901, 40.7282),
    "NEW YORK": (-73.9712, 40.7831),
    "NIAGARA": (-78.6904, 43.1924),
    "ONEIDA": (-75.4068, 43.2415),
    "ONONDAGA": (-76.1974, 43.0022),
    "ONTARIO": (-77.3026, 42.8551),
    "ORANGE": (-74.3118, 41.3912),
    "ORLEANS": (-78.1665, 43.2418),
    "OSWEGO": (-76.2151, 43.4618),
    "OTSEGO": (-74.9215, 42.6337),
    "PUTNAM": (-73.7926, 41.4251),
    "QUEENS": (-73.7949, 40.7282),
    "RENSSELAER": (-73.5104, 42.7101),
    "RICHMOND": (-74.1502, 40.5795),
    "ROCKLAND": (-74.0126, 41.1498),
    "ST. LAWRENCE": (-75.0815, 44.5001),
    "SARATOGA": (-73.8740, 43.1087),
    "SCHENECTADY": (-74.0657, 42.8118),
    "SCHOHARIE": (-74.4432, 42.5937),
    "SCHUYLER": (-76.9076, 42.3987),
    "SENECA": (-76.8301, 42.7812),
    "STEUBEN": (-77.3815, 42.2687),
    "SUFFOLK": (-72.9226, 40.9649),
    "SULLIVAN": (-74.6482, 41.7262),
    "TIOGA": (-76.3026, 42.1712),
    "TOMPKINS": (-76.4726, 42.4601),
    "ULSTER": (-74.1682, 41.8887),
    "WARREN": (-73.8165, 43.6537),
    "WASHINGTON": (-73.4390, 43.3112),
    "WAYNE": (-76.8715, 43.0637),
    "WESTCHESTER": (-73.7490, 41.1626),
    "WYOMING": (-78.2376, 42.7001),
    "YATES": (-77.1051, 42.6437),
    # Variant spellings
    "SAINT LAWRENCE": (-75.0815, 44.5001),
    "ST LAWRENCE": (-75.0815, 44.5001),
    # Brooklyn / Nassau variants seen in the queue data
    "BROOKLYN": (-73.9442, 40.6452),
    "NASSU": (-73.5901, 40.7282),  # typo seen in NYISO data
    "OFFSHORE": (-73.5000, 40.5000),  # offshore wind; approximate
}


# ---------------------------------------------------------------------------
# Name normalization (also used by tests via direct import)
# ---------------------------------------------------------------------------

_VOLTAGE_RE = re.compile(r"\b\d+\.?\d*\s*kv\b", re.IGNORECASE)
_PUNCT_RE = re.compile(r"[^A-Z0-9 ]")
_WS_RE = re.compile(r"\s+")


def normalize_name(name: str | None) -> str:
    """Return a normalized string for substation-name matching.

    Uppercase, strip voltage suffixes (e.g. '345kV', '115 kV'), punctuation,
    and extra whitespace.  Returns empty string for None / blank / sentinel values.
    """
    if not name:
        return ""
    s = str(name).upper().strip()
    if s in ("TBD", "N/A", "NA", "NONE", ""):
        return ""
    s = _VOLTAGE_RE.sub("", s)
    s = _PUNCT_RE.sub("", s)
    s = _WS_RE.sub(" ", s).strip()
    return s


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------


def download_xlsx(dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "NYISO-Interconnection-Queue.xlsx"
    print(f"Downloading NYISO queue → {dest} …")
    urllib.request.urlretrieve(NYISO_URL, dest)
    print(f"  saved {dest.stat().st_size / 1024:.0f} KB")
    return dest


# ---------------------------------------------------------------------------
# Parse
# ---------------------------------------------------------------------------


def _read_active_sheet(xlsx_path: Path, sheet: str) -> pd.DataFrame:
    """Read one active-queue sheet; return empty DataFrame on error."""
    try:
        return pd.read_excel(xlsx_path, sheet_name=sheet, header=0, engine="openpyxl")
    except Exception as exc:
        print(f"  warning: could not read sheet {sheet!r}: {exc}", file=sys.stderr)
        return pd.DataFrame()


def parse_queue(xlsx_path: Path) -> tuple[pd.DataFrame, date]:
    """Return (active_rows_df, snapshot_date).

    Reads from all active sheets and normalises column names.
    snapshot_date is approximated as today (NYISO does not embed a date in the
    file; the retrieved_at column captures when the data was fetched).
    """
    snapshot_date = date.today()

    def _mw_from_cell(v) -> float | None:
        """Convert a pandas cell value to float, returning None for any NaN/null.

        Works correctly with numpy 2.x where numpy.float64 no longer inherits from
        Python's float (so isinstance(v, float) is False for numpy scalars).
        """
        try:
            if pd.isna(v):
                return None
        except TypeError:
            pass
        try:
            result = float(v)
            # NaN != NaN is always True in IEEE 754 — covers float("NaN") strings
            return None if result != result else result
        except (TypeError, ValueError):
            return None

    def _str_cell(v, default: str = "") -> str:
        """Convert a cell to str, returning default for NaN/null cells."""
        try:
            if pd.isna(v):
                return default
        except TypeError:
            pass
        return str(v).strip()

    rows = []
    for sheet in _ACTIVE_SHEETS:
        raw = _read_active_sheet(xlsx_path, sheet)
        if raw.empty:
            continue

        for _, r in raw.iterrows():
            queue_id = _str_cell(r.get("Queue Pos.", ""))
            project_name = _str_cell(r.get("Project Name", ""))

            # Skip blank rows (both identifiers null) and annotation rows
            if not queue_id and not project_name:
                continue
            if queue_id.upper().startswith("NOTES"):
                continue

            rows.append(
                {
                    "queue_id": queue_id or None,
                    "project_name": project_name or None,
                    "summer_mw": _mw_from_cell(r.get("SP (MW)")),
                    "winter_mw": _mw_from_cell(r.get("WP (MW)")),
                    "county": _str_cell(r.get("County", "")).upper() or None,
                    "interconnection_point": _str_cell(
                        r.get("Points of Interconnection", "")
                    )
                    or None,
                    "status": _str_cell(r.get("S", "")) or None,
                }
            )

    df = pd.DataFrame(rows) if rows else pd.DataFrame()
    return df, snapshot_date


# ---------------------------------------------------------------------------
# Substation matching
# ---------------------------------------------------------------------------


def build_substation_index(substations: list[dict]) -> dict[str, dict]:
    """Return {normalized_name: row} for all HIFLD substations."""
    index: dict[str, dict] = {}
    for row in substations:
        key = normalize_name(row["name"])
        if key:
            index[key] = row
    return index


def match_poi(
    poi: str | None,
    index: dict[str, dict],
) -> tuple[dict | None, str]:
    """Try exact then fuzzy substation name match.

    Returns (substation_row_or_None, method) where method is one of:
      'exact'  — normalized POI == normalized substation name
      'fuzzy'  — one is a substring of the other
      'county' — no match; caller will use county centroid
    """
    key = normalize_name(poi)
    if not key:
        return None, "county"

    # 1. Exact
    if key in index:
        return index[key], "exact"

    # 2. Fuzzy — substring in either direction
    for sub_key, row in index.items():
        if key in sub_key or sub_key in key:
            return row, "fuzzy"

    return None, "county"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> None:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set", file=sys.stderr)
        sys.exit(1)

    # --- 1. Download ---
    xlsx_path = download_xlsx(DATA_DIR)
    retrieved_at = date.today()

    # --- 2. Parse ---
    print("Parsing queue …")
    df, snapshot_date = parse_queue(xlsx_path)
    print(f"  {len(df)} active projects; snapshot_date={snapshot_date}")

    if df.empty:
        print("ERROR: no active projects parsed — check xlsx structure", file=sys.stderr)
        sys.exit(1)

    # --- 3. Connect & fetch substations ---
    print("Connecting to database …")
    conn = await asyncpg.connect(db_url)
    try:
        # Create table if not already present (safe on an existing volume where
        # init-postgis.sql has already run).
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS nyiso_queue (
                id                    BIGSERIAL PRIMARY KEY,
                queue_id              TEXT,
                project_name          TEXT,
                summer_mw             DOUBLE PRECISION,
                winter_mw             DOUBLE PRECISION,
                county                TEXT,
                interconnection_point TEXT,
                matched_substation_id BIGINT,
                match_method          TEXT,
                status                TEXT,
                snapshot_date         DATE,
                retrieved_at          DATE,
                geom                  GEOMETRY(Point, 4326)
            )
            """
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS nyiso_queue_geom_idx "
            "ON nyiso_queue USING GIST (geom)"
        )

        sub_rows = await conn.fetch(
            "SELECT id, name, ST_AsText(geom) AS wkt FROM substations"
        )
        print(f"  loaded {len(sub_rows)} substations for name matching")

        substations = [
            {"id": r["id"], "name": r["name"], "wkt": r["wkt"]} for r in sub_rows
        ]
        index = build_substation_index(substations)

        # --- 4. Resolve geometry for each row ---
        print("Resolving geometries …")
        records = []
        match_counts: dict[str, int] = {"exact": 0, "fuzzy": 0, "county": 0}
        no_geom = 0

        for _, row in df.iterrows():
            poi = row["interconnection_point"]
            sub, method = match_poi(poi, index)

            if sub is not None:
                geom_wkt: str | None = sub["wkt"]
                matched_id: int | None = sub["id"]
            else:
                # County-centroid fallback
                county_key = str(row.get("county") or "").upper().strip()
                county_key = re.sub(
                    r"\s+county$", "", county_key, flags=re.IGNORECASE
                ).strip()
                centroid = NY_COUNTY_CENTROIDS.get(county_key)
                if centroid:
                    lng, lat = centroid
                    geom_wkt = f"POINT({lng} {lat})"
                else:
                    geom_wkt = None
                    no_geom += 1
                matched_id = None

            match_counts[method] += 1
            records.append(
                {
                    "queue_id": row["queue_id"],
                    "project_name": row["project_name"],
                    "summer_mw": row["summer_mw"],
                    "winter_mw": row["winter_mw"],
                    "county": row["county"],
                    "interconnection_point": row["interconnection_point"],
                    "matched_substation_id": matched_id,
                    "match_method": method,
                    "status": row["status"],
                    "snapshot_date": snapshot_date,
                    "retrieved_at": retrieved_at,
                    "geom_wkt": geom_wkt,
                }
            )

        total = len(records)
        print(
            f"  exact={match_counts['exact']}, fuzzy={match_counts['fuzzy']}, "
            f"county={match_counts['county']} of {total} rows "
            f"({no_geom} with no geometry)"
        )

        # --- 5. Normalize any residual NaN floats → None before inserting ---
        # Python float('nan') (distinct from numpy NaN) can escape _mw_from_cell
        # and would be stored as PostgreSQL NaN (not NULL) by asyncpg.
        for rec in records:
            for key in ("summer_mw", "winter_mw"):
                v = rec[key]
                if v is not None:
                    try:
                        if math.isnan(float(v)):
                            rec[key] = None
                    except (TypeError, ValueError):
                        pass

        # --- 6. Full refresh ---
        print("Writing to nyiso_queue (full refresh) …")
        async with conn.transaction():
            await conn.execute("TRUNCATE nyiso_queue RESTART IDENTITY")
            for rec in records:
                if rec["geom_wkt"]:
                    geom_sql = (
                        f"ST_SetSRID(ST_GeomFromText('{rec['geom_wkt']}'), 4326)"
                    )
                else:
                    geom_sql = "NULL"

                await conn.execute(
                    f"""
                    INSERT INTO nyiso_queue
                      (queue_id, project_name, summer_mw, winter_mw, county,
                       interconnection_point, matched_substation_id, match_method,
                       status, snapshot_date, retrieved_at, geom)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,{geom_sql})
                    """,
                    rec["queue_id"],
                    rec["project_name"],
                    rec["summer_mw"],
                    rec["winter_mw"],
                    rec["county"],
                    rec["interconnection_point"],
                    rec["matched_substation_id"],
                    rec["match_method"],
                    rec["status"],
                    rec["snapshot_date"],
                    rec["retrieved_at"],
                )

        count = await conn.fetchval("SELECT COUNT(*) FROM nyiso_queue")
        print(f"  inserted {count} rows")

        # Summary by match method
        summary = await conn.fetch(
            "SELECT match_method, COUNT(*), "
            "ROUND(COALESCE(SUM(summer_mw),0)::numeric) AS total_mw "
            "FROM nyiso_queue GROUP BY match_method ORDER BY match_method"
        )
        print("\nMatch summary:")
        for s in summary:
            pct = round(s["count"] / total * 100)
            print(
                f"  {s['match_method']:8s}  {s['count']:5d} projects ({pct:3d}%)  "
                f"{s['total_mw']:>10.0f} MW"
            )

    finally:
        await conn.close()

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
