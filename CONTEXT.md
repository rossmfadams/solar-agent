# Helios

An AI agent that automates early-stage site diligence for utility-scale solar projects in New York State, producing a structured viability memo from an address or coordinates.

## Language

**Site**:
A candidate solar project location as submitted by the user (address or lat/lng). For pre-screening purposes, treated as 1:1 with a single Parcel.
_Avoid_: Project, property, location

**Parcel**:
The NY GIS cadastral unit that a Site resolves to. The atomic unit of spatial analysis.
_Avoid_: Lot, property, land, site (when meaning the cadastral record)

**Interconnection Capacity**:
A proxy measure of transmission grid availability near a Site, expressed as total MW queued in the NYISO interconnection queue within 10 miles of nearby substations. High queue density signals a congested area. Transmission distance scored as: ≤1 mile = strong positive, 1–5 miles = neutral, 5–10 miles = mild negative, >10 miles = strong negative.
_Avoid_: Hosting capacity (reserved for distribution-level ArcGIS data, not applicable at utility scale)

**Viability Score**:
An integer 0–100 paired with a 0–5 star rating representing a Site's development potential. Hard Disqualifiers force the score to 0 (0 stars, "Hard Disqualified"). Scored sites map to: 1–25 = 1 star (Very Low), 26–50 = 2 stars (Low), 51–70 = 3 stars (Moderate), 71–85 = 4 stars (Good), 86–100 = 5 stars (Strong).
_Avoid_: Rating, rank, grade

**Hard Disqualifier**:
A constraint that makes a site legally or physically unbuildable, forcing the Viability Score to 0. Independent of weighted scoring. Current hard disqualifiers: NWI wetlands overlap, PAD-US protected lands overlap, active town solar moratorium.
_Avoid_: Knockout, red flag, blocker

**Moratorium**:
An explicit, currently-active legislative prohibition on new solar permit applications in a given town. Must be supported by a citation to a specific document and section to trigger the Hard Disqualifier. Restrictive-but-legal ordinances (onerous setbacks, SUP requirements) are not moratoriums.
_Avoid_: Ban, restriction, ordinance (when meaning a moratorium specifically)

**Memo**:
The structured output artifact Helios produces for a Site. Has eight required sections: Header, Hard Disqualifiers, Top 3 Constraints, Interconnection, Environmental, Terrain, Ordinance Summary, and Interactive Map. Every section is always present; unavailable data is marked "unable to verify" rather than omitted.
_Avoid_: Report, summary, assessment

**Citation**:
A structured reference attached to every flag in a Memo. Contains three fields: source name, specific reference (layer name / document section / queue snapshot), and retrieval date. Rendered inline in the Memo.
_Avoid_: Link, source, reference (when meaning the structured Citation object)

**Ordinance**:
A town's enacted solar zoning rules, retrieved via a prioritized source lookup (eCode360 → Municode → town website → NYSERDA guidebook). Cached with a 30-day TTL; retrieval date is always shown in the citation. Absence of a found ordinance does not trigger a Hard Disqualifier.
_Avoid_: Zoning code, local law, regulation (when referring to the retrieved document specifically)

**Slope**:
Mean slope across the Parcel polygon, derived from USGS 3DEP elevation data. Scored as: ≤5% = no deduction (0pts), 5–15% = mild deduction (−8pts), >15% = strong deduction (−15pts). Never a Hard Disqualifier.
_Avoid_: Grade, pitch, incline

**Viability Score Weights**:
Scoring deductions applied after Hard Disqualifiers are cleared. Transmission distance: ≤1 mile = 0, 1–5 miles = −10, 5–10 miles = −20, >10 miles = −35. NYISO queue congestion within 10 miles: <500 MW = 0, 500–1,500 MW = −10, >1,500 MW = −20. Flood zone: −20 for AE/AH/AO/VE overlap, −10 for Zone X shaded, 0 for Zone X unshaded or no overlap. Slope: ≤5% = 0, 5–15% = −8, >15% = −15. Ordinance: up to −10, determined by LLM from ordinance text. All other deductions computed deterministically.

## Relationships

- A **Site** resolves to exactly one **Parcel** (or a 500m point buffer if parcel data is unavailable, clearly marked in the Memo)

## Example dialogue

> **Dev:** "This site has a small NWI wetland patch in the corner — should we still give it a score?"
> **Domain expert:** "No. Any wetland overlap is a **Hard Disqualifier**. The **Viability Score** goes to zero and the **Memo** shows the disqualifier with its **Citation**. The analyst can decide later whether the overlap is avoidable, but Helios doesn't make that call."

> **Dev:** "The town's **Ordinance** requires a 500ft setback from property lines. Is that a **Moratorium**?"
> **Domain expert:** "No — a **Moratorium** is an active ban on applications. Restrictive setbacks are an **Ordinance** that costs points in the **Viability Score**, but the site isn't disqualified."

> **Dev:** "We couldn't resolve a **Parcel** for this address. Should we skip the environmental checks?"
> **Domain expert:** "No — fall back to the 500m point buffer, run all checks, and mark the **Memo** clearly that the boundary is estimated. The **Memo** always has all eight sections."

## Flagged ambiguities

- "site" and "parcel" were used interchangeably — resolved: **Site** is the user's input; **Parcel** is the GIS record it maps to. They are 1:1 for pre-screening.
