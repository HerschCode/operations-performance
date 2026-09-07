CREATE INDEX IF NOT EXISTS idx_events_case_id ON staging.events(case_id);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON staging.events(timestamp);
CREATE INDEX IF NOT EXISTS idx_process_cases_supplier ON analytics.process_cases(supplier_id);
CREATE INDEX IF NOT EXISTS idx_process_cases_category ON analytics.process_cases(category);
