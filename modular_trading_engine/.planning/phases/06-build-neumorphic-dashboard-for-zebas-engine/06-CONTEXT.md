# Phase 06: Build Neumorphic Dashboard for Zebas Engine - Context

**Gathered:** 2026-04-10
**Status:** Ready for planning
**Source:** User request & Previous Knowledge Items

<domain>
## Phase Boundary

This phase involves building a real-time monitoring dashboard for the Zebas Trading Engine. It includes an embedded backend API (FastAPI) inside the engine to broadcast internal state via WebSockets, and a React-based frontend using a "Sleeker Neumorphic" aesthetic.
</domain>

<decisions>
## Implementation Decisions

### Technical Stack
- **Backend:** FastAPI embedded inside the Python bot process, using Lifespan context managers to run the background trading engine and websocket server concurrently.
- **Frontend:** React + Vite + Vanilla CSS (No Tailwind unless approved).

### Dashboard Data Requirements
- **Break Level:** Display current coordinates/direction.
- **Origin Level:** Display current origin coordinates.
- **Hold Level Status:** Display timestamp, tests, candidate classification, and whether it triggered a limit entry order.
- **Filtering:** Provide a functional UI filter to strip out market noise (stale levels, unvalidated data) and highlight active candidates/orders.

### UI/UX Design Language (Sleeker Neumorphism)
- Use a flatter palette with a muted matte blue accent (`#5b8ec5`).
- Ensure tight shadows (`6px 6px 12px #c8d0db`, etc.).
- Reduce radii: Outer cards 16px, Inner components 8px.
- Follow meticulous numerical formatting (1 decimal place).
</decisions>

<canonical_refs>
## Canonical References

### Design & Architecture
- `knowledge/real_time_trading_dashboard/artifacts/architecture/fastapi_ws_lifespan.md` — FastAPI structure for bridging sync execution with async APIs
- `knowledge/real_time_trading_dashboard/artifacts/frontend/neumorphic_ui_design.md` — Neumorphic tokens and design systems
</canonical_refs>

<specifics>
## Specific Ideas

- The UI should clearly highlight tracking states to monitor exactly what the mathematical engine is watching.
</specifics>

<deferred>
## Deferred Ideas

- None.
</deferred>
