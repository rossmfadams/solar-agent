# LangGraph as agent orchestration framework

The agent's tool execution pattern — geocode/resolve in sequence, then five independent data-fetch tools in parallel, then synthesize — maps naturally to a simple `asyncio.gather` pipeline with no branching. LangGraph was chosen anyway as a firm requirement, anticipating future needs: conditional retry logic when data sources are unavailable, and a multi-step sub-graph for ordinance research (web search → PDF parse → LLM summarization) that may need its own state and error handling. The overhead of LangGraph is accepted upfront to avoid a costly migration later.

## Considered Options

- **Plain async pipeline** — simpler, easier to reason about, sufficient for the current linear fan-out/fan-in shape. Rejected because it cannot accommodate conditional branching without a rewrite.
- **LangGraph** — accepted. Adds boilerplate now but supports the anticipated sub-graph complexity without architectural changes.
