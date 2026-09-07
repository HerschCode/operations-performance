# Data Dictionary

Every field the pipeline touches, what it means, and where it comes from. If a field here doesn't
match what a table/API response actually returns, that's a bug -- same rule as
`analytical-methodology.md` for metrics.

## Source data
Real fields come from the BPI Challenge 2019 procurement event log (XES export, columns renamed
in `src/ingestion/load_event_log.py:RAW_COLUMN_MAP`). Synthetic fields are generated to fill gaps
the real log doesn't cover (business rules, SLA targets) -- see `docs/data-contract.md` for the
full real-vs-synthetic breakdown.

| Field | Type | Source | Description |
|---|---|---|---|
| `case_id` | string | Real (`case:concept:name`) | Unique identifier for one procurement case (one purchase order's full lifecycle) |
| `activity` | string | Real (`concept:name`) | The process step this event represents (e.g. "Create Purchase Order", "Record Goods Receipt") |
| `timestamp` | datetime | Real (`time:timestamp`) | When this event occurred |
| `resource` | string | Real (`org:resource`) | The person/system that performed the activity. `UNKNOWN` after cleaning if missing in source |
| `purchase_order_id` | string | Real (`case:Purchasing Document`) | The underlying PO number this case relates to |
| `item_id` | string | Real (`case:Item`) | Line-item identifier within the PO |
| `category` | string | Real (`case:Spend area text`) | Spend category -- drives which SLA target applies (`config/sla.yaml`) |
| `supplier_id` | string | Real (`case:Vendor`) | Vendor identifier. `UNKNOWN` after cleaning if missing in source |

## Derived fields (computed, not sourced)
| Field | Computed by | Description |
|---|---|---|
| `event_count` | `build_process_cases.py` | Number of events in this case |
| `start_time` / `end_time` | `build_process_cases.py` | First / last event timestamp for the case |
| `cycle_time_hours` | `build_process_cases.py` | `end_time - start_time` in hours -- see `analytical-methodology.md` |
| `variant` | `build_process_cases.py` | Full ordered activity sequence, joined as `"A -> B -> C"` |
| `variant_frequency` | `build_process_cases.py` | How many other cases share this exact variant |
| `sla_target_hours` | `sla_analysis.evaluate_sla` | The SLA threshold applied to this case, from `config/sla.yaml` |
| `sla_breach` | `sla_analysis.evaluate_sla` | `cycle_time_hours > sla_target_hours` |
| `has_rework` | `rework.rework_by_case` | Whether this case has a non-allowed repeated activity |
| `breach_probability` / `risk_level` | `src/ml/predict.py` | Model output -- see `docs/ml-model.md` |

## Synthetic-only fields (business context, not in BPI 2019)
| Field | Defined in | Description |
|---|---|---|
| SLA targets by category | `config/sla.yaml` | Business rule, not derivable from the event log itself |
| Expected process sequence | `config/process.yaml` | The "correct" P2P path used for conformance checking |
| `allowed_repeats` | `config/process.yaml` | Which repeated activities are normal operation, not rework |

## Fields intentionally not modeled yet
Order value/monetary amount, business unit, and region are referenced in earlier planning
documents and in `docs/ml-model.md`'s "known limitations" as a reasonable next feature set, but
aren't wired into the current pipeline -- BPI 2019 does carry some monetary fields under different
column names depending on export version; confirm the exact column name against your actual export
before adding them (`load_event_log.py:RAW_COLUMN_MAP`), rather than assuming a name.
