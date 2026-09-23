-- Rolling 28-day SLA breach rate, using a RANGE window frame over an actual time interval
-- (not ROWS -- ROWS BETWEEN 27 PRECEDING would give the last 28 *rows*, which is wrong
-- whenever case volume isn't perfectly uniform day to day; RANGE ... INTERVAL '27 days'
-- PRECEDING gives the last 28 *calendar days* regardless of how many cases fall in them).
-- One row per case, each showing the breach rate of its own trailing 28-day cohort -- this
-- is what an ops dashboard would actually plot as a trend line, not a single aggregate.
SELECT
    case_id,
    start_time,
    sla_breach,
    ROUND(
        AVG(CASE WHEN sla_breach THEN 1.0 ELSE 0.0 END) OVER (
            ORDER BY start_time
            RANGE BETWEEN INTERVAL '27 days' PRECEDING AND CURRENT ROW
        )::numeric, 3
    ) AS trailing_28d_breach_rate,
    COUNT(*) OVER (
        ORDER BY start_time
        RANGE BETWEEN INTERVAL '27 days' PRECEDING AND CURRENT ROW
    ) AS trailing_28d_case_count
FROM (
    SELECT
        pc.case_id, pc.start_time,
        pc.cycle_time_hours > COALESCE(r.target_hours, 240) AS sla_breach
    FROM analytics.process_cases pc
    LEFT JOIN analytics.sla_rules r ON r.category = pc.category
) scored
ORDER BY start_time
LIMIT 20;
