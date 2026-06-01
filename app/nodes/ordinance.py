"""research_local_ordinance — nested LangGraph sub-graph for solar ordinance lookup.

Architecture
------------
The parent node `research_local_ordinance` is a thin wrapper that:
  1. Degrades immediately if no town (muni) is available.
  2. Returns a fresh cache hit if one exists (≤30-day TTL).
  3. Otherwise invokes the live sub-graph, writes the result through to cache,
     and returns the mapped state keys.

The live sub-graph is a StateGraph[OrdinanceState] that loops over source tiers
(eCode360 → Municode → town website → NYSERDA guidebook) in priority order,
stopping at the first hit.  Each tier is one Claude call (claude-sonnet-4-6)
with the server-side web_search tool restricted to that tier's allowed domains
plus a forced client-side `record_ordinance` tool for structured extraction.

Why a nested StateGraph here (vs. a plain loop in the parent node):
  The tier search has genuine conditional control flow — found → finish,
  not-found → next tier, exhausted → "unable to verify" — that maps naturally
  to conditional edges.  The parent graph stays flat because its chain
  (geocode → parcel → grid → hosting) is purely linear.

Parallel safety
---------------
This node writes only `ordinance_*` keys, which are disjoint from all keys
written by check_grid_proximity and check_hosting_capacity.  LangGraph's plain
TypedDict channels raise InvalidUpdateError on concurrent same-key writes, so
the namespace separation is load-bearing, not cosmetic.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from typing import TypedDict

import anthropic
from langgraph.graph import StateGraph, END

from app.db import get_pool

# ---------------------------------------------------------------------------
# Degraded state — returned on any unrecoverable failure (mirrors other nodes)
# ---------------------------------------------------------------------------

_DEGRADED: dict = {
    "ordinance_available": False,
    "ordinance_found": False,
    "ordinance_source": None,
    "ordinance_source_url": None,
    "ordinance_section": None,
    "ordinance_setbacks": None,
    "ordinance_sup": None,
    "ordinance_summary_text": None,
    "ordinance_moratorium_active": False,
    "ordinance_moratorium_section": None,
    "ordinance_moratorium_quote": None,
    "ordinance_retrieval_date": None,
}

# ---------------------------------------------------------------------------
# Source tiers (searched in order; first hit wins)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Tier:
    name: str
    domains: list[str] | None  # None = unrestricted (used for town website tier)


TIERS: list[Tier] = [
    Tier("eCode360", ["ecode360.com"]),
    Tier("Municode", ["municode.com", "library.municode.com"]),
    Tier("Town website", None),
    Tier("NYSERDA Solar Guidebook", ["nyserda.ny.gov"]),
]

# ---------------------------------------------------------------------------
# Anthropic client
# ---------------------------------------------------------------------------

def _get_client() -> anthropic.AsyncAnthropic:
    """Build an async Anthropic client.  Raises RuntimeError if key is unset."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    return anthropic.AsyncAnthropic(api_key=api_key)


# ---------------------------------------------------------------------------
# Prompts and tool schemas
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a land-use research assistant specializing in New York State solar energy ordinances.

Your task: find and extract the ENACTED solar zoning rules for the given NY town from the \
allowed source(s).

Extract:
- Setback requirements (distances from property lines, roads, buildings, wetlands, etc.)
- Special Use Permit (SUP) requirements for solar installations
- Whether there is an active moratorium on new solar permit applications

CRITICAL moratorium rule: Set moratorium_active=true ONLY when you find an explicit, \
currently-active legislative prohibition on new solar PERMIT APPLICATIONS \
(e.g., "no applications for solar energy systems shall be accepted or processed until…"). \
A moratorium requires a specific section reference AND a verbatim quote of the prohibition. \
Restrictive setbacks, SUP requirements, height limits, design standards, screening \
requirements, or similar conditions are ordinance constraints — they are NOT moratoriums. \
Do not conflate them.

If no solar ordinance is found at the allowed source(s), set found=false and \
moratorium_active=false.
"""

_RECORD_ORDINANCE_TOOL: dict = {
    "name": "record_ordinance",
    "description": (
        "Record your findings about the town's solar energy ordinance. "
        "Call this with found=false if no ordinance was located at the allowed source(s)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "found": {
                "type": "boolean",
                "description": "True if a solar ordinance was found at this source tier.",
            },
            "source": {
                "type": "string",
                "description": "Source name (e.g. 'eCode360', 'Municode', 'Town website').",
            },
            "url": {
                "type": "string",
                "description": "URL of the source document or page.",
            },
            "section": {
                "type": "string",
                "description": "Document chapter/section reference (e.g. 'Chapter 190, § 190-12').",
            },
            "setbacks": {
                "type": "string",
                "description": "Setback requirements as stated in the ordinance.",
            },
            "sup_requirements": {
                "type": "string",
                "description": "Special Use Permit requirements for solar installations.",
            },
            "moratorium_active": {
                "type": "boolean",
                "description": (
                    "True ONLY for an explicit active prohibition on new solar applications "
                    "backed by a specific section + verbatim quote.  Restrictive setbacks "
                    "or SUP requirements are NOT moratoriums."
                ),
            },
            "moratorium_section": {
                "type": "string",
                "description": "Section reference for the moratorium provision.",
            },
            "moratorium_quote": {
                "type": "string",
                "description": "Verbatim text of the moratorium provision.",
            },
            "summary": {
                "type": "string",
                "description": "Brief plain-English summary of the solar ordinance.",
            },
        },
        "required": ["found", "moratorium_active"],
    },
}

# ---------------------------------------------------------------------------
# Cache SQL
# ---------------------------------------------------------------------------

_READ_CACHE_QUERY = """
SELECT source_name, source_url, document_section, setbacks, sup_requirements,
       moratorium_active, moratorium_section, moratorium_quote, summary, found,
       retrieved_at
