"""synthesize_memo — computes the ordinance deduction via a single LLM call.

All deterministic scoring (weighted deductions, star mapping, hard disqualifiers)
lives in build_memo / helpers in app/models.py so it can be unit-tested without
a graph or API key.  This node's only job is the one piece that needs an LLM:
asking the model to score ordinance severity on a 0–10 scale.
"""
from __future__ import annotations

import os

import anthropic


def _get_client() -> anthropic.AsyncAnthropic:
    """Build an async Anthropic client.  Raises RuntimeError if key is unset."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    return anthropic.AsyncAnthropic(api_key=api_key)


_SCORE_ORDINANCE_TOOL: dict = {
    "name": "score_ordinance",
    "description": (
        "Return a severity deduction (0–10) for the solar ordinance constraints found. "
        "0 = permissive / no meaningful constraints; 10 = highly restrictive."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "deduction": {
                "type": "integer",
                "description": "Severity score 0–10 (higher = more restrictive).",
                "minimum": 0,
                "maximum": 10,
            },
        },
        "required": ["deduction"],
    },
}


async def synthesize_memo(state: dict) -> dict:
    """LangGraph node: score ordinance restrictiveness via LLM, default 0 on any failure."""
    if not state.get("ordinance_found"):
        return {"ordinance_deduction": 0}

    summary = state.get("ordinance_summary_text") or ""
    setbacks = state.get("ordinance_setbacks") or ""
    sup = state.get("ordinance_sup") or ""

    try:
        client = _get_client()
    except RuntimeError:
        return {"ordinance_deduction": 0}

    prompt = (
        f"Solar ordinance found:\n"
        f"Summary: {summary}\n"
        f"Setbacks: {setbacks}\n"
        f"SUP requirements: {sup}\n\n"
        f"Score the restrictiveness: 0 = permissive, 10 = highly restrictive."
    )

    try:
        resp = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=256,
            tools=[_SCORE_ORDINANCE_TOOL],
            tool_choice={"type": "tool", "name": "score_ordinance"},
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception:
        return {"ordinance_deduction": 0}

    for block in resp.content:
        if (
            hasattr(block, "type")
            and block.type == "tool_use"
            and block.name == "score_ordinance"
        ):
            raw = int(block.input.get("deduction", 0))
            deduction = max(0, min(10, raw))
            return {"ordinance_deduction": -deduction}

    return {"ordinance_deduction": 0}
