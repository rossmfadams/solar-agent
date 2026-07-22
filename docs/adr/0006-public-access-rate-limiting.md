# Public access policy: per-IP rate limit + global concurrency cap, no auth

Helios is now a public, unauthenticated, portfolio-linked app rather than an internal analyst tool, and every pipeline run costs real money (Claude API calls, geocoding, third-party data lookups). We need abuse/cost protection that doesn't require login, but also can't penalize legitimate group usage — a hiring manager sharing the link around an office, or several people trying it at once during an interview, all appear as a single shared IP behind NAT.

We're using a generous per-IP rate limit (in-memory, e.g. ~15-20 runs/hour/IP — high enough not to bite a small group demo) combined with a global concurrency cap (e.g. max ~5 runs in flight across the whole app at once) as the real backstop against worst-case simultaneous spend. The concurrency cap bounds cost regardless of how many people share an IP; the per-IP limit's job is narrowed to stopping a single actor from scripting large volumes of sequential requests. Both limits fail with a friendly message, not a bare 429.

CAPTCHA and stricter per-IP-only limiting were both rejected: CAPTCHA adds friction to a demo whose value is a smooth, impressive flow, and a strict per-IP limit alone would break the shared-office-IP scenario without the concurrency cap actually bounding cost.

## Consequences

- This also drove the decision to drop the Batch Uploads screen from the design system entirely (see [ADR-0004](0004-react-spa-frontend-on-flyio.md)) — batch would let one request trigger N pipeline runs, defeating the concurrency cap.
- Rate limit state is in-memory (single Fly Machine, no Redis) — acceptable at this scale; would need revisiting if this ever ran on multiple concurrent Machines.
