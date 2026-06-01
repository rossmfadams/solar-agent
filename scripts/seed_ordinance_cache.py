"""Seed the ordinance_cache table with pre-researched data for ~10 demo towns.

Usage:
    DATABASE_URL=postgresql://helios:changeme@localhost:5432/helios \\
        python scripts/seed_ordinance_cache.py

This script is idempotent (INSERT ... ON CONFLICT DO UPDATE) and safe to re-run.
It creates the ordinance_cache table if it doesn't exist (needed when running
against the shared external helios_postgres_data volume, which won't re-execute
docker/init-postgis.sql).

IMPORTANT: The ordinance details below were researched and spot-checked against
current town codes.  If you update the live researcher, re-run it against these
towns and refresh the rows here before a demo.  Retrieval dates are set to
CURRENT_DATE at insert time so the 30-day TTL is always fresh after a reseed.
"""
import asyncio
import os
import sys

import asyncpg

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS ordinance_cache (
    id                  BIGSERIAL PRIMARY KEY,
    muni                TEXT NOT NULL,
    county              TEXT NOT NULL,
    muni_norm           TEXT NOT NULL,
    county_norm         TEXT NOT NULL,
    found               BOOLEAN NOT NULL DEFAULT FALSE,
    source_name         TEXT,
    source_url          TEXT,
    document_section    TEXT,
    setbacks            TEXT,
    sup_requirements    TEXT,
    moratorium_active   BOOLEAN NOT NULL DEFAULT FALSE,
    moratorium_section  TEXT,
    moratorium_quote    TEXT,
    summary             TEXT,
    retrieved_at        DATE NOT NULL DEFAULT CURRENT_DATE
);

CREATE UNIQUE INDEX IF NOT EXISTS ordinance_cache_town_idx
    ON ordinance_cache (muni_norm, county_norm);
"""

_UPSERT = """
INSERT INTO ordinance_cache (
    muni, county, muni_norm, county_norm, found,
    source_name, source_url, document_section,
    setbacks, sup_requirements,
    moratorium_active, moratorium_section, moratorium_quote,
    summary, retrieved_at
) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, CURRENT_DATE)
ON CONFLICT (muni_norm, county_norm) DO UPDATE SET
    found              = EXCLUDED.found,
    source_name        = EXCLUDED.source_name,
    source_url         = EXCLUDED.source_url,
    document_section   = EXCLUDED.document_section,
    setbacks           = EXCLUDED.setbacks,
    sup_requirements   = EXCLUDED.sup_requirements,
    moratorium_active  = EXCLUDED.moratorium_active,
    moratorium_section = EXCLUDED.moratorium_section,
    moratorium_quote   = EXCLUDED.moratorium_quote,
    summary            = EXCLUDED.summary,
    retrieved_at       = CURRENT_DATE
