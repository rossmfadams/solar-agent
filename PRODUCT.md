# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
Primary: a portfolio site visitor. They land on Helios's project page, read a short explanation of what it does, then click "Explore project" to try it themselves — pasting one NY address, watching the agent work in real time, and reading the resulting memo. They are evaluating the builder's work (craft, technical depth, product judgment), not conducting real site diligence. No login, no persistence across visitors; each browser session only sees its own past runs ("Recent runs").

Secondary (shapes domain credibility but not the primary design target): a solar developer or analyst (e.g. a Head of Development at a 5-50MW NY-focused developer) triaging inbound leads. The tool must read as a plausible real analyst tool to this audience even though it isn't the person the interface is designed for.

## Product Purpose
Helios automates early-stage site diligence for utility-scale solar projects in New York State. Given an address or coordinates, it produces a structured, cited viability memo covering siting constraints, interconnection availability, and permitting feasibility in roughly 90 seconds — work that would take a junior analyst 30–60 minutes per site. Success is a visitor understanding, within one memo, both what the tool does and that its output is trustworthy (sourced, reproducible, not hand-waved).

## Positioning
Helios is not a chatbot that answers questions about a site — it's a fixed, structured pipeline. Every run executes the same deterministic sequence of checks (parcel resolution, transmission/substation proximity, NYISO queue congestion, flood/wetlands/protected-lands overlap, slope, ordinance research) against real GIS and document sources, and synthesizes them into a reproducible 0–100 score with every flag traceable to a specific citation. A neighboring "AI site advisor" chatbot could not truthfully claim the same reproducibility or sourcing discipline.

## Operating Context
- Single-site flow only: visitor pastes/autocompletes one NY address, submits, and watches live progress (siting / interconnection / permitting checks streaming via SSE) before the memo renders.
- Output is a one-page memo: header, Hard Disqualifiers, Top 3 Constraints, Interconnection, Environmental, Terrain, Ordinance Summary, and an interactive map — always all eight sections, with "unable to verify" shown rather than a section being omitted.
- Sites outside New York State are rejected immediately after geocoding, before the pipeline runs.
- Public, unauthenticated access — per-IP rate limiting and a global concurrency cap protect against abuse/cost (batch/CSV input was scoped out for this reason).
- Deployed as a single Fly.io app with scale-to-zero Machines, prewarmed by the portfolio site on page load — so a visitor's first request may have a cold-start delay.

## Capabilities and Constraints
- Confirmed functional scope: address/lat-lng input, parcel resolution (or 500m point-buffer fallback), transmission/substation distance, NYISO interconnection queue density, FEMA flood / NWI wetlands / PAD-US protected-lands overlap, USGS 3DEP slope, town ordinance research and summarization, viability scoring with Hard Disqualifiers, markdown/PDF memo export.
- Explicitly out of scope: late-stage diligence (Phase 1 ESA, glare/glint studies), legally-binding zoning interpretation, states outside NY, non-solar technologies (wind, BESS, EV charging), project finance modeling, batch/CSV input, sub-1MW projects, title/ownership lookup.
- Domain terminology (Site, Parcel, Interconnection Capacity, Viability Score, Hard Disqualifier, Moratorium, Memo, Citation, Ordinance, Slope) is fixed by CONTEXT.md — copy in the UI should stay consistent with it rather than inventing synonyms.
- Degrades gracefully: when a data source is unavailable, the relevant memo field is marked "unable to verify" rather than the memo failing or omitting the section.

## Evidence on Hand
- Real backend and scoring logic exist and run against real public data sources (NY GIS Clearinghouse, HIFLD, NYISO queue, FEMA NFHL, USFWS NWI, PAD-US, USGS 3DEP, town ordinance documents) — this is not a mocked demo.
- Ordinance research is cached for a limited set of demo NY towns; ordinance data for towns outside that cached set may come back "unable to verify."
- No customer testimonials, case studies, or press exist and none should be fabricated — Helios has no real deployed customers; it is a self-built portfolio project.

## Product Principles
1. Every claim in the memo must be traceable to a citation — never present a flag or score component without its source.
2. All eight memo sections always appear; absence of data is stated explicitly, never silently dropped.
3. The primary audience is judging craft and trustworthiness of the work, not just trying to get a real siting answer — the experience should read as a credible, production-grade analyst tool even though its real function today is portfolio demonstration.
4. Scope stays narrow and explicit (NY, utility-scale solar, single-site, no batch) — resist expanding functional claims beyond what F1–F10 in the PRD actually cover.

## Accessibility & Inclusion
No product-specific accessibility requirement has been established beyond standard web accessibility practice.
