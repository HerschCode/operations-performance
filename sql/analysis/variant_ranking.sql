-- Rank process variants within each category by frequency, using RANK() (not ROW_NUMBER --
-- ties matter here: two variants with the identical case count should share a rank, not be
-- arbitrarily split by insertion order) and DENSE_RANK for a gap-free ranking alongside it,
-- so the difference between the two is visible in the same result set rather than asserted.
SELECT
    category,
    variant,
    case_count,
    RANK()       OVER (PARTITION BY category ORDER BY case_count DESC) AS rank_with_gaps,
    DENSE_RANK() OVER (PARTITION BY category ORDER BY case_count DESC) AS rank_no_gaps,
    ROUND(
        100.0 * case_count / SUM(case_count) OVER (PARTITION BY category), 1
    ) AS pct_of_category_cases
FROM (
    SELECT category, variant, COUNT(*) AS case_count
    FROM analytics.process_cases
    WHERE category IS NOT NULL
    GROUP BY category, variant
) v
ORDER BY category, rank_with_gaps
LIMIT 30;