FROM ordinance_cache
WHERE muni_norm = $1
  AND county_norm = $2
  AND retrieved_at > (CURRENT_DATE - INTERVAL '30 days')
"""

_WRITE_CACHE_QUERY = """
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
# Cache helpers
# ---------------------------------------------------------------------------

def _normalize_town(name: str) -> str:
    """Lowercase, strip, collapse whitespace — used as the cache key."""
    return " ".join(name.lower().split())


async def _read_cache(conn, muni_norm: str, county_norm: str):
    """Return a fresh cache row or None (TTL enforced in SQL)."""
    return await conn.fetchrow(_READ_CACHE_QUERY, muni_norm, county_norm)


async def _write_cache(
    conn,
    muni: str,
    county: str,
    muni_norm: str,
    county_norm: str,
    result: dict | None,
    found: bool,
) -> None:
    """Upsert ordinance result (including negative results) into cache."""
    r = result or {}
    await conn.execute(
        _WRITE_CACHE_QUERY,
        muni,
        county,
        muni_norm,
        county_norm,
        found,
        r.get("source"),
        r.get("url"),
        r.get("section"),
        r.get("setbacks"),
        r.get("sup_requirements"),
        bool(r.get("moratorium_active", False)),
        r.get("moratorium_section"),
        r.get("moratorium_quote"),
        r.get("summary"),
    )


def _map_cache_row(row) -> dict:
    """Map an ordinance_cache DB row to the ordinance_* state keys."""
    retrieval = row["retrieved_at"]
    return {
        "ordinance_available": True,
        "ordinance_found": bool(row["found"]),
        "ordinance_source": row["source_name"],
        "ordinance_source_url": row["source_url"],
        "ordinance_section": row["document_section"],
        "ordinance_setbacks": row["setbacks"],
        "ordinance_sup": row["sup_requirements"],
        "ordinance_summary_text": row["summary"],
        "ordinance_moratorium_active": bool(row["moratorium_active"]),
        "ordinance_moratorium_section": row["moratorium_section"],
        "ordinance_moratorium_quote": row["moratorium_quote"],
        "ordinance_retrieval_date": retrieval.isoformat() if retrieval else date.today().isoformat(),
    }


def _map_result(result: dict, retrieval_date: str) -> dict:
    """Map a live record_ordinance response to the ordinance_* state keys."""
    return {
        "ordinance_available": True,
        "ordinance_found": True,
        "ordinance_source": result.get("source"),
        "ordinance_source_url": result.get("url"),
        "ordinance_section": result.get("section"),
        "ordinance_setbacks": result.get("setbacks"),
        "ordinance_sup": result.get("sup_requirements"),
        "ordinance_summary_text": result.get("summary"),
        "ordinance_moratorium_active": bool(result.get("moratorium_active", False)),
        "ordinance_moratorium_section": result.get("moratorium_section"),
        "ordinance_moratorium_quote": result.get("moratorium_quote"),
        "ordinance_retrieval_date": retrieval_date,
    }


# ---------------------------------------------------------------------------
# Live research — single tier (the mockable seam for unit tests)
# ---------------------------------------------------------------------------

