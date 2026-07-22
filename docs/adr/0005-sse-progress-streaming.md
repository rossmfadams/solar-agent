# Server-Sent Events for live pipeline progress, not polling or WebSockets

The pipeline run takes ~90 seconds, and the product goal is for it to feel like watching an AI agent work (in the spirit of Claude Code's tool-call feed), not a blank loading spinner. The LangGraph graph (`app/graph.py`) has real parallelism — `check_grid_proximity` → `check_hosting_capacity`, `check_environmental_constraints`, `check_terrain`, and `research_local_ordinance` all fan out concurrently from `resolve_parcel` before fanning in to `synthesize_memo` — so whatever transport we choose has to represent nodes completing out of order, not a strict sequence.

We're using Server-Sent Events: one endpoint streams a JSON event per completed LangGraph node (via `.astream()` instead of `.ainvoke()`), ending with a final memo event. The frontend renders this as a checklist where parallel branches appear as independent rows that light up concurrently, sitting above already-completed steps.

WebSockets were rejected as unnecessary — the data only flows server→client, and a long-lived bidirectional connection adds complexity with no payoff here. Polling was rejected because it pairs more naturally with scale-to-zero infra (no long-lived connection) but produces choppier, less "alive" progress; a single active SSE connection during a run doesn't conflict with Fly.io's scale-to-zero behavior, which only spins a Machine down when idle, not mid-request.

## Consequences

- Nodes that degrade gracefully (return "unable to verify" instead of failing) surface as a distinct warning-toned "done" state in the step feed, not a hard error — consistent with the Memo's existing philosophy that missing data is a caveat, not a failure.
- `main.py` needs a streaming variant of the `/screen` flow (`.astream()` over the compiled graph) alongside or replacing the current blocking `.ainvoke()` call.
