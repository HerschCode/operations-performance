-- Each case joined to its category's SLA target, with the breach flag computed once here
-- rather than re-derived (inconsistently) in every mart that needs it -- COALESCE(240) matches
-- src/analytics/sla_analysis.py's own default target for a category with no configured rule.
select
    pc.case_id,
    pc.category,
    pc.supplier_id,
    pc.start_time,
    pc.end_time,
    pc.cycle_time_hours,
    coalesce(r.target_hours, 240) as sla_target_hours,
    pc.cycle_time_hours > coalesce(r.target_hours, 240) as sla_breach
from {{ ref('stg_process_cases') }} pc
left join {{ ref('stg_sla_rules') }} r on r.category = pc.category