async def _research_tier(muni: str, county: str, tier: Tier) -> dict | None:
    """Search one source tier for a solar ordinance.

    Two-step pattern:
      1. Let Claude search freely (no tool_choice) — web_search_20250305 is
         server-side; results are auto-populated in the same response.
      2. If Claude called record_ordinance directly, return it.  Otherwise
         force record_ordinance extraction from Claude's text summary.

    Returns the record_ordinance input dict, or None if the API call failed.
    """
    try:
        client = _get_client()
    except RuntimeError:
        return None

    web_search_def: dict = {
        "type": "web_search_20250305",
        "name": "web_search",
        "max_uses": 5,
    }
    if tier.domains:
        web_search_def["allowed_domains"] = tier.domains

    user_message = (
        f"Research the enacted solar energy zoning ordinance for "
        f"the Town of {muni}, {county} County, New York State. "
        f"Search for setback requirements, Special Use Permit (SUP) "
        f"requirements, and any active moratorium on new solar "
        f"applications. Use only sources from {tier.name}."
    )

    # Step 1 — search.  No tool_choice so web_search executes before any output.
    try:
        resp1 = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=_SYSTEM_PROMPT,
            tools=[web_search_def, _RECORD_ORDINANCE_TOOL],
            messages=[{"role": "user", "content": user_message}],
        )
    except Exception:
        return None

    # Fast path: Claude called record_ordinance directly after searching.
    for block in resp1.content:
        if (
            hasattr(block, "type")
            and block.type == "tool_use"
            and block.name == "record_ordinance"
        ):
            return block.input  # type: ignore[return-value]

    # Slow path: Claude gave a text summary — force structured extraction.
    text_parts = [
        b.text for b in resp1.content
        if hasattr(b, "type") and b.type == "text" and b.text.strip()
    ]
    if not text_parts:
        return None

    try:
        resp2 = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            tools=[_RECORD_ORDINANCE_TOOL],
            tool_choice={"type": "tool", "name": "record_ordinance"},
            messages=[
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": "\n".join(text_parts)},
                {
                    "role": "user",
                    "content": (
                        "Based on your research above, call record_ordinance with "
                        "your findings.  If no solar ordinance was found at this "
                        "source, set found=false and moratorium_active=false."
                    ),
                },
            ],
        )
    except Exception:
        return None

    for block in resp2.content:
        if (
            hasattr(block, "type")
            and block.type == "tool_use"
            and block.name == "record_ordinance"
        ):
            return block.input  # type: ignore[return-value]

    return None


# ---------------------------------------------------------------------------
# Nested sub-graph — tier priority loop with conditional edges
# ---------------------------------------------------------------------------

class OrdinanceState(TypedDict):
    muni: str
    county: str
    tier_index: int   # index of the NEXT tier to try
    found: bool
    result: dict | None


async def _try_tier_node(state: OrdinanceState) -> dict:
    """Try the current tier; advance tier_index regardless of outcome.

    A per-tier exception (e.g. transient API error) is treated as a miss so the
    sub-graph falls through to the next source rather than aborting entirely.
    """
    idx = state["tier_index"]
    try:
        raw = await _research_tier(state["muni"], state["county"], TIERS[idx])
    except Exception:
        raw = None
    found = raw is not None and bool(raw.get("found", False))
    return {
        "tier_index": idx + 1,
        "found": found,
        "result": raw if found else None,
    }


def _route_tier(state: OrdinanceState) -> str:
    """Route to END when a result is found or all tiers are exhausted."""
    if state["found"]:
        return "done"
    if state["tier_index"] >= len(TIERS):
        return "done"
    return "continue"


def _build_ordinance_subgraph() -> object:
    builder: StateGraph = StateGraph(OrdinanceState)
    builder.add_node("try_tier", _try_tier_node)
    builder.set_entry_point("try_tier")
    builder.add_conditional_edges(
        "try_tier",
        _route_tier,
        {"continue": "try_tier", "done": END},
    )
    return builder.compile()


_ordinance_subgraph = _build_ordinance_subgraph()

# ---------------------------------------------------------------------------
# Parent node — cache check → live sub-graph → write-through
# ---------------------------------------------------------------------------

async def research_local_ordinance(state: dict) -> dict:
    """LangGraph node: look up the town's solar ordinance (cache-first, live on miss).

    Runs in parallel with check_grid_proximity / check_hosting_capacity after
    resolve_parcel.  Returns only ordinance_* keys (disjoint namespace).
    """
    muni: str | None = state.get("muni")
    county: str | None = state.get("county") or ""

    if not muni:
        return _DEGRADED

    muni_norm = _normalize_town(muni)
    county_norm = _normalize_town(county)

    # --- Cache read ---
    row = None
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            row = await _read_cache(conn, muni_norm, county_norm)
    except RuntimeError:
        pass  # DATABASE_URL unset — skip cache, fall through to live research
    except Exception:
        pass  # DB unavailable — proceed to live research

    if row is not None:
        return _map_cache_row(row)

    # --- Live research via nested sub-graph ---
    try:
        initial: OrdinanceState = {
            "muni": muni,
            "county": county,
            "tier_index": 0,
            "found": False,
            "result": None,
        }
        final = await _ordinance_subgraph.ainvoke(initial)
        found: bool = bool(final.get("found", False))
        result: dict | None = final.get("result")
    except Exception:
        return _DEGRADED

    retrieval_date = date.today().isoformat()

    # --- Write-through to cache (best-effort; failure is non-fatal) ---
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await _write_cache(conn, muni, county, muni_norm, county_norm, result, found)
    except Exception:
        pass

    if not found or result is None:
        # Searched all tiers, nothing found — signal available but not found
        # so the memo renders "unable to verify" rather than a hard degrade.
        return {
            **_DEGRADED,
            "ordinance_available": True,
            "ordinance_found": False,
        }

    return _map_result(result, retrieval_date)
