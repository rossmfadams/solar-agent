# React SPA frontend, static-served by FastAPI, deployed on Fly.io scale-to-zero

The original PRD specified a server-rendered HTML frontend (Jinja2-style + Folium for the map), aimed at an internal analyst tool. The product framing has since shifted: Helios is now primarily a portfolio piece, accessed by anonymous visitors who click through from a portfolio site, not a multi-analyst SaaS tool. That changes the requirements enough to warrant a different frontend architecture.

We're building the frontend as a React + Vite + TypeScript SPA (recreating the delivered `helios-design` design-system prototype), built to static assets and served directly by FastAPI (`StaticFiles` mount), rather than as a separate deploy target. The whole app — API and frontend — ships as one Docker image on Fly.io, using Fly Machines' auto-stop/auto-start to scale to zero when idle. Fly's proxy auto-starts a stopped Machine on any incoming request, so the portfolio site can prewarm the app by pinging `/health` when a visitor lands on the project page, before they click through to "Explore project."

Render and AWS serverless (Lambda + Aurora Serverless) were considered and rejected: Render's scale-to-zero has slower, less controllable cold starts with no simple prewarm mechanism; AWS's setup complexity (Lambda packaging, VPC networking for Postgres/PostGIS, cold starts inside a 90s LangGraph run) wasn't worth it for a portfolio project's engineering budget.

## Consequences

- The PRD's "Frontend: Single-page app — server-rendered HTML + Folium for the map" line is stale; the Folium map is now embedded via `<iframe>` pointing at the existing `GET /screen/{site_id}` HTML endpoint, everything else is a JSON API consumed by the SPA.
- The Dashboard and Batch Uploads screens from the design system are out of scope — see [ADR-0006](0006-public-access-rate-limiting.md) for why a public, unauthenticated app can't safely support batch runs.
- Single-container deploy means there's no independent frontend deploy/rollback; frontend and backend release together.
