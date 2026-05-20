# NYISO queue density as proxy for transmission interconnection capacity

The original plan was to query utility ArcGIS hosting capacity maps (ConEd, National Grid, NYSEG, etc.) for available grid headroom. Those maps are distribution-level tools — they reflect capacity for sub-5MW projects connecting to distribution feeders. Helios targets 5–50MW utility-scale projects, which interconnect via NYISO's transmission queue process, not local utility distribution portals. Querying the distribution maps for utility-scale screening would produce misleading signals.

Instead, Helios uses NYISO interconnection queue density (total MW queued within 10 miles of nearby substations) as a transmission-level proxy. High queue density indicates a congested study area and a longer/harder interconnection path. This is a proxy, not a true capacity measurement — NYISO does not publish a simple hosting capacity number for transmission. The Memo labels this field "Interconnection Capacity (proxy)" to make the limitation visible.

## Consequences

- The `check_hosting_capacity` tool in F4 queries the NYISO interconnection queue, not utility ArcGIS REST services. The PRD has been updated to reflect this.
- If NYISO ever publishes a richer public API for transmission availability, this is the integration point to upgrade.
