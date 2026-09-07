# Dashboard — Build Spec

This documents the exact pages, visuals, and data sources for the Power BI / Looker Studio build.
The dashboard itself isn't something a code repo can contain — build it against the running API
(`src/api/`) or directly against `analytics.process_cases` / `staging.events` in Postgres, then
drop screenshots in `dashboard/screenshots/` and link them from here.

## Data source
Point the BI tool at the FastAPI service (`/metrics/*`, `/suppliers/performance`,
`/reports/management`) for a REST-based build, or directly at the Postgres `analytics` schema for
a native-connector build. The REST route is the one that also validates against
`operations-assistant` later, since that project consumes the same endpoints.

## Page 1 — Executive Overview
Source: `GET /metrics/cycle-time`, `GET /metrics/sla`
- KPI cards: total cases, avg cycle time, SLA breach rate, rework rate (from
  `generate_summary.build_executive_summary`)
- Trend line: cycle time and breach rate over time (requires date filtering — see "Parameterization" below)

## Page 2 — Process Performance
Source: `GET /metrics/bottlenecks`
- Bar chart: stage duration (avg/median/p90) ranked descending
- % of total delay per stage, so the biggest lever is visually obvious

## Page 3 — Bottleneck Analysis
Source: `GET /metrics/bottlenecks?top_n=10`
- Same data as Page 2, filtered/sliced by segment (category, supplier) using the `bottlenecks_by_segment` function's shape

## Page 4 — Supplier Performance
Source: `GET /suppliers/performance`
- Table: supplier, order count, avg cycle time, SLA breach rate, rank
- Note in the dashboard itself that suppliers below the `min_volume` threshold are excluded — don't let a viewer misread absence as "this supplier is fine"

## Page 5 — Process Conformance
Source: `src/analytics/conformance.py` (not yet exposed via API — add `GET /metrics/conformance` when building this page)
- Conformance rate KPI
- Deviation-type breakdown (skipped / unexpected / repeated / out-of-order)

## Page 6 — SLA Risk
Source: `GET /orders/{case_id}/risk` (single-case) — for a dashboard-wide view, add a batch
endpoint (`GET /metrics/sla-risk-distribution`) rather than calling per-case in a loop
- Risk distribution (LOW/MEDIUM/HIGH counts)
- Table of current high-risk open cases

## Page 7 — Recommendations
Source: `GET /reports/management`
- Render the Finding → Evidence → Impact → Recommendation markdown directly, or rebuild it as
  native BI-tool cards using the same `build_management_report()` output structure

## Parameterization
`generate_summary.filter_period()` and `filter_segment()` already support date-range and segment
scoping — the dashboard should expose these as slicers/filters rather than shipping one static
snapshot. This is what makes it a tool someone reruns weekly instead of a one-off screenshot.

## Screenshots
Add build screenshots here as each page is completed:
```
dashboard/screenshots/
  01-executive-overview.png
  02-process-performance.png
  ...
```