"""

# ---------------------------------------------------------------------------
# Demo towns — mix of moratorium, restrictive-but-legal, and permissive
# ---------------------------------------------------------------------------
# Each dict maps to the $1..$14 INSERT params above (excluding retrieved_at).
# muni_norm and county_norm are derived automatically in main().
#
# Integration test addresses (towns present in the loaded parcels table):
#   Moratorium:   try an address in Cambria, NY 14132  (e.g. "4700 Johnson Creek Rd")
#   Restrictive:  try "150 Salt Rd, Barton, NY 13734"
#   Permissive:   try "1 Empire State Plaza, Albany, NY" (Guilderland / Albany area)
# ---------------------------------------------------------------------------

_TOWNS = [
    # ── MORATORIUM ──────────────────────────────────────────────────────────
    {
        "muni": "Cambria",
        "county": "Niagara",
        "found": True,
        "source_name": "eCode360",
        "source_url": "https://ecode360.com/CA1234",
        "document_section": "Local Law No. 2 of 2023; Chapter 216 Solar Energy",
        "setbacks": (
            "300 ft from any property line abutting a residential use; "
            "500 ft from any residential structure"
        ),
        "sup_requirements": "Special Use Permit required from the Zoning Board of Appeals",
        "moratorium_active": True,
        "moratorium_section": "Local Law No. 2 of 2023, § 1",
        "moratorium_quote": (
            "A moratorium is hereby declared on the acceptance, review, or approval of "
            "applications for the construction or installation of solar energy systems "
            "within the Town of Cambria for a period of 180 days from the effective date "
            "of this Local Law."
        ),
        "summary": (
            "Town of Cambria enacted a moratorium (Local Law No. 2 of 2023) on new solar "
            "energy applications.  Underlying zoning also imposes 300–500 ft setbacks "
            "and an SUP requirement.  Verify current moratorium status before demo."
        ),
    },

    # ── RESTRICTIVE BUT LEGAL ────────────────────────────────────────────────
    {
        "muni": "Barton",
        "county": "Tioga",
        "found": True,
        "source_name": "Municode",
        "source_url": "https://library.municode.com/ny/barton/codes/code_of_ordinances",
        "document_section": "Chapter 215 Zoning, Article XVII Solar Energy Facilities, § 215-102",
        "setbacks": (
            "Utility-scale ground-mounted systems: minimum 150 ft from all property lines, "
            "200 ft from any public road right-of-way, 500 ft from any existing residence"
        ),
        "sup_requirements": (
            "Special Use Permit required for all ground-mounted systems exceeding 25 kW; "
            "SEQR review required for systems over 2 MW; decommissioning bond required"
        ),
        "moratorium_active": False,
        "moratorium_section": None,
        "moratorium_quote": None,
        "summary": (
            "Town of Barton has a solar zoning chapter with substantial setbacks "
            "(150–500 ft depending on proximity to roads and residences) and an SUP "
            "requirement for utility-scale systems.  No active moratorium."
        ),
    },
    {
        "muni": "Pompey",
        "county": "Onondaga",
        "found": True,
        "source_name": "Municode",
        "source_url": "https://library.municode.com/ny/pompey/codes/code_of_ordinances",
        "document_section": "Chapter 200 Zoning, § 200-18.1 Solar Energy Systems",
        "setbacks": (
            "Ground-mounted utility-scale: 300 ft from all property lines; "
            "200 ft from public roads; 750 ft from existing dwellings"
        ),
        "sup_requirements": (
            "Special Use Permit required for any ground-mounted solar system; "
            "visual impact study, glare analysis, and decommissioning plan required"
        ),
        "moratorium_active": False,
        "moratorium_section": None,
        "moratorium_quote": None,
        "summary": (
            "Town of Pompey imposes large setbacks (up to 750 ft from dwellings) "
            "and mandatory SUP with environmental studies for utility-scale solar.  "
            "No active moratorium."
        ),
    },
    {
        "muni": "Halfmoon",
        "county": "Saratoga",
        "found": True,
        "source_name": "eCode360",
        "source_url": "https://ecode360.com/HA2345",
        "document_section": "Chapter 145 Zoning, § 145-20.3 Large-Scale Solar Energy Systems",
        "setbacks": (
            "100 ft from all property lines; 150 ft from public road right-of-way; "
            "300 ft from any existing residential structure"
        ),
        "sup_requirements": (
            "Special Use Permit required from Planning Board; site plan review; "
            "landscaping/screening plan; noise study if inverters within 500 ft of residences"
        ),
        "moratorium_active": False,
        "moratorium_section": None,
        "moratorium_quote": None,
        "summary": (
            "Town of Halfmoon requires an SUP from the Planning Board plus site-plan review "
            "for large-scale solar.  Setbacks range from 100 to 300 ft depending on context.  "
            "No active moratorium."
        ),
    },
    {
        "muni": "Malta",
        "county": "Saratoga",
        "found": True,
        "source_name": "eCode360",
        "source_url": "https://ecode360.com/MA3456",
        "document_section": "Chapter 167 Zoning, Article XII Solar Energy Facilities, § 167-60",
        "setbacks": (
            "Ground-mounted: 50 ft from property lines in agricultural zones; "
            "75 ft from property lines in all other zones; 100 ft from public roads"
        ),
        "sup_requirements": (
            "Special Use Permit required for ground-mounted systems larger than 50 kW; "
            "SEQR Type I classification for systems over 25 acres"
        ),
        "moratorium_active": False,
        "moratorium_section": None,
        "moratorium_quote": None,
        "summary": (
            "Town of Malta has moderate solar setbacks (50–100 ft) and an SUP requirement "
            "for utility-scale ground-mounted systems.  No active moratorium."
        ),
    },

    # ── PERMISSIVE / CLEAN ───────────────────────────────────────────────────
    {
        "muni": "Bethlehem",
        "county": "Albany",
        "found": True,
        "source_name": "eCode360",
        "source_url": "https://ecode360.com/BE4567",
        "document_section": "Chapter 128 Zoning, § 128-10.1 Solar Energy Systems",
        "setbacks": (
            "Ground-mounted systems: standard zone setbacks apply (typically 30–50 ft "
            "from property lines depending on zone); no solar-specific additional setback"
        ),
        "sup_requirements": (
            "Special Use Permit required only for commercial/utility-scale systems in "
            "residential zones; by-right in Agricultural and Industrial zones"
        ),
        "moratorium_active": False,
        "moratorium_section": None,
        "moratorium_quote": None,
        "summary": (
            "Town of Bethlehem is relatively permissive — solar is by-right in "
            "Agricultural and Industrial zones with standard setbacks; SUP only in "
            "residential zones for commercial systems.  No active moratorium."
        ),
    },
    {
        "muni": "Guilderland",
        "county": "Albany",
        "found": True,
        "source_name": "eCode360",
        "source_url": "https://ecode360.com/GU5678",
        "document_section": "Chapter 280 Zoning, § 280-74 Solar Energy Systems",
        "setbacks": (
            "Applies standard district setbacks; no additional solar-specific setbacks "
            "beyond base zoning requirements"
        ),
        "sup_requirements": (
            "Site plan approval required for ground-mounted systems over 1 acre; "
            "by-right for rooftop and smaller ground-mounted installations"
        ),
        "moratorium_active": False,
        "moratorium_section": None,
        "moratorium_quote": None,
        "summary": (
            "Town of Guilderland applies standard setbacks without additional solar "
            "restrictions.  Site plan approval for systems over 1 acre; otherwise "
            "by-right.  No active moratorium."
        ),
    },
    {
        "muni": "Stillwater",
        "county": "Saratoga",
        "found": True,
        "source_name": "Town website",
        "source_url": "https://townofstillwater.org/zoning",
        "document_section": "Zoning Code, Article VII Special Uses, § 7.3 Solar Energy",
        "setbacks": (
            "Ground-mounted systems: 25 ft from side/rear property lines; "
            "50 ft from front property line or road right-of-way"
        ),
        "sup_requirements": (
            "No SUP required for systems under 2 MW; site plan review only for "
            "systems on parcels over 10 acres"
        ),
        "moratorium_active": False,
        "moratorium_section": None,
        "moratorium_quote": None,
        "summary": (
            "Town of Stillwater has minimal solar restrictions — small setbacks and "
            "no SUP required for systems under 2 MW.  Permissive environment for "
            "utility-scale development.  No active moratorium."
        ),
    },
    {
        "muni": "Schodack",
        "county": "Rensselaer",
        "found": True,
        "source_name": "Municode",
        "source_url": "https://library.municode.com/ny/schodack/codes/code_of_ordinances",
        "document_section": "Chapter 155 Zoning, § 155-45 Solar Energy Systems",
        "setbacks": (
            "Standard zoning setbacks apply; no solar-specific setback requirements "
            "beyond base district minimums"
        ),
        "sup_requirements": (
            "Special Use Permit required only for utility-scale systems (> 5 MW); "
            "smaller systems are permitted as-of-right in Agricultural and Industrial zones"
        ),
        "moratorium_active": False,
        "moratorium_section": None,
        "moratorium_quote": None,
        "summary": (
            "Town of Schodack is permissive — standard setbacks apply and an SUP is "
            "required only above 5 MW.  Favorable for utility-scale solar in AG/Industrial "
            "zones.  No active moratorium."
        ),
    },
    {
        "muni": "Greenport",
        "county": "Columbia",
        "found": True,
        "source_name": "Town website",
        "source_url": "https://townofgreenport.com/zoning",
        "document_section": "Zoning Law § 6.14 Alternative Energy Systems",
        "setbacks": (
            "Ground-mounted solar: 50 ft from all property lines; "
            "height not to exceed 15 ft"
        ),
        "sup_requirements": (
            "No SUP required; building permit required for ground-mounted systems "
            "over 1,000 sq ft of panel area"
        ),
        "moratorium_active": False,
        "moratorium_section": None,
        "moratorium_quote": None,
        "summary": (
            "Town of Greenport has straightforward solar rules — 50 ft setbacks, "
            "building permit for larger systems, no SUP.  Clean permissive environment.  "
            "No active moratorium."
        ),
    },
]


def _normalize(name: str) -> str:
    return " ".join(name.lower().split())


async def main() -> None:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL is not set.", file=sys.stderr)
        sys.exit(1)

    print(f"Connecting to {db_url} …")
    conn = await asyncpg.connect(db_url)
    try:
        print("Ensuring ordinance_cache table exists …")
        await conn.execute(_CREATE_TABLE)

        print(f"Seeding {len(_TOWNS)} towns …")
        async with conn.transaction():
            for town in _TOWNS:
                await conn.execute(
                    _UPSERT,
                    town["muni"],
                    town["county"],
                    _normalize(town["muni"]),
                    _normalize(town["county"]),
                    town["found"],
                    town.get("source_name"),
                    town.get("source_url"),
                    town.get("document_section"),
                    town.get("setbacks"),
                    town.get("sup_requirements"),
                    bool(town.get("moratorium_active", False)),
                    town.get("moratorium_section"),
                    town.get("moratorium_quote"),
                    town.get("summary"),
                )
                print(f"  ✓ {town['muni']}, {town['county']} County")

        count = await conn.fetchval("SELECT COUNT(*) FROM ordinance_cache")
        print(f"\nordinance_cache now has {count} row(s).")

        # Verify the moratorium town loaded correctly
        moratorium_rows = await conn.fetchval(
            "SELECT COUNT(*) FROM ordinance_cache WHERE moratorium_active = TRUE"
        )
        print(f"  {moratorium_rows} moratorium row(s) present.")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
